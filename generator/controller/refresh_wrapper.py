from typing import List

from nmigen import *

from generator.controller.record import MemoryResponseRecord, MemoryRequestRecord


class RefreshWrapper(Elaboratable):
    def __init__(self, addr_width: int, data_bits: int, refresh_counter_width: int):
        self.addr_width = addr_width
        self.data_bits = data_bits
        self.refresh_counter_width = refresh_counter_width

        self.req_in = MemoryRequestRecord(addr_width, data_bits)
        self.rsp_out = MemoryResponseRecord(data_bits)

        self.req_out = MemoryRequestRecord(addr_width, data_bits)
        self.rsp_in = MemoryResponseRecord(data_bits)

    def elaborate(self, platform):
        m = Module()

        # Connect the request and response busses
        m.d.comb += [
            self.req_in.connect(self.req_out),
            self.rsp_in.connect(self.rsp_out),
        ]

        counter = Signal(unsigned(self.refresh_counter_width))
        m.d.sync += counter.eq(counter + 1)

        refresh_pending = Signal()
        with m.If(counter.all()):
            m.d.sync += refresh_pending.eq(1)

        current_address = Signal(unsigned(self.addr_width))

        waiting_for_response = Signal()

        with m.If(~waiting_for_response):
            with m.If(refresh_pending):
                m.d.comb += [
                    self.req_in.ready.eq(0),

                    self.req_out.valid.eq(1),
                    self.req_out.addr.eq(current_address),
                    self.req_out.write_en.eq(0),
                ]

                with m.If(self.req_out.ready):
                    m.d.sync += [
                        refresh_pending.eq(0),
                        current_address.eq(current_address + 1),
                        waiting_for_response.eq(1),
                    ]
        with m.Else():
            # Mark the response input as ready, and the response output as invalid
            m.d.comb += [
                self.rsp_in.ready.eq(1),
                self.rsp_out.valid.eq(0),
            ]

            # Wait until a valid response is presented
            with m.If(self.rsp_in.valid):
                m.d.sync += waiting_for_response.eq(0)

        return m

    def ports(self) -> List[Signal]:
        return [*self.req_in.ports(), *self.rsp_out.ports(), *self.req_out.ports(), *self.rsp_in.ports()]
