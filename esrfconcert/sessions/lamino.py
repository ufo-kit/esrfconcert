"""
Online reconstruction
---------------------

Usage:
    viewer.show(reco.manager.volume[0])  # Show first slice (defined by args.region and args.center_position_z)
    reco.manager.num_received_projections  # Display how many projections have been processed

    # Optimize lamino angle (similar for other parameters, all angles are in radians in concert!)
    args.z_parameter = 'axis-angle-x'
    # e.g. search +/- 5 degrees
    args.region = [args.axis_angle_x[0] - np.deg2rad(5), args.axis_angle_x[0] + np.deg2rad(5), np.deg2rad(1)]
    # Use the middle slice
    args.z = 0
    # Re-backproject
    await reco.manager.backproject(async_generatre(reco.manager.projections))
    viewer.show(reco.manager.volume[0])

    # Go back to reconstructing slices
    args.z_parameter = 'z'
    args.region = [0.0, 1.0, 0.0] # Do not forget the decimal points!
    await reco.manager.backproject(async_generate(reco.manager.projections))
"""
from numpy import asarray_chkfinite
import asyncio
import logging
import numpy as np

import concert
from concert.quantities import q
from concert.coroutines.base import async_generate
from concert.devices.cameras.uca import Camera
from concert.devices.cameras.pco import Timestamp
from concert.ext.viewers import PyplotImageViewer
from concert.readers import TiffSequenceReader
from concert.devices.shutters.dummy import Shutter as DummyShutter
from esrfconcert.devices.shutters.bliss import Shutter as BlissShutter
from concert.devices.motors.dummy import (ContinuousLinearMotor as DummyContinuousLinearMotor,
                                          ContinuousRotationMotor as DummyContinuousRotationMotor)
from concert.experiments.addons import Consumer, ImageWriter
from concert.storage import DummyWalker, DirectoryWalker
from concert.ext.ufo import GeneralBackprojectArgs, GeneralBackprojectManager
from concert.experiments.addons import Consumer, OnlineReconstruction
from esrfconcert.experiments.laminography import ContinuousLaminography
from esrfconcert.devices.motors.micos import (
    ContinuousLinearMotor,
    ContinuousRotationMotor,
    LaminoScanningMotor,
    PseudoMotor,
    SampleManipulationMotor
)
from esrfconcert.devices.motors.sampletranslation import (move_sample_x, move_sample_y)
from esrfconcert.networking.micos import SocketConnection
from bliss.setup_globals import *
from bliss.common import session
from bliss.config import static
from bliss.shell import standard


LOG = logging.getLogger(__name__)


# Set parameters
# Micos Motion Server:

concert.config.PROGRESS_BAR = False
micos_connection = ('160.103.39.110', 6542)
steps_per_degree = 26222

# scanning rotation motor
# TO CHECK: INDECES CORRECT? IN ANDREI'S SCRIPT CONSTRUCTORS ARE CALLED WITH INDEX-1?!
# sample translation motors
# puscher
sx45 = SampleManipulationMotor('Sam', 0, micos_connection[0], micos_connection[1],
                               in_position=1 * q.mm, out_position=0 * q.mm)
sy45 = SampleManipulationMotor('Sam', 1, micos_connection[0], micos_connection[1],
                               in_position=1 * q.mm, out_position=0 * q.mm)
# magnets
px45 = SampleManipulationMotor('Sam', 2, micos_connection[0], micos_connection[1],
                               in_position=-0.2 * q.mm, out_position=-1.2 * q.mm)
py45 = SampleManipulationMotor('Sam', 3, micos_connection[0], micos_connection[1],
                               in_position=1 * q.mm, out_position=0 * q.mm)
# scanning rotation motor
# TO CHECK: INDECES CORRECT? IN ANDREI'S SCRIPT CONSTRUCTORS ARE CALLED WITH INDEX-1?!
lamino_rot = LaminoScanningMotor('Sam', 4, micos_connection[0], micos_connection[1], sx45, sy45)
lamino_tilt = ContinuousRotationMotor('Cont2', 0, micos_connection[0], micos_connection[1])
pseudo_motor = PseudoMotor('Cont2', micos_connection[0], micos_connection[1])


lamino_tilt['position'].upper = 30*q.deg

# Bliss beamline components

blissConfig = static.get_config()

# 'lamino' session contains:
# - motors: lmy, lmz (for microscope)
# - shutters: frontend, bsh1, bsh2
# - storage ring: machinfo
blissSessionLamino =  blissConfig.get('lamino')
blissSessionLamino.setup()

# Microscope translation motors
lmy = blissSessionLamino.env_dict['lmy']
lmz = blissSessionLamino.env_dict['lmz']

# Detector tanslation motors
cx = blissSessionLamino.env_dict['cx']
cy = blissSessionLamino.env_dict['cy']
cz = blissSessionLamino.env_dict['cz']

