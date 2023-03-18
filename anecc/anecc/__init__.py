#!/usr/bin/python3

# SPDX-License-Identifier: MIT
# Copyright 2022 Eileen Yoon <eyn@gmx.com>

import subprocess
import sysconfig
import platform
import tempfile
import logging
import shutil
import shlex
import os

from anect import anect_convert, anect_write

logging.basicConfig(
    format='%(name)s::%(levelname)s: %(message)s',
    level=logging.INFO
)
logging.addLevelName(logging.INFO, 'info')
logging.addLevelName(logging.WARNING, 'warn')
logger = logging.getLogger(__name__)

CC = "gcc"
PYTHON_HDR = sysconfig.get_paths()['include']  # "/usr/include/python3.10"
LIBDRM_HDR = "/usr/include/libdrm"
DRIVER_HDR = "/home/eileen/ane/ane/src/include"
ANELIB_HDR = "/home/eileen/ane/anelib/include"
ANELIB_OBJ = "/home/eileen/ane/build/anelib.o"


def _anecc_common(path, name, outdir):
	if (platform.system() != "Linux"):
		logger.warn("compiling is only supported on Linux.")
	res = anect_convert(path, name=name)
	if (platform.system() != "Linux"):
		logger.warn("Model can convert successfully. Re-run anecc in Linux.")
		exit(0)

	name = res.name  # override with sanitized name
	if (not outdir):
		outdir = os.getcwd()
	else:
		outdir = os.path.abspath(outdir)
	return (res, name, outdir)


def anecc_compile(path, name="model", outdir="", c=True, python=False):

	res, name, outdir = _anecc_common(path, name, outdir)

	with tempfile.TemporaryDirectory() as tmpdir:
		anect_write(res, prefix=tmpdir)
		os.chdir(tmpdir)

		anec_hdr = f'anec_{name}.h'
		anec_obj = f'{name}.anec.o'
		cmd = f'ld -r -b binary -o {anec_obj} {name}.anec'
		logger.info(cmd)
		subprocess.run(shlex.split(cmd))

		if (c):
			logger.info('compiling for C...')
			hdr_path = os.path.join(outdir, anec_hdr)
			obj_path = os.path.join(outdir, anec_obj)
			shutil.copyfile(anec_hdr, hdr_path)
			shutil.copyfile(anec_obj, obj_path)
			logger.info(f'created header: {hdr_path}')
			logger.info(f'created object: {obj_path}')

		if (python):
			logger.info('compiling for Python...')
			pyane_lib = f'{name}.anec.so'
			pyane_src = os.path.join(tmpdir, f'pyane_{name}.c')
			pyane_obj = os.path.join(tmpdir, pyane_lib)
			with open(pyane_src, "w") as f:
				f.write(f'#include "pyane.h"\n')
				f.write(f'#include "{anec_hdr}"\n')

			cmd = f'{CC} -shared -pthread -fPIC -fno-strict-aliasing -I.' \
				f' -I/{PYTHON_HDR} -I/{LIBDRM_HDR}' \
				f' -I/{DRIVER_HDR} -I/{ANELIB_HDR}' \
				f' {ANELIB_OBJ} {anec_obj}' \
				f' {pyane_src} -o {pyane_obj}'
			logger.info(cmd)
			subprocess.run(shlex.split(cmd))

			lib_path = os.path.join(outdir, pyane_lib)
			shutil.copyfile(pyane_obj, lib_path)
			logger.info(f'created dylib: {lib_path}')

	return
