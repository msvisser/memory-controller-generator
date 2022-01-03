import logging
import time
from typing import List

import numpy as np
from amaranth import *
from amaranth.asserts import Assert
from amaranth.cli import main_parser, main_runner

import generator.error_correction
from generator.controller import BasicController
from generator.controller.generic import GenericController
from generator.controller.partial_wrapper import PartialWriteWrapper
from generator.controller.record import MemoryRequestRecord, MemoryResponseRecord, MemoryRequestWithPartialRecord, \
    SRAMInterfaceRecord
from generator.controller.write_back import WriteBackController
from generator.error_correction import GenericCode
from generator.testbench.cxxrtl import CXXRTLTestbench
from generator.util.reduce import or_reduce


class TestTop(Elaboratable):
    def __init__(self, code: GenericCode):
        self.code = code

        self.write_data = Signal(unsigned(self.code.total_bits))
        self.read_data = Signal(unsigned(self.code.total_bits))

        self.data_in = Signal(unsigned(self.code.data_bits))
        self.data_out = Signal(unsigned(self.code.data_bits))
        self.flips = Signal(unsigned(self.code.total_bits))
        self.error = Signal()
        self.uncorrectable_error = Signal()

    def elaborate(self, platform):
        m = Module()

        m.submodules.encoder = encoder = self.code.encoder()
        m.submodules.decoder = decoder = self.code.decoder()

        m.d.comb += [
            encoder.data_in.eq(self.data_in),
            self.write_data.eq(encoder.enc_out),
            decoder.enc_in.eq(self.read_data),
            self.data_out.eq(decoder.data_out),
            self.error.eq(decoder.error),
            self.uncorrectable_error.eq(decoder.uncorrectable_error),
        ]

        if platform == "formal":
            m.d.comb += self.read_data.eq(self.write_data ^ self.flips)

            with m.If(self.flips == 0):
                # When no bits are flipped the resulting decoded data should match the encoded data exactly.
                # The error and uncorrectable_error lines should stay low in this case.
                m.d.comb += [
                    Assert(encoder.data_in == decoder.data_out),
                    Assert(encoder.enc_out == decoder.enc_out),
                    Assert(~decoder.error),
                    Assert(~decoder.uncorrectable_error),
                ]

            # True if the current flips should be correctable
            is_correctable = Signal()
            m.d.comb += is_correctable.eq(0)
            for correctable_error in self.code.correctable_errors:
                flip = or_reduce(1 << i for i in correctable_error)
                with m.If(self.flips == flip):
                    m.d.comb += is_correctable.eq(1)

            with m.If(is_correctable):
                # If the error should be correctable the encoded data should match the decoded data exactly,
                # but the error line should be high. The uncorrectable_error line should still be low.
                m.d.comb += [
                    Assert(encoder.data_in == decoder.data_out),
                    Assert(encoder.enc_out == decoder.enc_out),
                    Assert(decoder.error),
                    Assert(~decoder.uncorrectable_error),
                ]

            # True if the current flips should be detectable
            is_detectable = Signal()
            m.d.comb += is_detectable.eq(0)
            for detectable_error in self.code.detectable_errors:
                flip = or_reduce(1 << i for i in detectable_error)
                with m.If(self.flips == flip):
                    m.d.comb += is_detectable.eq(1)

            with m.If(is_detectable):
                # If the error is detectable, but not correctable, the error and uncorrectable_error lines should be
                # high and no assertions can be made on the output data.
                m.d.comb += [
                    Assert(decoder.error),
                    Assert(decoder.uncorrectable_error),
                ]

        return m

    def ports(self):
        return [
            self.write_data, self.read_data,
            self.data_in, self.data_out, self.flips,
            self.error, self.uncorrectable_error
        ]


class WrapperTop(Elaboratable):
    def __init__(self, controller: GenericController):
        self.controller = controller

        self.req = MemoryRequestWithPartialRecord(controller.addr_width, controller.code.data_bits, granularity=8)
        self.rsp = MemoryResponseRecord(controller.code.data_bits)

        self.sram = SRAMInterfaceRecord(controller.addr_width, controller.code.data_bits)

    def elaborate(self, platform):
        m = Module()

        m.submodules.controller = self.controller
        m.submodules.wrapper = wrapper = PartialWriteWrapper(addr_width=self.controller.addr_width, data_bits=self.controller.code.data_bits)

        m.d.comb += [
            self.req.connect(wrapper.req_in),
            wrapper.req_out.connect(self.controller.req),
            self.controller.rsp.connect(wrapper.rsp_in),
            wrapper.rsp_out.connect(self.rsp),

            self.controller.sram.connect(self.sram),
        ]

        return m

    def ports(self) -> List[Signal]:
        return [*self.req.ports(), *self.rsp.ports(), *self.sram.ports()]


if __name__ == "__main__":
    np.set_printoptions(linewidth=200)

    # Build the commandline argument parser
    parser = main_parser()
    parser.add_argument("-c", "--code", dest="code_name", default="HammingCode")
    parser.add_argument("-x", "--controller", dest="controller_name", default="BasicController")
    parser.add_argument("-b", "--bits", dest="data_bits", default=32, type=int)
    parser.add_argument("-v", "--verbose", dest="verbose", action="count", default=0)
    parser.add_argument("-p", "--platform", dest="platform", default=None)
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
    if not hasattr(generator.error_correction, args.code_name):
        raise ValueError(f"Unknown error correction code: {args.code_name}")
    code_class = getattr(generator.error_correction, args.code_name)
    code = code_class(data_bits=args.data_bits)

    # Dynamically select the controller based on the supplied name
    if not hasattr(generator.controller, args.controller_name):
        raise ValueError(f"Unknown controller: {args.controller_name}")
    controller_class = getattr(generator.controller, args.controller_name)

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
    # top = TestTop(code=code)
    # top = BasicController(code=code, addr_width=32)
    # top = WriteBackController(code=code, addr_width=32)
    # top = CXXRTLTestbench(code=code, addr_bits=10)

    ctrl = controller_class(code=code, addr_width=13)
    top = WrapperTop(ctrl)

    # Set the platform
    platform = args.platform

    # Run the nMigen main runner
    main_runner(parser, args, design=top, platform=platform, name="top", ports=top.ports())
