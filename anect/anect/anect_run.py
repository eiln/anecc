#!/usr/bin/python3

# SPDX-License-Identifier: MIT
# Copyright 2022 Eileen Yoon <eyn@gmx.com>

import click
from anect import anect_convert, anect_write, anect_print

@click.command(name="anect")
@click.argument('path', required=True, type=click.Path(exists=True))
@click.option('--name', '-n', type=str, help="Model name.")
@click.option('--outdir', '-o', type=str, default='', help="Output directory prefix.")
@click.option('--write', '-w', is_flag=True, default=False, help="Write header/binary.")
@click.option('--print', '-p', 'print_', is_flag=True, default=False, help="Print struct.")
@click.option('--force', '-f', is_flag=True, default=False, help="Bypass warnings.")
def run(path, name, outdir, write, print_, force):
	res = anect_convert(path, name, force)
	if (print_):
		anect_print(res)
	if (write):
		anect_write(res, prefix=outdir)
