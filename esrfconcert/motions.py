""" Sample translation in x and y

    The pushers px45 and py45 to move the sample on LAMINO-I
    have an 45° angle with respect to the beamline coordinate
    system (for lamino_tilt = 0°). A coordinate transformation
    is needed for more convenient sample manipulation during
    alignment.
"""


import asyncio
import numpy as np

from concert.quantities import q

# Define angle between x_beamline and y_beamline
ALPHA = 90 * q.deg
# Define angle between x_pusher and y_pusher
BETA = 90 * q.deg
# Define angle between x_beamline and x_pusher
GAMMA = 135 * q.deg


async def move_sample_x(distance, rmx, rmy):

    dist_x45push = distance / np.cos(GAMMA)
    dist_y45push = distance / np.cos(GAMMA + BETA)

    await asyncio.gather(rmx.move(dist_x45push), rmy.move(dist_y45push))


async def move_sample_y(distance, rmx, rmy):

    dist_x45push = distance / np.cos(GAMMA - ALPHA)
    dist_y45push = distance / np.cos(GAMMA + BETA - ALPHA)

    await asyncio.gather(rmx.move(dist_x45push), rmy.move(dist_y45push))


""" To Do or To Consider:
    functions like
    - set_sample_zero_pos
    - move_to_sample_pos(x,y)
    aso. """
