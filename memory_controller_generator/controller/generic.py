from typing import List

from amaranth import *

from .record import MemoryRequestRecord, MemoryResponseRecord, SRAMInterfaceRecord
from ..error_correction import GenericCode


class GenericController(Elaboratable):
    """
    Generic base class that can be used by all memory controllers.

    Using this base class enforces that all memory controllers will have the same request and response interface,
    and that the SRAM is connected in the same way.
    """

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
