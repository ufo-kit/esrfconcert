"""Bliss shutter."""
from concert.base import transition
from concert.devices.shutters import base


class Shutter(base.Shutter):

    """A dummy shutter that can be opened and closed."""

    def __init__(self, name):
        super(Shutter, self).__init__()
        self._name = name

    async def _open(self):
        self.open()

    async def _close(self):
        self.close()

    async def _get_state(self):
        state = self.state_string()
        # .state_string() returns either "OPEN", "CLOSED", or "UNKNOWN"
        
        if state == "UNKNOWN":
            print('Shutter {} is in unknown state'.format(self.name))
        else:
            print('Shutter {} is {}'.format(self.name, state))
