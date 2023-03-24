#!/usr/bin/python3

# SPDX-License-Identifier: MIT
# Copyright 2022 Eileen Yoon <eyn@gmx.com>

from anect import anect_convert, anect_write

import subprocess
import sysconfig
import platform
import tempfile
import logging
import shutil
import shlex
import os

logging.basicConfig(
    format='%(name)s::%(levelname)s: %(message)s',
    level=logging.INFO
)
logging.addLevelName(logging.INFO, 'info')
logging.addLevelName(logging.WARNING, 'warn')
logger = logging.getLogger(__name__)

CC = "gcc"
CFLAGS = "-I. -std=gnu99"
PYTHON_HDR = sysconfig.get_paths()['include']  # "/usr/include/python3.10"
DRIVER_HDR = "/home/eileen/ane/ane/src/include"  # should be resolved w/ accel?
LIBANE_HDR = "/usr/include/libane"
LIBANE_LIB = "/usr/lib/libane.a"


def _anecc_compile_c(name, outdir, tmpdir, flags=""):

	logger.info('compiling for C/C++...')

	kern_obj = f'{name}.anec.o'
	shutil.copyfile(kern_obj, os.path.join(outdir, kern_obj))
	logger.info(f'created kernel object: {os.path.join(outdir, kern_obj)}')

	# all but the init call is model-specific (duh)
	# so compile that & generate a header for it
	init_obj = os.path.join(tmpdir, f'anec_{name}.o')
	init_src = os.path.join(tmpdir, f'anec_{name}.c')  # tmp
	with open(init_src, "w") as f:
		f.write(f'#include "ane.h"\n')
		f.write(f'#include "anec_{name}.h"\n')

	cmd = f'{CC} {CFLAGS} {flags} -I/{DRIVER_HDR} -I/{LIBANE_HDR}' \
		f' -c -o {init_obj} {init_src}'
	logger.info(cmd)
	subprocess.run(shlex.split(cmd))

	obj_path = os.path.join(outdir, f'anec_{name}.o')
	shutil.copyfile(init_obj, obj_path)
	logger.info(f'created anec object: {obj_path}')

	hdr = "#ifndef __ANEC_%s_H__\n" \
		"#define __ANEC_%s_H__\n" \
		"\n" \
		"#if defined(__cplusplus)\n" \
		"extern \"C\" {\n" \
		"#endif\n" \
		"\n" \
		"#include \"ane.h\"\n" \
		"struct ane_nn *ane_init_%s(void);\n" \
		"\n" \
		"#if defined(__cplusplus)\n" \
		"}\n" \
		"#endif\n" \
		"\n" \
		"#endif /* __ANEC_%s_H__ */\n" % (name.upper(), name.upper(), name, name.upper())

	hdr_path = os.path.join(outdir, f'anec_{name}.h')
	with open(hdr_path, "w") as f:
		f.write(hdr)
	logger.info(f'created anec header: {hdr_path}')

	return


def _anecc_compile_python(name, outdir, tmpdir, flags=""):

	logger.info('compiling for Python...')

	# again, compile the init call
	dylib_name = f'{name}.anec.so'
	dylib_obj = os.path.join(tmpdir, dylib_name)
	dylib_src = os.path.join(tmpdir, f'pyane_{name}.c')  # tmp
	with open(dylib_src, "w") as f:
		f.write(f'#include "pyane.h"\n')
		f.write(f'#include "anec_{name}.h"\n')
		f.write('void *pyane_init(void) { return ane_init_%s(); }\n' % name)

	# compile completed dylib
	cmd = f'{CC} {CFLAGS} {flags} -shared -pthread -fPIC -fno-strict-aliasing' \
		f' -I/{PYTHON_HDR} -I/{DRIVER_HDR} -I/{LIBANE_HDR}' \
		f' {name}.anec.o {dylib_src} -o {dylib_obj}' \
		f' {LIBANE_LIB}'

	logger.info(cmd)
	subprocess.run(shlex.split(cmd))

	# save the thing
	dylib_path = os.path.join(outdir, dylib_name)
	shutil.copyfile(dylib_obj, dylib_path)
	logger.info(f'created dylib: {dylib_path}')

	return


def anecc_compile(path, name="model", outdir="", flags="", c=False, python=False):

	if (platform.system() != "Linux"):
		logger.warn("compiling is only supported on Linux.")

	res = anect_convert(path, name=name)

	if (platform.system() != "Linux"):
		logger.warn("Model can convert successfully. Re-run anecc in Linux.")
		return
	if not (c or python):
		logger.warn("Nothing to compile. See anecc --help for available options.")
		return

	name = res.name  # override with sanitized name
	outdir = os.path.abspath(outdir)

	if (flags):
		logger.info(f'Adding flags: {flags}')

	with tempfile.TemporaryDirectory() as tmpdir:
		anect_write(res, prefix=tmpdir)
		os.chdir(tmpdir)

		# See "Embedding resources in executable using GCC"
		# https://stackoverflow.com/a/4158997
		# Since ML weights are fucking massive,
		# we abuse ld to load them @ compile time.
		cmd = f'ld -r -b binary -o {name}.anec.o {name}.anec'
		logger.debug(cmd)
		subprocess.run(shlex.split(cmd))

		if (c):
			_anecc_compile_c(name, outdir, tmpdir, flags=flags)
		if (python):
			_anecc_compile_python(name, outdir, tmpdir, flags=flags)
