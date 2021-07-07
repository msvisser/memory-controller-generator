from nmigen import *
from nmigen.cli import main
from nmigen.asserts import Assert

from functools import reduce

from generator.error_correction import ExtendedHammingCode, HammingCode, IdentityCode


class TestTop(Elaboratable):
    def __init__(self, data_bits):
        self.data_bits = data_bits
        self.code = ExtendedHammingCode(data_bits=data_bits)

        self.data_in = Signal(unsigned(self.code.data_bits))
        self.data_out = Signal(unsigned(self.code.data_bits))
        self.flips = Signal(unsigned(self.code.total_bits))
        self.error = Signal()
        self.uncorrectable_error = Signal()

    def elaborate(self, platform):
        m = Module()

        self.code.generate_matrices()

        m.submodules.encoder = encoder = self.code.encoder()
        m.submodules.decoder = decoder = self.code.decoder()

        m.d.comb += [
            encoder.data_in.eq(self.data_in),
            self.data_out.eq(decoder.data_out),
        ]

        if platform == "formal":
            m.d.comb += decoder.enc_in.eq(encoder.enc_out ^ self.flips)

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
            m.d.comb += decoder.enc_in.eq(encoder.enc_out ^ self.flips)
            m.d.comb += [
                self.error.eq(decoder.error),
                self.uncorrectable_error.eq(decoder.uncorrectable_error),
            ]

        return m

    def ports(self):
        return [self.data_in, self.data_out, self.flips]


if __name__ == "__main__":
    top = TestTop(data_bits=8)
    platform = None
    # platform = "formal"
    main(design=top, platform=platform, name="top", ports=top.ports())


