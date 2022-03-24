"""Ethernet connection to micos motors on ANKA laminograph at ID19 at ESRF."""

import logging
import asyncio
from concert.quantities import q
from concert.networking import base


LOG = logging.getLogger(__name__)


class SocketConnection(base.SocketConnection):

    """Micos-specific ethernet connection."""

    def __init__(self, host, port, sleep_between=0.1*q.s):
        super(SocketConnection, self).__init__(host, port, return_sequence='\r\n')
        self.sleep_between = sleep_between
        self._initialized = False

    async def send(self, data):
        if not self._initialized:
            LOG.debug("Flushing Micos server: %s", await self.recv())
            self._initialized = True
        await super().send(data)

    async def execute(self, data):
        """Send *data*, get and interpret the response."""
        async with self.lock:
            await self.send(data)
            await asyncio.sleep(self.sleep_between.to(q.s).magnitude)
            result = await self.recv()

        return result


class MicosConnectionError(Exception):

    """Micos motor connection exception."""

    pass
