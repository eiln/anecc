#!/usr/bin/env python3

from setuptools import setup

setup(
    name="anecc",
    version="1.0.9",
    description='ANE converter',
    author='Eileen Yoon',
    author_email='eyn@gmx.com',
    packages=['anecc'],
    install_requires=['Click', 'construct'],
    entry_points='''
        [console_scripts]
        anecc=anecc.run:run
    ''',
)
