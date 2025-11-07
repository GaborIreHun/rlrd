from setuptools import setup
from setuptools import find_packages
from os.path import join, dirname
import sys

if sys.version_info < (3, 7):
    sys.exit('Sorry, Python < 3.7 is not supported. We use dataclasses that have been introduced in 3.7.')

setup(
    name='rlrd',
    version="0.1",
    description='',
    author='Yann Bouteiller and Simon Ramstedt',
    author_email='simonramstedt@gmail.com',
    download_url='',
    license='MIT',
    install_requires=[
        "pandas>=1.5.3,<2.1",
        "gym==0.19.0",
        "cloudpickle==1.6.0",
        "numpy==1.24.4",
        "scipy==1.10.1",
        "torch==2.2.2",
        "matplotlib==3.7.1",
        'imageio',
        'imageio-ffmpeg',
        'pyyaml',
        'wandb',
        # "gym-maze",
        "dm_control",
    ],
    extras_require={

    },
    scripts=[],
    packages=find_packages()
)
