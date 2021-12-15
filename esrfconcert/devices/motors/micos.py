# TODO: do we still need this?
"""Micos motors from ANKA laminograph at ID19 at ESRF."""

from concert.base import StateError, Quantity
from concert.devices.motors import base
from concert.quantities import q
from ankaconcert.networking.micos import SocketConnection


class _Base(object):

    """Base for all Micos motors on the laminograph at ID19. Motor *name* is used for communication
    with the controller.  *host* and *port* are connection details.
    """

    def __init__(self, controller, index, host, port):
        self._controller = controller
        self._index = index
        self._connection = SocketConnection(host, port)
        resp = self._connection.execute('{} AxisInfo'.format(self._controller, self._index))

    def _get_position_in_steps(self):
        pos = self._connection.execute('{} Crds ?'.format(self._controller))
        split = pos.split('{} Crds '.format(self._controller))[1].split()

        return float(split[self._index])

    def _set_position_in_steps(self, position):
        msg = self._connection.execute('{} AxisAbs {} {}'.format(self._controller,
                                                                 self._index + 1, position))
        if 'Movement not possible due to soft limits' in msg:
            raise StateError('You cannot move beyond soft limits')

        self['state'].wait('standby', sleep_time=self._connection.sleep_between)

    def _get_acceleration_unitless(self):
        acceleration = self._connection.execute('{} Accel ?'.format(self._controller))
        split = acceleration.split('{} Accel '.format(self._controller))[1].split()

        return float(split[self._index])

    def _set_acceleration_unitless(self, acceleration):
        self._connection.send('{} Accel {} {}'.format(self._controller, self._index + 1,
                                                         acceleration))

    def _get_velocity_in_steps(self):
        speed = self._connection.execute('{} Speed ?'.format(self._controller))
        split = speed.split('{} Speed '.format(self._controller))[1].split()

        return float(split[self._index])

    def _set_velocity_in_steps(self, velocity):
        self._connection.send('{} Speed {} {}'.format(self._controller, self._index + 1,
                                                         velocity))

    def _home(self):
        self._connection.execute('{} Calibrate {}'.format(self._controller, self._index + 1))
        self['state'].wait('standby', sleep_time=self._connection.sleep_between)

    def _stop(self):
        self._connection.send('{} Stop'.format(self._controller))

    def get_state(self):
        """Return the motor state."""
        # TODO: the controller provides information on the state of all motor, i.e. if one motor is
        # moving this function returns True also for all other controller motors.
        state = self._connection.execute('{} IsReady'.format(self._controller))

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

    def _get_position(self):
        return self._get_position_in_steps() * q.mm

    def _set_position(self, position):
        position = position.to(q.mm).magnitude
        self._set_position_in_steps(position)

    def _get_acceleration(self):
        return self._get_acceleration_unitless() * q.mm / q.s ** 2

    def _set_acceleration(self, acceleration):
        acceleration = acceleration.to(q.mm / q.s ** 2).magnitude
        self._set_acceleration_unitless(acceleration)

    def _get_state(self):
        return _Base.get_state(self)

    def _home(self):
        _Base._home(self)

    def _stop(self):
        _Base._stop(self)


class ContinuousLinearMotor(LinearMotor, base.ContinuousLinearMotor):

    """A continuous linear motor implementation."""

    def _get_velocity(self):
        velocity = self._get_velocity_in_steps()

        return velocity * q.mm / q.s

    def _set_velocity(self, velocity):
        velocity = velocity.to(q.mm / q.s).magnitude
        self._set_velocity_in_steps(velocity)


class RotationMotor(base.RotationMotor, _Base):

    """A rotation motor implementation."""

    acceleration = Quantity(q.deg / q.s ** 2)

    def __init__(self, controller, index, host, port):
        super(RotationMotor, self).__init__()
        _Base.__init__(self, controller, index, host, port)

    def _get_position(self):
        position = self._get_position_in_steps()

        return position * q.deg

    def _set_position(self, position):
        position = position.to(q.deg).magnitude
        self._set_position_in_steps(position)

    def _get_acceleration(self):
        return self._get_acceleration_unitless() * q.deg / q.s ** 2

    def _set_acceleration(self, acceleration):
        acceleration = acceleration.to(q.deg / q.s ** 2).magnitude
        self._set_acceleration_unitless(acceleration)

    def _get_state(self):
        return _Base.get_state(self)

    def _home(self):
        _Base._home(self)

    def _stop(self):
        _Base._stop(self)

class ContinuousRotationMotor(RotationMotor, base.ContinuousRotationMotor):

    """A continuous rotation motor implementation."""

    def _get_velocity(self):
        velocity = self._get_velocity_in_steps()

        return velocity * q.deg / q.s

    def _set_velocity(self, velocity):
        velocity = velocity.to(q.deg / q.s).magnitude
        self._set_velocity_in_steps(velocity)
