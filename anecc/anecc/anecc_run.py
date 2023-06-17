#!/usr/bin/python3

# SPDX-License-Identifier: MIT
# Copyright 2022 Eileen Yoon <eyn@gmx.com>

import click
from anecc import anecc_compile

@click.command(name="anecc")
@click.argument('path', required=True, type=click.Path(exists=True))
@click.option('--name', '-n', type=str, help="Model name.")
@click.option('--outdir', '-o', type=str, default='', help="Output directory prefix.")
def run(path, name, outdir):
	anecc_compile(path, name=name, outdir=outdir)
