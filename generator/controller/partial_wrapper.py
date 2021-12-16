from typing import List

from nmigen import *

from generator.controller.record import MemoryRequestWithPartialRecord, MemoryResponseRecord, MemoryRequestRecord


class PartialWriteWrapper(Elaboratable):
    """
    Wrapper which will translate non-word write operations to a pair of read and write operations.

    This wrapper will translate byte and halfword write operations to a full word read and write operation. This is
    required with the error correcting memory controllers as they only accept full word operations. This is a limitation
    of error correction as it does not allow partial updates, without recalculating all the error correction data.

    The implementation uses a small state machine to first translate a write request to a read request. After this it
    will wait for the response to the read, and craft a new write operation with the correct bytes replaced with new
    data. This write request is then sent to the memory controller again. The response to this write request will be
    returned as a response to the original write request.
    """
    def __init__(self, addr_width: int, data_bits: int):
        self.addr_width = addr_width
        self.data_bits = data_bits

        self.req_in = MemoryRequestWithPartialRecord(addr_width, data_bits, granularity=8)
        self.rsp_out = MemoryResponseRecord(data_bits)

        self.req_out = MemoryRequestRecord(addr_width, data_bits)
        self.rsp_in = MemoryResponseRecord(data_bits)

    def elaborate(self, platform):
        m = Module()

        # Connect the request and response busses
        m.d.comb += [
            self.req_in.connect(self.req_out, exclude=["write_mask"]),
            self.rsp_in.connect(self.rsp_out),
        ]

        tmp_req_addr = Signal(unsigned(self.addr_width))
        tmp_req_data = Signal(unsigned(self.data_bits))
        tmp_req_mask = Signal(unsigned(self.data_bits // 8))

        with m.FSM():
            with m.State("IDLE"):
                # If the current request has write enabled and a partial mask
                with m.If(self.req_in.write_en & (~self.req_in.write_mask.all())):
                    # Mark the output request as read
                    m.d.comb += self.req_out.write_en.eq(0),

                    # Once the request is accepted move to the other state
                    with m.If(self.req_in.valid & self.req_in.ready):
                        m.d.sync += [
                            tmp_req_addr.eq(self.req_in.addr),
                            tmp_req_data.eq(self.req_in.write_data),
                            tmp_req_mask.eq(self.req_in.write_mask),
                        ]
                        m.next = "WAIT_RSP"
            with m.State("WAIT_RSP"):
                # Mark the request input as busy and the request output as invalid
                m.d.comb += [
                    self.req_in.ready.eq(0),
                    self.req_out.valid.eq(0),
                ]

                # Mark the response input as ready, and the response output as invalid
                m.d.comb += [
                    self.rsp_in.ready.eq(1),
                    self.rsp_out.valid.eq(0),
                ]

                write_data = Signal(unsigned(self.data_bits))
                # Save the required bytes from the response
                for i in range(self.data_bits // 8):
                    with m.If(tmp_req_mask[i]):
                        m.d.comb += write_data.word_select(i, 8).eq(tmp_req_data.word_select(i, 8))
                    with m.Else():
                        m.d.comb += write_data.word_select(i, 8).eq(self.rsp_in.read_data.word_select(i, 8))

                # Override the request output with a write request
                m.d.comb += [
                    self.req_out.addr.eq(tmp_req_addr),
                    self.req_out.write_en.eq(1),
                    self.req_out.write_data.eq(write_data),
                ]

                # Wait until a valid response is presented
                with m.If(self.rsp_in.valid):
                    m.d.comb += self.req_out.valid.eq(1)

                    # Check if the request was directly accepted
                    with m.If(self.req_out.ready):
                        # Move to state 0
                        m.next = "IDLE"
                    with m.Else():
                        # Otherwise save the write data and move to state 2
                        m.d.sync += tmp_req_data.eq(write_data)
                        m.next = "WAIT_REQ"
            with m.State("WAIT_REQ"):
                # Mark the request input as busy
                m.d.comb += self.req_in.ready.eq(0)

                # Output a write request
                m.d.comb += [
                    self.req_out.valid.eq(1),
                    self.req_out.addr.eq(tmp_req_addr),
                    self.req_out.write_en.eq(1),
                    self.req_out.write_data.eq(tmp_req_data),
                ]

                # Wait until the write request is accepted
                with m.If(self.req_out.ready):
                    m.next = "IDLE"

        return m

    def ports(self) -> List[Signal]:
        return [*self.req_in.ports(), *self.rsp_out.ports(), *self.req_out.ports(), *self.rsp_in.ports()]
