from typing import List

from nmigen import *

from generator.controller.record import MemoryRequestRecord, MemoryResponseRecord, SRAMInterfaceRecord
from generator.error_correction import GenericCode


class GenericController(Elaboratable):
    def __init__(self, code: GenericCode, addr_width: int):
        self.code = code
        self.addr_width = addr_width

        # User interface
        self.req = MemoryRequestRecord(addr_width, code.data_bits)
        self.rsp = MemoryResponseRecord(code.data_bits)

        # SRAM interface
        self.sram = SRAMInterfaceRecord(addr_width, code.total_bits)

    def ports(self) -> List[Signal]:
        return [*self.req.ports(), *self.rsp.ports(), *self.sram.ports()]
