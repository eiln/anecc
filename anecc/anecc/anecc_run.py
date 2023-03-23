#!/usr/bin/python3

# SPDX-License-Identifier: MIT
# Copyright 2022 Eileen Yoon <eyn@gmx.com>

import click
from anecc import anecc_compile

@click.command(name="anecc")
@click.argument('path', required=True, type=click.Path(exists=True))
@click.option('--name', '-n', type=str, help="Model name.")
@click.option('--outdir', '-o', type=str, default='', help="Output directory prefix.")
@click.option('--flags', '-f', type=str, default='', help="Additional compiler flags.")
@click.option('--c', '-c', is_flag=True, default=False, help="Compile to C/C++.")
@click.option('--python', '-p', is_flag=True, default=False, help="Compile to Python.")
@click.option('--all', '-a', 'all_', is_flag=True, default=False, help="Compile to all.")
def run(path, name, outdir, flags, c, python, all_):
	c = c or all_
	python = python or all_
	anecc_compile(path, name=name, outdir=outdir, flags=flags, c=c, python=python)
