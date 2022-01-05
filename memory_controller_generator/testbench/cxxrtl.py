from amaranth import *

from ..controller import BasicController, WriteBackController
from ..controller.record import MemoryRequestRecord, MemoryResponseRecord, SRAMInterfaceRecord
from ..error_correction import GenericCode


class CXXRTLTestbench(Elaboratable):
    def __init__(self, code: GenericCode, addr_bits: int):
        self.code = code
        self.addr_bits = addr_bits

        self.req = MemoryRequestRecord(addr_bits, code.data_bits)
        self.rsp = MemoryResponseRecord(code.data_bits)
        self.sram = SRAMInterfaceRecord(addr_bits, code.total_bits)

        self.mem = None

    def elaborate(self, platform):
        m = Module()

        m.submodules.controller = controller = WriteBackController(self.code, addr_width=self.addr_bits)
        m.submodules.requester = requester = CXXRTLRequester(data_bits=self.code.data_bits, addr_bits=self.addr_bits)

        # Create a memory for simulation
        self.mem = mem = Memory(width=self.code.total_bits, depth=2 ** self.addr_bits,
                                init=list(0 for _ in range(2 ** self.addr_bits)))
        read_port = mem.read_port(transparent=False)
        write_port = mem.write_port()
        m.submodules += read_port, write_port

        # Hook up the memory ports to the controller
        m.d.comb += [
            read_port.addr.eq(controller.sram.addr),
            read_port.en.eq(controller.sram.clk_en),
            controller.sram.read_data.eq(read_port.data),

            write_port.addr.eq(controller.sram.addr),
            write_port.en.eq(controller.sram.clk_en & controller.sram.write_en),
            write_port.data.eq(controller.sram.write_data),
        ]

        # Monitor the controller SRAM signals
        m.d.comb += [
            self.sram.addr.eq(controller.sram.addr),
            self.sram.clk_en.eq(controller.sram.clk_en),
            self.sram.write_en.eq(controller.sram.write_en),
            self.sram.write_data.eq(controller.sram.write_data),
            self.sram.read_data.eq(controller.sram.read_data),
        ]

        # Hook up the requester to the controller
        m.d.comb += [
            requester.req.connect(controller.req),
            controller.rsp.connect(requester.rsp),
        ]

        # Monitor the request and response signals
        m.d.comb += [
            self.req.valid.eq(requester.req.valid),
            self.req.ready.eq(requester.req.ready),
            self.req.addr.eq(requester.req.addr),
            self.req.write_en.eq(requester.req.write_en),
            self.req.write_data.eq(requester.req.write_data),

            self.rsp.valid.eq(requester.rsp.valid),
            self.rsp.ready.eq(requester.rsp.ready),
            self.rsp.read_data.eq(requester.rsp.read_data),
            self.rsp.error.eq(requester.rsp.error),
            self.rsp.uncorrectable_error.eq(requester.rsp.uncorrectable_error),
        ]

        return m

    def ports(self):
        return [*self.req.ports(), *self.rsp.ports(), *self.sram.ports()]


class CXXRTLRequester(Elaboratable):
    def __init__(self,  data_bits: int, addr_bits: int):
        self.data_bits = data_bits
        self.addr_bits = addr_bits

        self.req = MemoryRequestRecord(addr_bits, data_bits)
        self.rsp = MemoryResponseRecord(data_bits)

    def elaborate(self, platform):
        m = Module()

        current_request_addr = Signal(unsigned(self.addr_bits))
        m.d.comb += [
            self.req.valid.eq(1),
            self.req.addr.eq(current_request_addr),
            self.req.write_en.eq(0),
            self.req.write_data.eq(0),
        ]

        with m.If(self.req.valid & self.req.ready):
            m.d.sync += current_request_addr.eq(current_request_addr + 1)

        m.d.comb += [
            self.rsp.ready.eq(1),
        ]

        return m
