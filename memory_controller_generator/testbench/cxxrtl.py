import logging
import time

import numpy as np
from amaranth import *
from amaranth.cli import main_parser, main_runner

import memory_controller_generator.controller
import memory_controller_generator.error_correction
from ..controller.generic import GenericController
from ..controller.record import MemoryRequestRecord, MemoryResponseRecord, SRAMInterfaceRecord


class CXXRTLTestbench(Elaboratable):
    def __init__(self, controller: GenericController):
        self.controller = controller
        self.code = controller.code
        self.addr_bits = controller.addr_width

        self.req = MemoryRequestRecord(self.addr_bits, code.data_bits)
        self.rsp = MemoryResponseRecord(code.data_bits)
        self.sram = SRAMInterfaceRecord(self.addr_bits, code.total_bits)

        self.mem = None

    def elaborate(self, platform):
        m = Module()

        m.submodules.controller = controller = self.controller
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


if __name__ == "__main__":
    np.set_printoptions(linewidth=200)

    # Build the commandline argument parser
    parser = main_parser()
    parser.add_argument("-c", "--code", dest="code_name", default="HammingCode")
    parser.add_argument("-x", "--controller", dest="controller_name", default="BasicController")
    parser.add_argument("-b", "--bits", dest="data_bits", default=32, type=int)
    parser.add_argument("-v", "--verbose", dest="verbose", action="count", default=0)
    parser.add_argument("-t", "--timeout", dest="timeout", default=30.0, type=float)
    parser.add_argument("-f", "--force-rebuild", dest="force_rebuild", default=False, const=True, action="store_const")
    args = parser.parse_args()

    # Set the logging level based on the verbose-ness
    if args.verbose == 0:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG
    log_format = "%(levelname)8s: %(message)s"
    logging.basicConfig(level=log_level, format=log_format)

    # Dynamically select the error correction code based on the supplied name
    if not hasattr(memory_controller_generator.error_correction, args.code_name):
        raise ValueError(f"Unknown error correction code: {args.code_name}")
    code_class = getattr(memory_controller_generator.error_correction, args.code_name)
    code = code_class(data_bits=args.data_bits)

    # Dynamically select the controller based on the supplied name
    if not hasattr(memory_controller_generator.controller, args.controller_name):
        raise ValueError(f"Unknown controller: {args.controller_name}")
    controller_class = getattr(memory_controller_generator.controller, args.controller_name)

    # Measure the time it takes to generate the matrices for this code
    start = time.time()
    code.generate_matrices_cached(timeout=args.timeout, force_rebuild=args.force_rebuild)
    duration = 1000 * (time.time() - start)
    logging.info(f"Matrix generation took {duration:.2f}ms")

    # Log the parity-check matrix
    logging.debug("Parity-check matrix:")
    for row in code.parity_check_matrix:
        logging.debug(f"  {row}")

    # Create top module
    ctrl = controller_class(code=code, addr_width=13)
    top = CXXRTLTestbench(ctrl)

    # Run the nMigen main runner
    main_runner(parser, args, design=top, platform="cxxrtl", name="top", ports=top.ports())
