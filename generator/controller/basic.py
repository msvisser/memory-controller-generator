from nmigen import *

from .record import MemoryRequestRecord, MemoryResponseRecord, SRAMInterfaceRecord
from ..error_correction import GenericCode


class BasicController(Elaboratable):
    """
    Simplest implementation of an error correcting memory controller.

    This is a very simple error correcting memory controller. The only function this controller has is to encode and
    decoder the data going to and coming from the memory. The rest of this module simply handles the arbitration of
    the request and response ports to make sure no requests are accepted when we are unable to handle them,
    and that all responses are only delivered once.
    """

    def __init__(self, code: GenericCode, addr_width):
        self.code = code

        # User interface
        self.req = MemoryRequestRecord(addr_width, code.data_bits)
        self.rsp = MemoryResponseRecord(code.data_bits)

        # SRAM interface
        self.sram = SRAMInterfaceRecord(addr_width, code.total_bits)

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
            self.req.ready.eq(self.rsp.ready),

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

        return m

    def ports(self):
        return [*self.req.ports(), *self.rsp.ports(), *self.sram.ports()]
