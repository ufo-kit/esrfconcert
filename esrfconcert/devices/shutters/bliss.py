"""Bliss shutter."""
from concert.devices.shutters import base


class Shutter(base.Shutter):

    """A Bliss shutter implementation."""

    async def __ainit__(self, device):
        await super().__ainit__()
        self._device = device

    async def _open(self):
        self._device.open()

    async def _close(self):
        self._device.close()

    async def _get_state(self):
        return self._device.state.name.lower()
