import concert
from concert.quantities import q
from concert.devices.cameras.uca import Camera
from concert.ext.viewers import PyplotImageViewer
from concert.devices.shutters.dummy import Shutter as DummyShutter
from concert.devices.motors.dummy import (ContinuousLinearMotor as DummyContinuousLinearMotor,
                                          ContinuousRotationMotor as DummyContinuousRotationMotor)
from concert.experiments.addons import Consumer, ImageWriter
from concert.storage import DummyWalker
from esrfconcert.experiments.laminography import ContinuousLaminography
from esrfconcert.devices.motors.micos import ContinuousLinearMotor, ContinuousRotationMotor
from esrfconcert.networking.micos import SocketConnection
from bliss.setup_globals import *
from bliss.common import session
from bliss.config import static
from bliss.shell import standard

# Set parameters
# Micos Motion Server:

concert.config.PROGRESS_BAR = False
micos_connection = ('160.103.39.110', 6542)
steps_per_degree = 26222

# scanning rotation motor
# TO CHECK: INDECES CORRECT? IN ANDREI'S SCRIPT CONSTRUCTORS ARE CALLED WITH INDEX-1?!
lamino_rot = ContinuousRotationMotor('Sam', 4, micos_connection[0], micos_connection[1])
lamino_tilt = ContinuousRotationMotor('Cont2', 0, micos_connection[0], micos_connection[1])
# sample translation motors
# puscher
sx45_motor = ContinuousLinearMotor('Sam', 0, micos_connection[0], micos_connection[1])
sy45_motor = ContinuousLinearMotor('Sam', 1, micos_connection[0], micos_connection[1])
# magnets
px45_motor = ContinuousLinearMotor('Sam', 2, micos_connection[0], micos_connection[1])
py45_motor = ContinuousLinearMotor('Sam', 3, micos_connection[0], micos_connection[1])

# Camera and viewer
camera = Camera('net')
viewer = PyplotImageViewer(show_refresh_rate=True, force=False)

# Bliss beamline components

blissConfig = static.get_config()

# 'lamino' session contains:
# - motors: lmy, lmz (for microscope)
# - shutters: frontend, bsh1, bsh2
# - storage ring: machinfo
blissSessionLamino =  blissConfig.get('lamino')
blissSessionLamino.setup()

lmyDevice = blissSessionLamino.env_dict['lmy']
lmzDevice = blissSessionLamino.env_dict['lmz']

# frondendDevice = blissSessionLamino.env_dict['frontendDevice']
bsh1Device = blissSessionLamino.env_dict['bsh1']
bsh2Device = blissSessionLamino.env_dict['bsh2']

machinfoDevice = blissSessionLamino.env_dict['machinfo']

# 'jens' session contains:
# - virtual motors: simmot1, simmot2

blissSessionJens =  blissConfig.get('jens')
blissSessionJens.setup()

simmot1Device = blissSessionJens.env_dict['simmot1']
simmot2Device = blissSessionJens.env_dict['simmot2']


walker = DummyWalker()
shutter = DummyShutter()
# flat_motor = DummyContinuousLinearMotor()
# rot_motor = DummyContinuousRotationMotor()
rot_motor = lamino_rot
flat_motor = lamino_tilt
ex = ContinuousLaminography (walker, flat_motor, rot_motor, shutter, 10 * q.deg, 0 * q.deg, camera)
live_preview = Consumer(ex.acquisitions, viewer)
writer = ImageWriter(ex.acquisitions, walker)
