from nmigen import *

from .record import MemoryRequestRecord, MemoryResponseRecord, SRAMInterfaceRecord
from ..error_correction import GenericCode


class WriteBackController(Elaboratable):
    def __init__(self, code: GenericCode, addr_width: int):
        self.code = code
        self.addr_width = addr_width

        self.req = MemoryRequestRecord(addr_width, code.data_bits)
        self.rsp = MemoryResponseRecord(code.data_bits)

        self.sram = SRAMInterfaceRecord(addr_width, code.total_bits)

    def elaborate(self, platform):
        m = Module()

        m.submodules.encoder = encoder = self.code.encoder()
        m.submodules.decoder = decoder = self.code.decoder()

        response_writeback_valid = Signal()
        last_req_addr = Signal(unsigned(self.addr_width))
        m.d.sync += last_req_addr.eq(self.req.addr)

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
            m.d.sync += [
                self.rsp.valid.eq(1),
                response_writeback_valid.eq(~self.req.write_en),
            ]
        # If no request fires and the response does fire, the buffered response is consumed and no longer valid
        with m.Elif(rsp_fire):
            m.d.sync += self.rsp.valid.eq(0)

        with m.If(response_writeback_valid & decoder.error & ~decoder.uncorrectable_error):
            m.d.comb += [
                self.req.ready.eq(0),

                self.sram.clk_en.eq(1),
                self.sram.addr.eq(last_req_addr),
                self.sram.write_en.eq(1),
                self.sram.write_data.eq(decoder.enc_out),
            ]

        m.d.sync += response_writeback_valid.eq(0)

        return m

    def ports(self) -> [Signal]:
        return [*self.req.ports(), *self.rsp.ports(), *self.sram.ports()]
