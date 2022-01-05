from typing import List

from amaranth import *

from .record import MemoryResponseRecord, MemoryRequestRecord


class RefreshWrapper(Elaboratable):
    """
    Automatic memory refresh wrapper implementation.

    This wrapper will automatically insert a read request every n cycles for incrementing memory addresses. The
    response of to this read request will be caught by the wrapper and ignored. When combined with the
    `WriteBackController` this will cause memory locations with errors to be corrected automatically. Without this
    controller the read requests might not actually do anything.

    To simplify the use of this wrapper, a controller implementation `RefreshController` exists which combines the
    `WriteBackController` with this `RefreshWrapper` to create a complete controller.

    By setting `force_refresh` the controller will forcefully do a refresh when the counter rolls over. Otherwise it
    will wait for the first cycle where there is no incomming request. While this is generally nicer, since it tries
    to avoid contention on the bus. However, in some cases the bus might be so busy that there is no time for refresh
    operations. In that case you might want to enable `force_refresh`.

    The options `address_and`, `address_or` and `address_sext` allow for manipulations of the generated refresh
    address. The address counter will first be and-ed with `address_and`, then or-ed with `address_or`. Finally the
    `address_sext` option allows for sign extending a part of the generated address. All one bits in the
    `address_sext` option result in replacing that address bit with the highest non set bit. By setting the upper `n`
    bits, the refresh address will only target a low and a high part of the memory. The combination of these options
    allows for some flexibility in which areas of the memory are actually refreshed.
    """

    def __init__(self, addr_width: int, data_bits: int, refresh_counter_width: int, force_refresh=False, address_and=-1,
                 address_or=0, address_sext=0):
        self.addr_width = addr_width
        self.data_bits = data_bits
        self.refresh_counter_width = refresh_counter_width
        self.force_refresh = force_refresh
        self.address_and = address_and
        self.address_or = address_or
        self.address_sext = address_sext

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

        # Create an automatically incrementing counter to periodically refresh
        counter = Signal(unsigned(self.refresh_counter_width))
        m.d.sync += counter.eq(counter + 1)

        # Set refresh pending when the counter reaches the maximum value
        refresh_pending = Signal()
        with m.If(counter.all()):
            m.d.sync += refresh_pending.eq(1)

        # Keep track of the current refresh address
        current_address = Signal(unsigned(self.addr_width))

        # High when a refresh request has been sent and it is waiting for a response
        waiting_for_response = Signal()

        with m.If(~waiting_for_response):
            with m.If(refresh_pending & (self.force_refresh | ~self.req_in.valid)):
                if self.force_refresh:
                    # Block any incomming requests
                    m.d.comb += self.req_in.ready.eq(0)

                # Apply a read request with the refresh address
                calc_address = Signal(unsigned(self.addr_width))
                m.d.comb += calc_address.eq((current_address & self.address_and) | self.address_or)
                for i in range(self.addr_width):
                    with m.If(self.address_sext & (1 << i)):
                        m.d.comb += calc_address[i].eq(calc_address[i - 1])

                m.d.comb += [
                    self.req_out.valid.eq(1),
                    self.req_out.addr.eq(calc_address),
                    self.req_out.write_en.eq(0),
                ]

                # Wait until the request is accepted
                with m.If(self.req_out.ready):
                    # Increment the current address and start waiting for a response
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
