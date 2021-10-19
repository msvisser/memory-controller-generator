import random
import unittest

from nmigen import *
from nmigen.back import pysim

from generator.controller.record import MemoryRequestRecord, MemoryResponseRecord, SRAMInterfaceRecord
from generator.controller.write_back import WriteBackController
from generator.error_correction import GenericCode, ExtendedHammingCode


class WriteBackControllerTestTop(Elaboratable):
    """
    Testing top module for checking the functionality of the BasicController.

    This module implements a BasicController and a memory to simulate and test the functionality of the
    BasicController. The memory is connected to the controller directly and should behave as a normal SRAM. The
    request and response ports of the controller are exposed for the simulator to control.
    """

    def __init__(self, code: GenericCode, addr_bits: int):
        self.code = code
        self.addr_bits = addr_bits

        self.req = MemoryRequestRecord(addr_bits, code.data_bits)
        self.rsp = MemoryResponseRecord(code.data_bits)

        self.sram = SRAMInterfaceRecord(addr_bits, code.total_bits)

        self.bit_flipper = Signal(code.total_bits)

        self.mem = None

    def elaborate(self, platform):
        m = Module()

        m.submodules.controller = controller = WriteBackController(self.code, addr_width=self.addr_bits)

        # Create a memory for simulation
        self.mem = mem = Memory(width=self.code.total_bits, depth=2 ** self.addr_bits, init=list(0 for _ in range(2 ** self.addr_bits)))
        read_port = mem.read_port(transparent=False)
        write_port = mem.write_port()
        m.submodules += read_port, write_port

        # Hook up the memory ports to the controller
        m.d.comb += [
            read_port.addr.eq(controller.sram.addr),
            read_port.en.eq(controller.sram.clk_en),
            controller.sram.read_data.eq(read_port.data ^ self.bit_flipper),

            write_port.addr.eq(controller.sram.addr),
            write_port.en.eq(controller.sram.clk_en & controller.sram.write_en),
            write_port.data.eq(controller.sram.write_data),
        ]

        m.d.comb += [
            self.sram.addr.eq(controller.sram.addr),
            self.sram.clk_en.eq(controller.sram.clk_en),
            self.sram.write_en.eq(controller.sram.write_en),
            self.sram.write_data.eq(controller.sram.write_data),
            self.sram.read_data.eq(controller.sram.read_data),
        ]

        # Hook up all other controller signals to the external signals
        m.d.comb += [
            self.req.connect(controller.req),
            controller.rsp.connect(self.rsp),
        ]

        return m

    def ports(self):
        return [*self.req.ports(), *self.rsp.ports(), *self.sram.ports(), self.bit_flipper]


class TestBasicController(unittest.TestCase):
    """Simulation testcase to exercise the BasicController implementation"""

    def test_simulation(self):
        # Set the clock period and number of cycles
        clk_period = 1e-6
        clk_cycles = 1e3

        # Setup the error correction code used in this test
        code = ExtendedHammingCode(data_bits=32)
        code.generate_matrices()

        # Setup the nMigen simulator
        top = WriteBackControllerTestTop(code, addr_bits=4)
        sim = pysim.Simulator(top)
        sim.add_clock(clk_period)

        # Seed the random generator to make the test deterministic
        random.seed(0)

        # Process responsible for creating random requests
        def process_req():
            while True:
                enable = random.random() < 0.75

                yield top.req.valid.eq(enable)
                yield top.req.addr.eq(random.randint(0, 15))
                yield top.req.write_en.eq(random.random() < 0.125)
                yield top.req.write_data.eq(random.randrange(0, 2 ** 32))

                yield
                while enable and not (yield top.req.ready):
                    yield

        # Process responsible for accepting responses with a random chance
        def process_rsp():
            while True:
                enable = random.random() < 0.66
                yield top.rsp.ready.eq(enable)
                yield
                while enable and not (yield top.rsp.valid):
                    yield

        def process_bit_flipper():
            while True:
                enable = random.random()
                if enable < 0.1:
                    offset = random.randint(0, code.total_bits - 1)
                    # yield top.bit_flipper.eq(3 << offset)
                elif enable < 0.5:
                    offset = random.randint(0, code.total_bits)
                    yield top.bit_flipper.eq(1 << offset)
                else:
                    yield top.bit_flipper.eq(0)
                yield

        # Process responsible for monitoring the interfaces and checking that the controller behaves
        def monitor():
            outstanding_request = 0
            memory_mirror = list(0 for _ in range(16))
            memory_previous = list(0 for _ in range(16))
            last_request = (0, 0, 0)

            while True:
                # Run one clock cycle
                yield
                # Get the request and response, ready and valid
                req_valid = yield top.req.valid
                req_ready = yield top.req.ready
                rsp_valid = yield top.rsp.valid
                rsp_ready = yield top.rsp.ready

                # If a response is accepted
                if rsp_valid and rsp_ready:
                    last_addr, last_write_en, _ = last_request
                    data = (yield top.rsp.read_data)
                    error = (yield top.rsp.error)
                    uncorrectable_error = (yield top.rsp.uncorrectable_error)

                    # If the last operation was a write, check the memory before the write operation
                    if last_write_en:
                        expected = memory_previous[last_addr]
                        if not uncorrectable_error:
                            # print(f"{last_addr} {data:x} {expected:x}")
                            self.assertEqual(data, expected)
                    # If the last operation was a read, check the current memory state
                    else:
                        expected = memory_mirror[last_addr]
                        if not uncorrectable_error:
                            # print(f"{last_addr} {data:x} {expected:x}")
                            self.assertEqual(data, expected)

                    outstanding_request -= 1

                # If a request is accepted
                if req_valid and req_ready:
                    addr = (yield top.req.addr)
                    write_en = (yield top.req.write_en)
                    data = (yield top.req.write_data)

                    # If the operation is a write, update the mirror of the memory
                    if write_en:
                        memory_previous[addr] = memory_mirror[addr]
                        memory_mirror[addr] = data

                    # Save this request for use in response handling
                    last_request = (addr, write_en, data)
                    outstanding_request += 1

                # Make sure that there are always 0 or 1 outstanding requests
                self.assertIn(outstanding_request, (0, 1))

        # Add the processes to the simulator
        sim.add_sync_process(process_req)
        sim.add_sync_process(process_rsp)
        sim.add_sync_process(process_bit_flipper)
        sim.add_sync_process(monitor)
        # Run the simulator for a defined number of cycles
        sim.run_until(clk_cycles * clk_period, run_passive=True)


if __name__ == "__main__":
    unittest.main()
