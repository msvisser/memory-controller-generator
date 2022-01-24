from amaranth import *

from .generic import GenericController
from .refresh_wrapper import RefreshWrapper
from .write_back import WriteBackController


class RefreshController(GenericController):
    """
    Implementation of an automatically refreshing memory controller.

    This implementation combines the `WriteBackController` with a `RefreshWrapper` to produce a controller which will
    periodically refresh memory locations.

    For details on the implementation of the refresh mechanism see the `RefreshWrapper` implementation.
    """

    def elaborate(self, platform):
        m = Module()

        # Create `RefreshWrapper` and `WriteBackController`
        m.submodules.refresh = refresh = RefreshWrapper(self.addr_width, self.code.data_bits, refresh_counter_width=7)
        m.submodules.controller = controller = WriteBackController(self.code, self.addr_width)

        # Connect the refresh wrapper and controller to the external signals
        m.d.comb += [
            self.req.connect(refresh.req_in),
            refresh.req_out.connect(controller.req),
            controller.rsp.connect(refresh.rsp_in),
            refresh.rsp_out.connect(self.rsp),

            controller.sram.connect(self.sram),

            self.debug.eq(controller.debug),
        ]

        return m


class ForceRefreshController(GenericController):
    """
    Implementation of an automatically refreshing memory controller with ``force_refresh=True``.

    This implementation combines the `WriteBackController` with a `RefreshWrapper` to produce a controller which will
    periodically refresh memory locations.

    For details on the implementation of the refresh mechanism see the `RefreshWrapper` implementation.
    """

    def elaborate(self, platform):
        m = Module()

        # Create `RefreshWrapper` and `WriteBackController`
        m.submodules.refresh = refresh = RefreshWrapper(self.addr_width, self.code.data_bits, refresh_counter_width=7,
                                                        force_refresh=True)
        m.submodules.controller = controller = WriteBackController(self.code, self.addr_width)

        # Connect the refresh wrapper and controller to the external signals
        m.d.comb += [
            self.req.connect(refresh.req_in),
            refresh.req_out.connect(controller.req),
            controller.rsp.connect(refresh.rsp_in),
            refresh.rsp_out.connect(self.rsp),

            controller.sram.connect(self.sram),

            self.debug.eq(controller.debug),
        ]

        return m


class ContinuousRefreshController(GenericController):
    """
    Implementation of an automatically refreshing memory controller with ``refresh_counter_width=0``.

    This implementation combines the `WriteBackController` with a `RefreshWrapper` to produce a controller which will
    periodically refresh memory locations.

    For details on the implementation of the refresh mechanism see the `RefreshWrapper` implementation.
    """

    def elaborate(self, platform):
        m = Module()

        # Create `RefreshWrapper` and `WriteBackController`
        m.submodules.refresh = refresh = RefreshWrapper(self.addr_width, self.code.data_bits, refresh_counter_width=0)
        m.submodules.controller = controller = WriteBackController(self.code, self.addr_width)

        # Connect the refresh wrapper and controller to the external signals
        m.d.comb += [
            self.req.connect(refresh.req_in),
            refresh.req_out.connect(controller.req),
            controller.rsp.connect(refresh.rsp_in),
            refresh.rsp_out.connect(self.rsp),

            controller.sram.connect(self.sram),

            self.debug.eq(controller.debug),
        ]

        return m


class TopRefreshController(GenericController):
    """
    Implementation of an automatically refreshing memory controller which only refreshes the top 128 words.

    This implementation combines the `WriteBackController` with a `RefreshWrapper` to produce a controller which will
    periodically refresh memory locations.

    For details on the implementation of the refresh mechanism see the `RefreshWrapper` implementation.
    """

    def elaborate(self, platform):
        m = Module()

        # Create `RefreshWrapper` and `WriteBackController`
        top_range = 7
        mask = ((1 << (self.addr_width - top_range)) - 1) << top_range
        m.submodules.refresh = refresh = RefreshWrapper(self.addr_width, self.code.data_bits, refresh_counter_width=7,
                                                        address_or=mask)
        m.submodules.controller = controller = WriteBackController(self.code, self.addr_width)

        # Connect the refresh wrapper and controller to the external signals
        m.d.comb += [
            self.req.connect(refresh.req_in),
            refresh.req_out.connect(controller.req),
            controller.rsp.connect(refresh.rsp_in),
            refresh.rsp_out.connect(self.rsp),

            controller.sram.connect(self.sram),

            self.debug.eq(controller.debug),
        ]

        return m


class TopBottomRefreshController(GenericController):
    """
    Implementation of an automatically refreshing memory controller which only refreshes the top and bottom 64 words.

    This implementation combines the `WriteBackController` with a `RefreshWrapper` to produce a controller which will
    periodically refresh memory locations.

    For details on the implementation of the refresh mechanism see the `RefreshWrapper` implementation.
    """

    def elaborate(self, platform):
        m = Module()

        # Create `RefreshWrapper` and `WriteBackController`
        top_range = 7
        mask = ((1 << (self.addr_width - top_range)) - 1) << top_range
        m.submodules.refresh = refresh = RefreshWrapper(self.addr_width, self.code.data_bits, refresh_counter_width=7,
                                                        address_sext=mask)
        m.submodules.controller = controller = WriteBackController(self.code, self.addr_width)

        # Connect the refresh wrapper and controller to the external signals
        m.d.comb += [
            self.req.connect(refresh.req_in),
            refresh.req_out.connect(controller.req),
            controller.rsp.connect(refresh.rsp_in),
            refresh.rsp_out.connect(self.rsp),

            controller.sram.connect(self.sram),

            self.debug.eq(controller.debug),
        ]

        return m
