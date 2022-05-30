from numpy import asarray_chkfinite
import asyncio
import logging
import numpy as np

import concert
from concert.quantities import q
from concert.devices.cameras.uca import Camera
from concert.devices.cameras.pco import Timestamp
from concert.ext.viewers import PyplotImageViewer
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
    PusherMotor,
    MagnetMotor
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
sx45 = PusherMotor('Sam', 0, micos_connection[0], micos_connection[1])
sy45 = PusherMotor('Sam', 1, micos_connection[0], micos_connection[1])
# magnets
px45 = MagnetMotor('Sam', 2, micos_connection[0], micos_connection[1])
py45 = MagnetMotor('Sam', 3, micos_connection[0], micos_connection[1])
# scanning rotation motor
# TO CHECK: INDECES CORRECT? IN ANDREI'S SCRIPT CONSTRUCTORS ARE CALLED WITH INDEX-1?!
lamino_rot = LaminoScanningMotor('Sam', 4, micos_connection[0], micos_connection[1], sx45, sy45)
lamino_tilt = ContinuousRotationMotor('Cont2', 0, micos_connection[0], micos_connection[1])

# Camera and viewer
camera = Camera('net')
camera.timestamp_mode = camera.uca.enum_values.timestamp_mode.BOTH
viewer = PyplotImageViewer(show_refresh_rate=False, force=False)

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
    if await px45.is_magnet_out() and await py45.is_magnet_out():
        await sx45.move_pusher_out()
        await sy45.move_pusher_out()
    else:
        raise MagnetsInException('Magnets are still in')


async def move_magnets_out():
    await px45.move_magnet_out()
    await py45.move_magnet_out()


def get_timestamp_diffs(images):
    times = np.array([Timestamp(image).time for image in images])
    diffs = [(times[i + 1] - times[i]).total_seconds() for i in range(len(images) - 1)]

    return np.array(diffs)


def are_timestamps_ok(images):
    numbers = np.array([Timestamp(image).number for image in images])
    return np.all(numbers[1:] - numbers[:-1] == 1)


# Dummy devices
dummy_walker = DummyWalker()
shutter = DummyShutter()
# flat_motor = DummyContinuousLinearMotor()
# rot_motor = DummyContinuousRotationMotor()

# Real deal
walker = DirectoryWalker(
    bytes_per_file=2**40,
    root='/mnt/multipath-shares/data/id19/laminography/2022-05-lamino-commissioning',
    log=LOG,
    log_name='experiment.log'
)
rot_motor = lamino_rot
flat_motor = lamino_tilt
ex = ContinuousLaminography (
    walker,
    flat_motor,
    rot_motor,
    fast_shutter,
    1 * q.deg,
    0.5 * q.deg,
    camera,
    num_projections=360
)
live_preview = Consumer(ex.acquisitions, viewer)
writer = ImageWriter(ex.acquisitions, walker)

# Online reco setup
n = 2560
args = GeneralBackprojectArgs([n // 2], [n // 2 + 0.5], ex.num_projections, overall_angle=2 * np.pi)
args.absorptivity = True
args.fix_nan_and_inf = True
args.region = [0.0, 1.0, 1.0]
manager = GeneralBackprojectManager(args)
reco = OnlineReconstruction(ex, args, do_normalization=False, average_normalization=True)
