import logging
import time
from functools import reduce

import numpy as np
from nmigen import *
from nmigen.asserts import Assert
from nmigen.cli import main_parser, main_runner

import generator.error_correction


class TestTop(Elaboratable):
    def __init__(self, data_bits, code_name):
        self.data_bits = data_bits

        # Dynamically select the error correction code based on the supplied name
        if not hasattr(generator.error_correction, code_name):
            raise ValueError(f"Unknown error correction code: {code_name}")
        code_class = getattr(generator.error_correction, code_name)
        self.code = code_class(data_bits=data_bits)

        self.write_data = Signal(unsigned(self.code.total_bits))
        self.read_data = Signal(unsigned(self.code.total_bits))

        self.data_in = Signal(unsigned(self.code.data_bits))
        self.data_out = Signal(unsigned(self.code.data_bits))
        self.flips = Signal(unsigned(self.code.total_bits))
        self.error = Signal()
        self.uncorrectable_error = Signal()

    def elaborate(self, platform):
        m = Module()

        # Measure the time it takes to generate the matrices for this code
        start = time.time()
        self.code.generate_matrices(timeout=30.0)
        duration = 1000 * (time.time() - start)
        logging.info(f"Matrix generation took {duration:.2f}ms")

        # Log the parity-check matrix
        logging.debug("Parity-check matrix:")
        for row in self.code.parity_check_matrix:
            logging.debug(f"  {row}")

        m.submodules.encoder = encoder = self.code.encoder()
        m.submodules.decoder = decoder = self.code.decoder()

        m.d.comb += [
            encoder.data_in.eq(self.data_in),
            self.write_data.eq(encoder.enc_out),
            decoder.enc_in.eq(self.read_data),
            self.data_out.eq(decoder.data_out),
        ]

        if platform == "formal":
            m.d.comb += self.read_data.eq(self.write_data ^ self.flips)

            flips_set = Signal(unsigned(8))
            m.d.comb += flips_set.eq(reduce(
                lambda a, b: a + b,
                (self.flips[i] for i in range(self.code.total_bits)),
                C(0, unsigned(8))
            ))

            with m.If(flips_set == 0):
                m.d.comb += [
                    Assert(encoder.data_in == decoder.data_out),
                    Assert(encoder.enc_out == decoder.enc_out),
                    Assert(~decoder.error),
                    Assert(~decoder.uncorrectable_error),
                ]
            with m.Elif(flips_set == 1):
                m.d.comb += [
                    Assert(encoder.data_in == decoder.data_out),
                    Assert(encoder.enc_out == decoder.enc_out),
                    Assert(decoder.error),
                    Assert(~decoder.uncorrectable_error),
                ]
            with m.Elif(flips_set == 2):
                m.d.comb += [
                    # Assert(encoder.data_in == decoder.data_out),
                    # Assert(encoder.enc_out == decoder.enc_out),
                    Assert(decoder.error),
                    Assert(decoder.uncorrectable_error),
                ]
        else:
            m.d.comb += [
                self.error.eq(decoder.error),
                self.uncorrectable_error.eq(decoder.uncorrectable_error),
            ]

        return m

    def ports(self):
        return [
            self.write_data, self.read_data,
            self.data_in, self.data_out, self.flips,
            self.error, self.uncorrectable_error
        ]


if __name__ == "__main__":
    np.set_printoptions(linewidth=200)

    # Build the commandline argument parser
    parser = main_parser()
    parser.add_argument("-c", "--code", dest="code_name", default="HammingCode")
    parser.add_argument("-b", "--bits", dest="data_bits", default=32, type=int)
    parser.add_argument("-v", "--verbose", dest="verbose", action="count", default=0)
    args = parser.parse_args()

    # Set the logging level based on the verbose-ness
    if args.verbose == 0:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG
    log_format = "%(levelname)8s: %(message)s"
    logging.basicConfig(level=log_level, format=log_format)

    # Create top module
    logging.info(f"Selected code: {args.code_name}, with {args.data_bits} bits")
    top = TestTop(data_bits=args.data_bits, code_name=args.code_name)

    # Set the platform
    platform = None
    # platform = "formal"

    # Run the nMigen main runner
    main_runner(parser, args, design=top, platform=platform, name="top", ports=top.ports())
