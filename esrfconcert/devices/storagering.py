"""ESRF storage ring."""
from concert.quantities import q
from concert.devices.storagerings.base import StorageRing as BaseStorageRing


class StorageRing(Device):

    """ESRF storage ring."""

    state = State()

    def __init__(self, machinfo):
        super(StorageRing, self).__init__()
        self._machinfo = machinfo

    async def _get_current(self):
        return self._machinfo.proxy.SR_Current * q.mA

    async def _get_energy(self):
        raise AccessorNotImplementedError

    async def _get_lifetime(self):
        raise AccessorNotImplementedError

    async def _get_state(self):
        raise AccessorNotImplementedError
