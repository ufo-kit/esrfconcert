# TODO: do we still need this?
"""Micos motors from ANKA laminograph at ID19 at ESRF."""

import asyncio
from concert.base import StateError, Quantity
from concert.devices.motors import base
from concert.quantities import q
from esrfconcert.networking.micos import SocketConnection


class _Base(object):

    """Base for all Micos motors on the laminograph at ID19. Motor *name* is used for communication
    with the controller.  *host* and *port* are connection details.
    """

    def __init__(self, controller, index, host, port):
        self._controller = controller
        self._index = index
        self._connection = SocketConnection(host, port)

    async def _get_position_in_steps(self):
        pos = await self._connection.execute('{} Crds ?'.format(self._controller))
        split = pos.split('{} Crds '.format(self._controller))[1].split()

        return float(split[self._index])

    async def _set_position_in_steps(self, position):
        msg = await self._connection.execute('{} AxisAbs {} {}'.format(self._controller,
                                                                 self._index + 1, position))
        if 'Movement not possible due to soft limits' in msg:
            raise StateError('You cannot move beyond soft limits')

        await self['state'].wait('standby', sleep_time=self._connection.sleep_between)

    async def _get_acceleration_unitless(self):
        acceleration = await self._connection.execute('{} Accel ?'.format(self._controller))
        split = acceleration.split('{} Accel '.format(self._controller))[1].split()

        return float(split[self._index])

    async def _set_acceleration_unitless(self, acceleration):
        await self._connection.send('{} Accel {} {}'.format(self._controller, self._index + 1,
                                                            acceleration))

    async def _get_velocity_in_steps(self):
        speed = await self._connection.execute('{} Speed ?'.format(self._controller))
        split = speed.split('{} Speed '.format(self._controller))[1].split()

        return float(split[self._index])

    async def _set_velocity_in_steps(self, velocity):
        await self._connection.send('{} Speed {} {}'.format(self._controller, self._index + 1,
                                                            velocity))

    async def _home(self):
        await self._connection.execute('{} Calibrate {}'.format(self._controller, self._index + 1))
        await self['state'].wait('standby', sleep_time=self._connection.sleep_between)

    async def _stop(self):
        await self._connection.send('{} Stop'.format(self._controller))
        await self['state'].wait('standby', sleep_time=self._connection.sleep_between)

    async def get_state(self):
        """Return the motor state."""
        # TODO: the controller provides information on the state of all motor, i.e. if one motor is
        # moving this function returns True also for all other controller motors.
        state = await self._connection.execute('{} IsReady'.format(self._controller))

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


class RotationMotor(base.RotationMotor, _Base):

    """A rotation motor implementation."""

    acceleration = Quantity(q.deg / q.s ** 2)

    def __init__(self, controller, index, host, port):
        super(RotationMotor, self).__init__()
        _Base.__init__(self, controller, index, host, port)

    async def _get_position(self):
        position = await self._get_position_in_steps()

        return position * q.deg

    async def _set_position(self, position):
        position = position.to(q.deg).magnitude
        await self._set_position_in_steps(position)

    async def _get_acceleration(self):
        return await self._get_acceleration_unitless() * q.deg / q.s ** 2

    async def _set_acceleration(self, acceleration):
        acceleration = acceleration.to(q.deg / q.s ** 2).magnitude
        await self._set_acceleration_unitless(acceleration)

    async def _get_state(self):
        return await _Base.get_state(self)

    async def _home(self):
        await _Base._home(self)

    async def _stop(self):
        await _Base._stop(self)

class ContinuousRotationMotor(RotationMotor, base.ContinuousRotationMotor):

    """A continuous rotation motor implementation."""

    async def _get_velocity(self):
        velocity = await self._get_velocity_in_steps()

        return velocity * q.deg / q.s

    async def _set_velocity(self, velocity):
        velocity = velocity.to(q.deg / q.s).magnitude
        await self._set_velocity_in_steps(velocity)

    async def _home(self):
        await self._connection.execute('{} RefMove {}'.format(self._controller, self._index + 1))
        await self['state'].wait('standby', sleep_time=self._connection.sleep_between)
