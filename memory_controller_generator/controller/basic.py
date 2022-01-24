from amaranth import *

from .generic import GenericController


class BasicController(GenericController):
    """
    Simplest implementation of an error correcting memory controller.

    This is a very simple error correcting memory controller. The only function this controller has is to encode and
    decoder the data going to and coming from the memory. The rest of this module simply handles the arbitration of
    the request and response ports to make sure no requests are accepted when we are unable to handle them,
    and that all responses are only delivered once.
    """
    def elaborate(self, platform):
        m = Module()

        m.submodules.encoder = encoder = self.code.encoder()
        m.submodules.decoder = decoder = self.code.decoder()

        req_fire = self.req.valid & self.req.ready
        rsp_fire = self.rsp.valid & self.rsp.ready

        m.d.comb += [
            # Connect request
            self.sram.clk_en.eq(req_fire),
            self.sram.addr.eq(self.req.addr),
            self.sram.write_en.eq(self.req.write_en),
            encoder.data_in.eq(self.req.write_data),
            self.sram.write_data.eq(encoder.enc_out),
            self.req.ready.eq((self.rsp.valid & self.rsp.ready) | ~self.rsp.valid),

            # Connect decoder
            decoder.enc_in.eq(self.sram.read_data),
            self.rsp.read_data.eq(decoder.data_out),
            self.rsp.error.eq(decoder.error),
            self.rsp.uncorrectable_error.eq(decoder.uncorrectable_error),
        ]

        # When a request fires it is accepted, therefore the response should always be valid on the next cycle
        with m.If(req_fire):
            m.d.sync += self.rsp.valid.eq(1)
        # If no request fires and the response does fire, the buffered response is consumed and no longer valid
        with m.Elif(rsp_fire):
            m.d.sync += self.rsp.valid.eq(0)

        m.d.comb += [
            self.debug.error.eq(decoder.error),
            self.debug.uncorrectable_error.eq(decoder.uncorrectable_error),
            self.debug.flips.eq(decoder.flips),
        ]
        m.d.sync += self.debug.ignore.eq(self.req.debug_ignore)

        return m
