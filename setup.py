"""Installation script for ESRF Concert plugin."""
from setuptools import setup, find_packages
import esrfconcert


setup(
    name='esrfconcert',
    python_requires='>=3.7',
    version=esrfconcert.__version__,
    author='Tomas Farago',
    author_email='tomas.farago@kit.edu',
    url='http://ankagit.anka.kit.edu/concert/esrfconcert',
    description='ESRF synchrotron plugin for Concert control system',
    long_description=open('README.rst').read(),
    exclude_package_data={'': ['README.rst']},
    install_requires=['concert'],
    packages=find_packages(),
)
