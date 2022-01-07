import logging
import time
from typing import List

import numpy as np
from amaranth import *
from amaranth.cli import main_parser, main_runner

import memory_controller_generator.controller
import memory_controller_generator.error_correction
from ..controller.generic import GenericController
from ..controller.partial_wrapper import PartialWriteWrapper
from ..controller.record import MemoryResponseRecord, MemoryRequestWithPartialRecord, SRAMInterfaceRecord


class ExampleTop(Elaboratable):
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
    top = ExampleTop(ctrl)

    # Run the nMigen main runner
    main_runner(parser, args, design=top, platform=None, name="top", ports=top.ports())
