#!/usr/bin/python3

# SPDX-License-Identifier: MIT
# Copyright 2022 Eileen Yoon <eyn@gmx.com>

import click
from anecc import anecc_c, anecc_py

@click.command(name="anecc")
@click.argument('path', required=True, type=click.Path(exists=True))
@click.option('--name', '-n', type=str, help="Model name.")
@click.option('--outdir', '-o', type=str, default='', help="Output directory prefix.")
@click.option('--python', '-p', is_flag=True, default=False, help="Compile to python (default C).")
def run(path, name, python, outdir):
	if (python):
		anecc_py(path, name, outdir)
	else:
		anecc_c(path, name, outdir)
