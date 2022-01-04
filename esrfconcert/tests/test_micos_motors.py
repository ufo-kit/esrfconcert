"""Test Tango motors."""
from unittest import TestCase
from esrfconcert.devices.motors.micos import (
    LinearMotor,
    RotationMotor,
    ContinuousLinearMotor,
    ContinuousRotationMotor,
)


MICOS_HOST = '160.103.39.110'
MICOS_PORT = 6542


class TestLinearMotor(TestCase):

    """Simple sanity tests."""

    def setUp(self):
        self.motor = LinearMotor('foo', 1234, MICOS_HOST, MICOS_PORT)

    def test_set_position(self):
        position = 1 * q.mm
        self.motor.position = position
        self.assertEqual(position, self.motor.position)
