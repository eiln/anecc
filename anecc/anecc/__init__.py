#!/usr/bin/python3

# SPDX-License-Identifier: MIT
# Copyright 2022 Eileen Yoon <eyn@gmx.com>

import subprocess
import tempfile
import logging
import shutil
import shlex
import os

from anect import anect_convert, anect_save

logging.basicConfig()
logger = logging.getLogger('anecc')
logger.setLevel(logging.INFO)

CC = "gcc"
PYTHON_HDR = "/usr/include/python3.10"
LIBDRM_HDR = "/usr/include/libdrm"
DRIVER_HDR = "/home/eileen/ane/ane/src/include"
ANELIB_HDR = "/home/eileen/ane/anelib/include"
ANELIB_OBJ = "/home/eileen/ane/build/anelib.o"


def anecc_compile(hwxpath, name="model", outdir=""):

	res = anect_convert(hwxpath, name=name)
	name = res.name  # override with sanitized name

	if (not outdir):
		outdir = os.getcwd()

	with tempfile.TemporaryDirectory() as tmpdir:
		os.chdir(tmpdir)
		anect_save(res, prefix=tmpdir)

		anec_obj = f'{name}.anec.o'
		cmd = f'ld -r -b binary -o {anec_obj} {name}.anec'
		logger.info(cmd)
		subprocess.run(shlex.split(cmd))

		pyane_src = os.path.join(tmpdir, f'pyane_{name}.c')
		pyane_obj = os.path.join(tmpdir, f'pyane_{name}.so')
		with open(pyane_src, "w") as f:
			f.write(f'#include "pyane.h"\n')
			f.write(f'#include "anec_{name}.h"\n')

		cmd = f'{CC} -shared -pthread -fPIC -fno-strict-aliasing \
			-I. -Wall -Werror \
			-I/{PYTHON_HDR} -I/{LIBDRM_HDR} \
			-I/{DRIVER_HDR} -I/{ANELIB_HDR} \
			{ANELIB_OBJ} {anec_obj} \
			{pyane_src} -o {pyane_obj}'
		logger.info(cmd)
		subprocess.run(shlex.split(cmd))

		outpath = os.path.join(outdir, f'pyane_{name}.so')
		shutil.copyfile(pyane_obj, outpath)
		logger.info(f'created {outpath}')