# frondendDevice = blissSessionLamino.env_dict['frontendDevice']
bsh1 = BlissShutter(blissSessionLamino.env_dict['bsh1'])
bsh2 = BlissShutter(blissSessionLamino.env_dict['bsh2'])
fast_shutter = BlissShutter(blissSessionLamino.env_dict['exp_shutter'])

machinfo = blissSessionLamino.env_dict['machinfo']

# 'jens' session contains:
# - virtual motors: simmot1, simmot2

blissSessionJens =  blissConfig.get('jens')
blissSessionJens.setup()

simmot1 = blissSessionJens.env_dict['simmot1']
simmot2 = blissSessionJens.env_dict['simmot2']


async def get_pusher_positions():
    pos_x = await sx45._get_position()
    pos_y = await sy45._get_position()

    return (pos_x, pos_y)


class MagnetsInException(Exception):
    pass


async def move_pushers_out():
    if await px45.get_state() != 'out':
        await px45.move_out()
    if await py45.get_state() != 'out':
        await py45.move_out()

    await sx45['position'].stash()
    await sy45['position'].stash()
    await sx45.move_out()
    await sy45.move_out()


async def move_pushers_in():
    if np.abs(lamino_rot.position.to(q.deg).magnitude > 0.1):
        raise RuntimeError("lamino_rot not in 0 deg")
    if await px45.get_state() == 'out' and await py45.get_state() == 'out':
        await sx45['position'].restore()
        await sy45['position'].restore()
        await px45.move_in()
        await py45.move_in()
    else:
        raise MagnetsInException('Magnets are still in')


async def move_magnets_out():
    await px45.move_out()
    await py45.move_out()


def get_timestamps(images=None, path=None):
    if images is None and path is None:
        raise ValueError("Only one of images or path may be not None")

    if path is not None:
        reader = TiffSequenceReader(path)
        return [Timestamp(reader.read(i)) for i in range(reader.num_images)]
    if images is not None:
        return [Timestamp(image) for image in images]


def get_timestamp_diffs(timestamps):
    times = np.array([timestamp.time for timestamp in timestamps])
    diffs = [(times[i + 1] - times[i]).total_seconds() for i in range(len(timestamps) - 1)]

    return np.array(diffs)


def are_timestamps_ok(timestamps):
    numbers = np.array([timestamp.number for timestamp in timestamps])
    return np.all(numbers[1:] - numbers[:-1] == 1)


async def set_frame_rate(fps):
    await camera.set_frame_rate(fps)
    await camera.set_exposure_time(1 / fps - 10 * q.ms)
    await camera.start_recording()
    await camera.stop_recording()
    print('FPS={}, exp={}'.format(await camera.get_frame_rate(), await camera.get_exposure_time()))


async def prepare(self):
    if await sx45.get_state() != 'out' or await sy45.get_state() != 'out':
        await move_pushers_out()
    self.log.info('Camera settings:')
    self.log.info(await camera.info_table)
    self.log.info(await sx45.info_table)
    self.log.info(await sy45.info_table)
    self.log.info(await px45.info_table)
    self.log.info(await py45.info_table)
    if await bsh1.get_state() != 'open':
        await bsh1.open()
    if await bsh2.get_state() != 'open':
        await bsh2.open()


viewer = PyplotImageViewer(show_refresh_rate=False, force=False)
walker = DirectoryWalker(
    bytes_per_file=2**40,
    #root='/mnt/multipath-shares/data/id19/laminography/2022-05-lamino-commissioning',
    root='/mnt/multipath-shares/data/visitor/blc13800/id19/',
    log=LOG,
    log_name='experiment.log'
)

# Dummy devices
dummy_walker = DummyWalker()
shutter = DummyShutter()
# flat_motor = DummyContinuousLinearMotor()
# rot_motor = DummyContinuousRotationMotor()

# Real deal
camera = Camera('net')
camera.timestamp_mode = camera.uca.enum_values.timestamp_mode.BOTH
camera.trigger_source = 'AUTO'
rot_motor = lamino_rot
flat_motor = lamino_tilt
ContinuousLaminography.prepare = prepare
ex = ContinuousLaminography (
    walker,
    flat_motor,
    rot_motor,
    fast_shutter,
    29.9 * q.deg,
    0.5 * q.deg,
    camera,
    num_projections=3701
)

ex.start_angle=-90*q.deg
ex.angular_range=370*q.deg

live_preview = Consumer(ex.acquisitions, viewer)
writer = ImageWriter(ex.acquisitions, walker)

# Online reco setup
#n = 2560
#args = GeneralBackprojectArgs([n // 2], [n // 2 + 0.5], ex.num_projections, overall_angle=2 * np.pi)
#args.absorptivity = True
#args.fix_nan_and_inf = True
#args.region = [0.0, 1.0, 1.0]
#manager = GeneralBackprojectManager(args)
#reco = OnlineReconstruction(ex, args, do_normalization=False, average_normalization=True)
