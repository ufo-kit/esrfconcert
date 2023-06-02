# TODO: do we still need this?
"""Micos motors from ANKA laminograph at ID19 at ESRF."""

import numpy as np
from concert.base import State, StateError, Quantity, Parameter, Parameterizable, check
from concert.coroutines.base import wait_until
from concert.devices.motors import base
from concert.quantities import q
from esrfconcert.networking.micos import SocketConnection


# Define angle between x_beamline and y_beamline
ALPHA = 90 * q.deg
# Define angle between x_pusher and y_pusher
BETA = 90 * q.deg
# Define angle between x_beamline and x_pusher
GAMMA = 135 * q.deg


class _Base(object):

    """Base for all Micos motors on the laminograph at ID19. Motor *name* is used for communication
    with the controller.  *host* and *port* are connection details.
    """

    async def __ainit__(self, controller, index, host, port):
        self._controller = controller
        self._index = index
        self._connection = SocketConnection(host, port)

    async def _get_positions_in_steps(self):
        pos = await self._connection.execute('{} Crds ?'.format(self._controller))
        split = pos.split('{} Crds '.format(self._controller))[1].split()

        return split

    async def _get_position_in_steps(self):
        split = await self._get_positions_in_steps()

        return float(split[self._index])

    async def _set_position_in_steps(self, position, wait_for='standby'):
        msg = await self._connection.execute('{} AxisAbs {} {}'.format(self._controller,
                                                                       self._index + 1, position))
        if 'Movement not possible due to soft limits' in msg:
            raise StateError('You cannot move beyond soft limits')

        await self['state'].wait(wait_for, sleep_time=self._connection.sleep_between)

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

    async def __ainit__(self, controller, index, host, port):
        await base.LinearMotor.__ainit__(self)
        await _Base.__ainit__(self, controller, index, host, port)

    async def _get_position(self):
        return await self._get_position_in_steps() * q.mm

    async def _set_position(self, position, wait_for='standby'):
        position = position.to(q.mm).magnitude
        await self._set_position_in_steps(position, wait_for=wait_for)

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


class SampleManipulationMotor(ContinuousLinearMotor):

    """An implementation specifically for pushers and magnets of LAMINO-I."""

    async def __ainit__(self, controller, index, host, port, in_position, out_position,
                        precision=0.1):
        await ContinuousLinearMotor.__ainit__(self, controller, index, host, port)
        self._in_position = in_position
        self._out_position = out_position
        self._precision = precision
        self['position']._parameter.check = check(
            source=['hard-limit', 'standby', 'in', 'out'],
            target=['hard-limit', 'standby', 'in', 'out']
        )

    async def _is_in_position(self, desired_position):
        pos = await self._get_position()

        return abs((pos - desired_position).to(q.mm).magnitude) < self._precision

    async def _set_position_in_steps(self, position, wait_for=None):
        # TODO: do this properly
        msg = await self._connection.execute('{} AxisAbs {} {}'.format(self._controller,
                                                                       self._index + 1, position))
        if 'Movement not possible due to soft limits' in msg:
            raise StateError('You cannot move beyond soft limits')

        async def condition():
            if wait_for is None:
                possible_states = ['in', 'out', 'standby']
            else:
                possible_states = [wait_for]
            return await self._get_state() in possible_states

        await wait_until(condition, sleep_time=1e-1 * q.s)

    async def _get_state(self):
        state = await super()._get_state()
        if state == 'standby':
            if await self._is_in_position(self._in_position):
                return 'in'
            elif await self._is_in_position(self._out_position):
                return 'out'

        return state

    async def _set_position(self, position, wait_for=None):
        await self._set_position_in_steps(position.to(q.mm).magnitude, wait_for=wait_for)

    async def move_in(self):
        await self._set_position(self._in_position, wait_for='in')

    async def move_out(self):
        await self._set_position(self._out_position, wait_for='out')


class RotationMotor(base.RotationMotor, _Base):

    """A rotation motor implementation."""

    acceleration = Quantity(q.deg / q.s ** 2)

    async def __ainit__(self, controller, index, host, port):
        await base.RotationMotor.__ainit__(self)
        await _Base.__ainit__(self, controller, index, host, port)

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


class LaminoScanningMotor(ContinuousRotationMotor):

    """An implementation with specific functionality for the rotary state of LAMINO-I"""

    async def __ainit__(self, controller, index, host, port, pusher1, pusher2):
        await ContinuousRotationMotor.__ainit__(self, controller, index, host, port)
        self.pusher1 = pusher1
        self.pusher2 = pusher2

    async def _set_position(self, position):
        if await self.pusher1.get_state() == 'out' and await self.pusher2.get_state() == 'out':
            position = position.to(q.deg).magnitude
            await self._set_position_in_steps(position)
        else:
            raise LaminoRotException('Pushers are not out')


class PseudoMotor(Parameterizable, _Base):

    position = Parameter(help='Position vector for several axes')
    state = State(default='standby')

    async def __ainit__(self, controller, host, port):
        await _Base.__ainit__(self, controller, None, host, port)
        await Parameterizable.__ainit__(self)

    async def _set_position(self, positions):
        str_positions = ' '.join([str(pos) for pos in positions])
        msg = await self._connection.execute(
            '{} MoveAbs {}'.format(self._controller, str_positions)
        )

        if 'Movement not possible due to soft limits' in msg:
            raise StateError('You cannot move beyond soft limits')

        await self['state'].wait('standby', sleep_time=self._connection.sleep_between)

    async def _get_position(self):
        str_positions = await self._get_positions_in_steps()

        return [float(pos) for pos in str_positions]

    async def _get_state(self):
        return await _Base.get_state(self)


class SampleMotor(PseudoMotor):

    async def __ainit__(self, controller, host, port, sx45, sy45, px45, py45, lamino_tilt):
        await PseudoMotor.__ainit__(self, controller, host, port)
        self.sx45 = sx45
        self.sy45 = sy45
        self.px45 = px45
        self.py45 = py45
        self.lamino_tilt = lamino_tilt

    async def move_x(self, rel_pos):
        return await self._move(rel_pos)

    async def move_y(self, rel_pos):
        return await self._move(rel_pos, offset=ALPHA)

    async def _move(self, rel_pos, offset=0 * q.deg):
        # check if magnets are out: Sample should be only moved if magnets are in!
        if await self.px45.get_state() != 'in' and await self.py45.get_state() != 'in':
            raise RuntimeError('Magnets are not in')
        else:
            # get current positions
            tilt_pos = await self.lamino_tilt.get_position()
            sx45_pos = await self.sx45.get_position()
            sy45_pos = await self.sy45.get_position()

            # calculate target positions, x/y controlled by offset
            sx45_target = sx45_pos + rel_pos / np.cos(GAMMA - offset)
            sy45_target = sy45_pos + rel_pos / np.cos(GAMMA + BETA - offset)

            await self.set_position([
                tilt_pos.to(q.deg).magnitude,
                sx45_target.to(q.mm).magnitude,
                sy45_target.to(q.mm).magnitude
            ])


class LaminoRotException(Exception):
    pass
