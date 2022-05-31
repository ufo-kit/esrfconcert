""" Sample translation in x and y

    The pushers px45 and py45 to move the sample on LAMINO-I
    have an 45° angle with respect to the beamline coordinate
    system (for lamino_tilt = 0°). A coordinate transformation
    is needed for more convenient sample manipulation during
    alignment.
"""


import asyncio
import logging
import numpy as np
import time

from concert.base import Parameter, Quantity
from concert.coroutines.base import background, start
from concert.quantities import q

# Define angle between x_beamline and y_beamline
ALPHA = 90 * q.deg
# Define angle between x_pusher and y_pusher
BETA = 90 * q.deg
# Define angle between x_beamline and x_pusher
GAMMA = 135 * q.deg


async def _move_sample(
    rel_pos,
    pseudo_motor,
    sx45,
    sy45,
    px45,
    py45,
    lamino_tilt,
    offset=0 * q.deg
):
    # check if magnets are out: Sample should be only moved if magnets are in!
    if await px45.is_magnet_out() or await py45.is_magnet_out():
        raise RuntimeError('Magnets are not in')
    else:
        # get current positions
        tilt_pos = await lamino_tilt.get_position()
        sx45_pos = await sx45.get_position()
        sy45_pos = await sy45.get_position()

        # calculate target positions, x/y controlled by offset
        sx45_target = sx45_pos + rel_pos / np.cos(GAMMA - offset)
        sy45_target = sy45_pos + rel_pos / np.cos(GAMMA + BETA - offset)

        await pseudo_motor.set_position([
            tilt_pos.to(q.deg).magnitude,
            sx45_target.to(q.mm).magnitude,
            sy45_target.to(q.mm).magnitude
        ])


async def move_sample_x(
    rel_pos,
    pseudo_motor,
    sx45,
    sy45,
    px45,
    py45,
    lamino_tilt
):
    await _move_sample(rel_pos, pseudo_motor, sx45, sy45, px45, py45, lamino_tilt)


async def move_sample_y(
    rel_pos,
    pseudo_motor,
    sx45,
    sy45,
    px45,
    py45,
    lamino_tilt,
    offset=0 * q.deg
):
    await _move_sample(rel_pos, pseudo_motor, sx45, sy45, px45, py45, lamino_tilt, offset=ALPHA)


""" To Do or To Consider: 
    functions like
    - set_sample_zero_pos
    - move_to_sample_pos(x,y)
    aso. """
