#!/usr/bin/python3

# SPDX-License-Identifier: MIT
# Copyright 2022 Eileen Yoon <eyn@gmx.com>

import click
from anecc import anecc_convert, anecc_print, anecc_compile

@click.command(name="anecc")
@click.argument('path', required=True, type=click.Path(exists=True))
@click.option('--name', '-n', type=str, help="Model name")
@click.option('--out', '-o', type=str, default='', help="Output file name (default $name.anec)")
@click.option('--dry', '-d', is_flag=True, default=False, help="Don't write anec.")
@click.option('--print', '-p', 'print_', is_flag=True, default=False, help="Print struct.")
@click.option('--force', '-f', is_flag=True, default=False, help="Bypass warnings.")
def run(path, name, out, dry, print_, force):
	res = anecc_convert(path, name, force)
	if (print_):
		anecc_print(res)
	if (not dry):
		anecc_compile(res, out)
