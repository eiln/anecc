#!/usr/bin/python3

# SPDX-License-Identifier: MIT
# Copyright 2022 Eileen Yoon <eyn@gmx.com>

import click
from anecc import anecc_compile

@click.command()
@click.argument('path', required=True, type=click.Path(exists=True))
@click.option('--name', '-n', type=str)
@click.option('--outd', '-o', type=str, default='')
def run(path, name, outd):
	anecc_compile(path, name, outd)
