from nmigen import *

from .write_back import WriteBackController
from .refresh_wrapper import RefreshWrapper
from .generic import GenericController


class RefreshController(GenericController):
    def elaborate(self, platform):
        m = Module()

        m.submodules.refresh = refresh = RefreshWrapper(self.addr_width, self.code.data_bits, refresh_counter_width=7)
        m.submodules.controller = controller = WriteBackController(self.code, self.addr_width)

        m.d.comb += [
            self.req.connect(refresh.req_in),
            refresh.req_out.connect(controller.req),
            controller.rsp.connect(refresh.rsp_in),
            refresh.rsp_out.connect(self.rsp),

            controller.sram.connect(self.sram),
        ]

        return m
