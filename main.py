import numpy as np
from nmigen import *
from nmigen.cli import main
from nmigen.asserts import Assert

from functools import reduce

from generator.error_correction import HsiaoCode, ExtendedHammingCode, HammingCode, ParityCode, IdentityCode


class TestTop(Elaboratable):
    def __init__(self, data_bits):
        self.data_bits = data_bits
        self.code = HsiaoCode(data_bits=data_bits)

        self.write_data = Signal(unsigned(self.code.total_bits))
        self.read_data = Signal(unsigned(self.code.total_bits))

        self.data_in = Signal(unsigned(self.code.data_bits))
        self.data_out = Signal(unsigned(self.code.data_bits))
        self.flips = Signal(unsigned(self.code.total_bits))
        self.error = Signal()
        self.uncorrectable_error = Signal()

    def elaborate(self, platform):
        m = Module()

        self.code.generate_matrices(timeout=30.0)

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
    top = TestTop(data_bits=32)
    platform = None
    # platform = "formal"
    main(design=top, platform=platform, name="top", ports=top.ports())


