""" Laminography experiments.

    Note: In contrast to regular radiography/tomography implementations
    where the object name "scanning_motor" is self-explanatory, here the term
    "scanning_motor" will be used to define the motor, that is moving during a
    scan. This is done to avoid confusion of the motor performing the laminographic
    tilt with the rotational motor changing the view direction.
"""
import asyncio
import logging
import time

from concert.base import Parameter, Quantity
from concert.coroutines.base import background, start
from concert.quantities import q
from concert.experiments.base import Acquisition, Experiment
from concert.experiments.synchrotron import SteppedTomography, ContinuousTomography


LOG = logging.getLogger(__name__)


class SteppedLaminography(SteppedTomography):
    """
    Stepped laminography
    """
    async def __ainit__(self, walker, flat_motor, scanning_motor, radio_position, flat_position, camera,
                 shutter, num_flats=51, num_darks=50, num_projections=3600, 
                 angular_range=360 * q.deg, start_angle=0 * q.deg, seperate_scans=True):
        
        await SteppedTomography.__ainit__(self)

    async def _take_radios(self):
        try:
            await self._prepare_radios()
            await self._camera.set_trigger_source("SOFTWARE")
            async with self._camera.recording():
                for i in range(await self.get_num_projections()):
                    await self._tomography_motor.set_position(
                            i * await self.get_angular_range() / await self.get_num_projections() +
                            await self.get_start_angle()
                        )
                    try:
                        await self._camera.trigger()
                    except:
                        pass
                    yield await self._camera.grab()
        finally:
            await self._finish_radios()


class ContinuousLaminography(ContinuousTomography):
    """
    Continuous laminography
    """
    velocity = Quantity(q.deg / q.s)

    async def __ainit__(self, walker, flat_motor, scanning_motor, shutter, radio_position, flat_position, camera,
                 num_flats=51, num_darks=50, num_projections=3600, angular_range=360 * q.deg, start_angle=0 * q.deg,
                 separate_scans=True):
        await ContinuousTomography.__ainit__(
            self,
            walker=walker,
            flat_motor=flat_motor,
            tomography_motor=scanning_motor,
            shutter=shutter,
            radio_position=radio_position,
            flat_position=flat_position,
            camera=camera,
            num_flats=num_flats,
            num_darks=num_darks,
            num_projections=num_projections,
            angular_range=angular_range,
            start_angle=start_angle,
            separate_scans=separate_scans
        )
        self['radio_position']._parameter.unit = q.deg
        self['flat_position']._parameter.unit = q.deg

    async def _prepare_radios(self):
        if 'motion_velocity' in self._tomography_motor:
            await self._tomography_motor['motion_velocity'].stash()
        await self._camera.set_trigger_source('AUTO')
        width = await self._camera.get_roi_width()
        height = await self._camera.get_roi_height()
        bpp = await self._camera.get_sensor_bitdepth() // 8
        # lid193 has 48 GB memory, let's use maximum 40
        max_buffered_images = int(40 * 2 ** 30 / (width * height * bpp))
        await self._camera.set_num_buffers(min(2 * self._num_projections, max_buffered_images))
        await self._camera.set_buffered(True)
        LOG.info('Setting num_buffers to %s', await self._camera.get_num_buffers())

        await self._flat_motor.set_position(await self.get_radio_position())
        await self._tomography_motor.set_velocity(25 * q.deg / q.s)
        await self._tomography_motor.set_position(await self.get_start_angle())

    async def _finish_radios(self):
        if self._finished:
            return
        await self._prepare_darks()
        if await self._tomography_motor.get_state() == 'moving':
            await self._tomography_motor.stop()
        if 'motion_velocity' in self._tomography_motor:
            await self._tomography_motor['motion_velocity'].restore()
        await self._tomography_motor.set_position(await self.get_start_angle())
        self._finished = True

    async def _take_radios(self):
        rot_velocity = await self.get_velocity()
        margin_time = rot_velocity / await self._tomography_motor.get_acceleration()
        # TODO: make this a parameter
        additional_margin = 0.5 * q.deg
        margin = 0.5 * rot_velocity * margin_time + additional_margin
        end_pos = await self.get_start_angle() + await self.get_angular_range() + 2 * margin
        LOG.debug("End position: %s, additional_margin: %s, margin: %s",
                 end_pos, additional_margin, margin)
        try:
            await self._prepare_radios()
            # TODO: change this to motion_velocity
            await self._tomography_motor.set_velocity(rot_velocity)
            LOG.debug("Starting motion with scanning motor at %s",
                      await self._tomography_motor.get_position())
            motion_task = self._tomography_motor.set_position(end_pos)
            LOG.debug("Waiting %s for acceleration", margin_time)
            await asyncio.sleep(margin_time.to(q.s).magnitude)
            stop_reported = False
            async with self._camera.recording():
                LOG.debug("Camera started recording with scanning motor at %s",
                          await self._tomography_motor.get_position())
                for i in range(self._num_projections):
                    yield await self._camera.grab()
                    if not stop_reported and motion_task.done():
                        LOG.debug("Motion task done when grabbing projection %d", i)
                        stop_reported = True
                LOG.debug("Grabbing frames completed with scanning motor at %s",
                          await self._tomography_motor.get_position())
                await motion_task
                LOG.debug("Motion finished")
        finally:
            # TODO: remove after motion_velocity is implemented
            await self._tomography_motor.set_velocity(25 * q.deg / q.s)
            await self._finish_radios()
