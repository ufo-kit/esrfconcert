"""Bliss shutter."""
from concert.base import transition
from concert.devices.shutters import base


class Shutter(base.Shutter):

    """A dummy shutter that can be opened and closed."""

    def __init__(self):
        super(Shutter, self).__init__()

    async def _open(self):
        raise AccessorNotImplementedError

    async def _close(self):
        raise AccessorNotImplementedError

    async def _get_state(self):
        raise AccessorNotImplementedError
