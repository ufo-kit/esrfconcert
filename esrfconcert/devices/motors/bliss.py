"""Bliss motors implementation."""

import asyncio
import logging
from concert.base import check, Quantity
from concert.devices.motors import base
from concert.quantities import q
from bliss.shell.standard import mv


LOG = logging.getLogger(__name__)


class _Base(object):

    """Base for all motors included via Bliss on the laminograph at ID19. *Device* is the Tango object
    used for communication and should be named identically to the name given to the motor in the
    ID19 beamline configuration.
    """

    async def __ainit__(self, device):
        self._device = device
        self._velocity = 0 * self['velocity'].unit
        self['position']._external_lower_getter = self._get_lower_external_position_limit
        self['position']._external_upper_getter = self._get_upper_external_position_limit

    def _get_external_limit(self, which):
        return self._device.limits[which]

    async def _get_lower_external_position_limit(self):
        return self._get_external_limit(0)

    async def _get_upper_external_position_limit(self):
        return self._get_external_limit(1)

    async def _get_position(self):
        return self._device.position * self['position'].unit

    async def _set_position(self, position):
        mv(self._device, position.to(self['position'].unit).magnitude)

    async def _get_acceleration(self):
        return self._device.acceleration * self['acceleration'].unit

    async def _set_acceleration(self, acceleration):
        self._device.acceleration = acceleration.to(self['acceleration'].unit).magnitude

    async def _get_motion_velocity(self):
        return self._device.velocity * self['motion_velocity'].unit

    async def _set_motion_velocity(self, velocity):
        self._device.velocity = velocity.to(self['motion_velocity'].unit).magnitude

    async def _get_velocity(self):
        return self._velocity

    async def _set_velocity(self, velocity):
        self._device.jog(velocity=velocity.to(self['velocity'].unit).magnitude)
        await asyncio.sleep(self._device.jog_acctime)
        self._velocity = velocity

    async def _home(self):
        self._device.home(wait=True)

    async def _stop(self):
        self._device.stop(wait=True)
        self._velocity = 0 * self['velocity'].unit

    async def _get_state(self):
        """Return the motor state."""
        state = self._device.state

        if 'READY' in state:
            return 'standby'
        elif 'LIMNEG' in state:
            return 'hard-limit'
        elif 'LIMPOS' in state:
            return 'hard-limit'
        elif 'MOVING' in state:
            return 'moving'
        elif 'FAULT' in state:
            return 'error'
        elif 'HOME' in state:
            return 'moving'
        elif 'OFF' in state:
            return 'off'
        elif 'DISABLED' in state:
            return 'disabled'


class LinearMotor(_Base, base.LinearMotor):

    """A linear motor implementation."""

    acceleration = Quantity(q.mm / q.s ** 2)

    async def __ainit__(self, device):
        await base.LinearMotor.__ainit__(self)
        await _Base.__ainit__(self, device)


class ContinuousLinearMotor(LinearMotor, base.ContinuousLinearMotor):

    """A continuous linear motor implementation."""

    motion_velocity = Quantity(unit=q.mm / q.s,
                               help='Motion velocity constant for all motor movement ' +
                                    'types (position setting, homing, ...)',
                               check=check(source=['hard-limit', 'standby'],
                                           target=['hard-limit', 'standby']))


class RotationMotor(_Base, base.RotationMotor):

    """A linear motor implementation."""

    acceleration = Quantity(q.deg / q.s ** 2)

    async def __ainit__(self, device):
        await base.RotationMotor.__ainit__(self)
        await _Base.__ainit__(self, device)


class ContinuousRotationMotor(RotationMotor, base.ContinuousRotationMotor):

    """A continuous linear motor implementation."""

    motion_velocity = Quantity(unit=q.deg / q.s,
                               help='Motion velocity constant for all motor movement ' +
                                    'types (position setting, homing, ...)',
                               check=check(source=['hard-limit', 'standby'],
                                           target=['hard-limit', 'standby']))
