from amaranth import *

from .generic import GenericController


class WriteBackController(GenericController):
    """
    Implementation of a write-back controller.

    This memory controller will handle requests normally as long as no errors are detected. However, when the decoder
    detects and corrects an error, the corrected value is immediately written back to the memory, to make sure that
    the value in memory is correct. Doing this operation will block the request stream for one cycle.
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

        # Keep track of when a write-back operation might be valid (after a read request)        
        response_writeback_valid = Signal()
        with m.If(req_fire):
            m.d.sync += response_writeback_valid.eq(~self.req.write_en)
        with m.Else():
            m.d.sync += response_writeback_valid.eq(0)
        
        # Keep the address of the last request
        last_req_addr = Signal(unsigned(self.addr_width))
        m.d.sync += last_req_addr.eq(self.req.addr)

        # If the previous request was a read and the decoder detected a correctable error
        with m.If(response_writeback_valid & decoder.error & ~decoder.uncorrectable_error):
            # Do not accept a request this cycle
            m.d.comb += self.req.ready.eq(0)

            # Write the corrected value back to the memory. This does not cause a response to be created, as no request
            # is accepted from the external interface.
            m.d.comb += [
                self.sram.clk_en.eq(1),
                self.sram.addr.eq(last_req_addr),
                self.sram.write_en.eq(1),
                self.sram.write_data.eq(decoder.enc_out),
            ]

        m.d.comb += [
            self.debug.error.eq(decoder.error),
            self.debug.uncorrectable_error.eq(decoder.uncorrectable_error),
            self.debug.flips.eq(decoder.flips),
        ]
        m.d.sync += self.debug.ignore.eq(self.req.debug_ignore)

        return m
