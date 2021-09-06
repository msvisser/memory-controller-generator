from nmigen import Signal
from nmigen.hdl.rec import DIR_FANOUT, DIR_FANIN, Record


class MemoryRequestRecord(Record):
    """Record for memory request signals used by a controller."""

    def __init__(self, addr_width: int, data_width: int):
        super().__init__([
            ("valid", 1, DIR_FANOUT),
            ("ready", 1, DIR_FANIN),
            ("addr", addr_width, DIR_FANOUT),
            ("write_en", 1, DIR_FANOUT),
            ("write_data", data_width, DIR_FANOUT),
        ], src_loc_at=1)

    def ports(self) -> [Signal]:
        return self.fields.values()


class MemoryResponseRecord(Record):
    """Record for memory response signals used by a controller."""

    def __init__(self, data_width: int):
        super().__init__([
            ("valid", 1, DIR_FANOUT),
            ("ready", 1, DIR_FANIN),
            ("read_data", data_width, DIR_FANOUT),
            ("error", 1, DIR_FANOUT),
            ("uncorrectable_error", 1, DIR_FANOUT),
        ], src_loc_at=1)

    def ports(self) -> [Signal]:
        return self.fields.values()


class SRAMInterfaceRecord(Record):
    """Record for SRAM interface signals used by a controller"""

    def __init__(self, addr_width: int, data_width: int):
        super().__init__([
            ("clk_en", 1, DIR_FANOUT),
            ("addr", addr_width, DIR_FANOUT),
            ("write_en", 1, DIR_FANOUT),
            ("write_data", data_width, DIR_FANOUT),
            ("read_data", data_width, DIR_FANIN),
        ], src_loc_at=1)

    def ports(self) -> [Signal]:
        return self.fields.values()
