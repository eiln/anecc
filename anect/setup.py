#!/usr/bin/env python3

from setuptools import setup

setup(
    name="anect",
    version="1.0.4",
    description='ane converter',
    author='Eileen Yoon',
    author_email='eyn@gmx.com',
    packages=['anect'],
    install_requires=['Click'],
    entry_points='''
        [console_scripts]
        anect=anect.anect_run:run
    ''',
)
