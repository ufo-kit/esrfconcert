# TODO: do we still need this?
"""Micos motors from ANKA laminograph at ID19 at ESRF."""

import asyncio
from concert.base import StateError, Quantity
from concert.devices.motors import base
from concert.quantities import q

from bliss.shell.standard import umv, mv, umvr, mvr

class _Base(object):

    """Base for all motors included via Bliss on the laminograph at ID19. *Device* is the Tango object
    used for communication and should be named identically to the name given to the motor in the ID19 
    beamline configuration.
    """

    def __init__(self, device):
        self._device = device

    async def _get_position(self):
        pos = await self._device.position
        return pos

    async def _set_position(self, position):
        mv(self._device, position)

    async def _get_acceleration(self):
        acceleration = await self._device.acceleration * ( q.mm / q.s ** 2 )

        return acceleration

    async def _set_acceleration_unitless(self, acceleration):
        accelerationIn = acceleration.to(q.mm / q.s ** 2).magnitude
        await self._device.acceleration = accelerationIn

    async def _get_velocity(self):
        speed = await self._device.velocity * ( q.mm / q.s )

        return speed

    async def _set_velocity_in_steps(self, velocity):
        velocityIn = velocity.to(q.mm / q.s ** 2).magnitude
        await self._device.velocity = velocityIn

    async def _home(self):
        raise AccessorNotImplementedError

    async def _stop(self):
        await self._device.stop()

    async def get_state(self):
        """Return the motor state."""
        # .state in Bliss returns a bliss.common.axis.AxisState object, necessary to convert it to string?
        msg = await self._device.state

        if state == '{} not ready'.format(self._controller):
            return 'moving'
        else:
            return 'standby'
        # TODO: hard limit?


class LinearMotor(base.LinearMotor, _Base):

    """A linear motor implementation."""

    acceleration = Quantity(q.mm / q.s ** 2)

    def __init__(self, controller, index, host, port):
        super(LinearMotor, self).__init__()
        _Base.__init__(self, controller, index, host, port)

    async def _get_position(self):
        return await self._get_position_in_steps() * q.mm

    async def _set_position(self, position):
        position = position.to(q.mm).magnitude
        await self._set_position_in_steps(position)

    async def _get_acceleration(self):
        return await self._get_acceleration_unitless() * q.mm / q.s ** 2

    async def _set_acceleration(self, acceleration):
        acceleration = acceleration.to(q.mm / q.s ** 2).magnitude
        await self._set_acceleration_unitless(acceleration)

    async def _get_state(self):
        return await _Base.get_state(self)

    async def _home(self):
        await _Base._home(self)

    async def _stop(self):
        await _Base._stop(self)


class ContinuousLinearMotor(LinearMotor, base.ContinuousLinearMotor):

    """A continuous linear motor implementation."""

    async def _get_velocity(self):
        velocity = await self._get_velocity_in_steps()

        return velocity * q.mm / q.s

    async def _set_velocity(self, velocity):
        velocity = velocity.to(q.mm / q.s).magnitude
        await self._set_velocity_in_steps(velocity)