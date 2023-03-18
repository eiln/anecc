#!/usr/bin/env python3

from setuptools import setup

setup(
    name="anecc",
    version="1.0.4",
    description='ane compiler',
    author='Eileen Yoon',
    author_email='eyn@gmx.com',
    packages=['anecc'],
    install_requires=['Click', 'anect'],
    entry_points='''
        [console_scripts]
        anecc=anecc.anecc_run:run
    ''',
)
