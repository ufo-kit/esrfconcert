""" Laminography experiments.

    Note: In contrast to regular radiography/tomography implementations
    where the object name "tomography_motor" is self-explanatory, here the term
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


LOG = logging.getLogger(__name__)


class Laminography(Experiment):
    num_flats = Parameter()
    num_darks = Parameter()
    num_projections = Parameter()
    radio_position = Quantity(q.deg)
    flat_position = Quantity(q.deg)

    def __init__(self, walker, flat_motor, shutter, radio_position, flat_position, camera,
                 num_flats=51, num_darks=50, num_projections=3600, separate_scans=True):
        self._num_flats = num_flats
        self._num_darks = num_darks
        self._num_projections = num_projections
        self._radio_position = radio_position
        self._flat_position = flat_position
        self._finished = None
        self._flat_motor = flat_motor
        self._shutter = shutter
        self._camera = camera
        darks_acq = Acquisition("darks", self._take_darks)
        flats_acq = Acquisition("flats", self._take_flats)
        radios_acq = Acquisition("radios", self._take_radios)
        super(Laminography, self).__init__([darks_acq, flats_acq, radios_acq], walker, separate_scans=separate_scans)

    async def _get_num_flats(self):
        return self._num_flats

    async def _get_num_darks(self):
        return self._num_darks

    async def _get_num_projections(self):
        return self._num_projections

    async def _get_radio_position(self):
        return self._radio_position

    async def _get_flat_position(self):
        return self._flat_position

    async def _set_num_flats(self, n):
        self._num_flats = int(n)

    async def _set_num_darks(self, n):
        self._num_darks = int(n)

    async def _set_num_projections(self, n):
        self._num_projections = int(n)

    async def _set_flat_position(self, position):
        self._flat_position = position

    async def _set_radio_position(self, position):
        self._radio_position = position

    async def _prepare_flats(self):
        await self._flat_motor.set_position(await self.get_flat_position())
        if await self._shutter.get_state() != "open":
            await self._shutter.open()

    async def _prepare_darks(self):
        if await self._shutter.get_state() != "closed":
            await self._shutter.close()

    async def _prepare_radios(self):
        await self._flat_motor.set_position(await self.get_radio_position())
        if await self._shutter.get_state() != "open":
            await self._shutter.open()

    async def _finish_radios(self):
        """
        Function that is called after all frames are acquired. It will be called only once.
        """
        if self._finished:
            return
        if await self._shutter.get_state() != "closed":
            await self._shutter.close()
        self._finished = True

    @background
    async def run(self):
        self._finished = False
        await super().run()

    async def _take_radios(self):
        try:
            await self._prepare_radios()
            async for frame in self._produce_frames(self._num_projections):
                yield frame
        finally:
            await self._finish_radios()

    async def _take_flats(self):
        try:
            await self._prepare_flats()
            async for frame in self._produce_frames(self._num_flats):
                yield frame
        finally:
            await self._prepare_darks()

    async def _take_darks(self):
        try:
            await self._prepare_darks()
            async for frame in self._produce_frames(self._num_darks):
                yield frame
        finally:
            await self._prepare_darks()

    async def _produce_frames(self, number, after_acquisition=None):
        """
        Generator of frames

        :param number: Number of frames that are generated
        :param after_acquisition: function that is called after all frames are acquired (but maybe not yet downloaded).
        Could be None or a Future.
        :return:
        """
        async with self._camera.recording():
            for i in range(int(number)):
                yield await self._camera.grab()
        if after_acquisition is not None:
            await after_acquisition()


class SteppedLaminography(Laminography):
    angular_range = Quantity(q.deg)
    start_angle = Quantity(q.deg)

    def __init__(self, walker, flat_motor, scanning_motor, shutter, radio_position, flat_position, camera,
                 num_flats=51, num_darks=50, num_projections=3600, angular_range=360 * q.deg, start_angle=0 * q.deg,
                 seperate_scans=True):
        self._angular_range = angular_range
        self._start_angle = start_angle
        self._scanning_motor = scanning_motor
        super(SteppedLaminography, self).__init__(walker=walker, flat_motor=flat_motor, shutter=shutter,
                                                radio_position=radio_position, flat_position=flat_position,
                                                camera=camera, num_flats=num_flats, num_darks=num_darks,
                                                num_projections=num_projections, separate_scans=seperate_scans)

    async def _get_angular_range(self):
        return self._angular_range

    async def _get_start_angle(self):
        return self._start_angle

    async def _set_angular_range(self, angle):
        self._angular_range = angle

    async def _set_start_angle(self, angle):
        self._start_angle = angle

    async def _prepare_radios(self):
        await self._scanning_motor.set_position(await self.get_start_angle())
        await super(SteppedLaminography, self)._prepare_radios()

    async def _finish_radios(self):
        if self._finished:
            return
        await self._prepare_darks()
        await self._scanning_motor.set_position(await self.get_start_angle())
        self._finished = True

    async def _take_radios(self):
        try:
            await self._prepare_radios()
            await self._camera.set_trigger_source("SOFTWARE")
            async with self._camera.recording():
                for i in range(await self.get_num_projections()):
                    await self._scanning_motor.set_position(
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


class ContinuousLaminography(SteppedLaminography):
    velocity = Quantity(q.deg / q.s)

    def __init__(self, walker, flat_motor, scanning_motor, shutter, radio_position, flat_position, camera,
                 num_flats=51, num_darks=50, num_projections=3600, angular_range=360 * q.deg, start_angle=0 * q.deg,
                 separate_scans=True):
        super(ContinuousLaminography, self).__init__(walker=walker, flat_motor=flat_motor,
                                                   scanning_motor=scanning_motor, shutter=shutter,
                                                   radio_position=radio_position, flat_position=flat_position,
                                                   camera=camera, num_flats=num_flats, num_darks=num_darks,
                                                   num_projections=num_projections, angular_range=angular_range,
                                                   start_angle=start_angle, seperate_scans=separate_scans)

    async def _get_velocity(self):
        angular_range = await self.get_angular_range()
        num_projections = await self.get_num_projections()
        fps = await self._camera.get_frame_rate()

        return fps * angular_range / num_projections

    async def _prepare_radios(self):
        await super(ContinuousLaminography, self)._prepare_radios()
        if 'motion_velocity' in self._scanning_motor:
            await self._scanning_motor['motion_velocity'].stash()
        await self._camera.set_trigger_source('AUTO')
        width = await self._camera.get_roi_width()
        height = await self._camera.get_roi_height()
        bpp = await self._camera.get_sensor_bitdepth() // 8
        # lid193 has 48 GB memory, let's use maximum 40
        max_buffered_images = int(40 * 2 ** 30 / (width * height * bpp))
        await self._camera.set_num_buffers(min(self._num_projections, max_buffered_images))
        await self._camera.set_buffered(True)
        LOG.info('Setting num_buffers to %s', await self._camera.get_num_buffers())

    async def _finish_radios(self):
        if self._finished:
            return
        await self._prepare_darks()
        if await self._scanning_motor.get_state() == 'moving':
            await self._scanning_motor.stop()
        if 'motion_velocity' in self._scanning_motor:
            await self._scanning_motor['motion_velocity'].restore()
        await self._scanning_motor.set_position(await self.get_start_angle())
        self._finished = True

    async def _take_radios(self):
        try:
            await self._prepare_radios()
            async with self._camera.recording():
                await self._scanning_motor.set_velocity(await self.get_velocity())
                for i in range(self._num_projections):
                    yield await self._camera.grab()
        finally:
            await self._finish_radios()
