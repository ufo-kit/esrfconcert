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
        """
        Storage ring energy not accessible via machinfo
        so it is hard-coded
        """
        return 6 * q.GeV

    async def _get_lifetime(self):
        return self._machinfo.proxy.SR_Lifetime * q.s

    async def _get_state(self):
        """
        SR_Mode returns an Integer for different states of 
        the storage ring. Indexing not clear except for
        1 = USM = USerMode --> Output: "UserOperation"
        """
        operation_state = self._machinfo.proxy.SR_Mode
        state = "unknown"
        if operation_state == 1:
            state = "UserOperation"
        elif operation_state == 2:
            state = "MachineDevelopment"
        elif operation_state == 3:
            state = "Shutdown"
        elif operation_state == 4:
            state = "SafetyTest"
        elif operation_state == 5:
            state = "InsertionDeviceTest"
        return state

