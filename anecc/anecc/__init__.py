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
PYTHON_HDR = sysconfig.get_paths()['include']  # "/usr/include/python3.10"
LIBDRM_HDR = "/usr/include/libdrm"
DRIVER_HDR = "/home/eileen/ane/ane/src/include"  # should be resolved w/ accel?
LIBANE_HDR = "/usr/include/libane"
LIBANE_OBJ = "/usr/lib/libane.o"  # python doesn't like archives


def anecc_compile(path, name="model", outdir="", c=False, python=False):

	if (platform.system() != "Linux"):
		logger.warn("compiling is only supported on Linux.")

	res = anect_convert(path, name=name)
	name = res.name  # override with sanitized name

	if (platform.system() != "Linux"):
		logger.warn("Model can convert successfully. Re-run anecc in Linux.")
		return
	if not (c or python):
		logger.warn("Nothing to compile. See anecc --help for available options.")
		return

	if (not outdir):
		outdir = os.getcwd()
	else:
		outdir = os.path.abspath(outdir)

	with tempfile.TemporaryDirectory() as tmpdir:
		anect_write(res, prefix=tmpdir)

		anec_obj = f'{name}.anec.o'
		anec_hdr = f'anec_{name}.h'

		os.chdir(tmpdir)

		# See "Embedding resources in executable using GCC"
		# https://stackoverflow.com/a/4158997
		# Since ML weights are fucking massive,
		# we abuse ld to load them @ compile time.
		cmd = f'ld -r -b binary -o {anec_obj} {name}.anec'
		logger.debug(cmd)
		subprocess.run(shlex.split(cmd))

		if (c):
			logger.info('compiling for C/C++...')

			# save kernel object
			shutil.copyfile(anec_obj, os.path.join(outdir, anec_obj))
			logger.info(f'created kernel object: {os.path.join(outdir, anec_obj)}')

			# all but the init call is model-specific (duh)
			# so compile that & generate a header for it
			init_obj = os.path.join(tmpdir, f'anec_{name}.o')
			init_src = os.path.join(tmpdir, f'anec_{name}.c')  # tmp
			with open(init_src, "w") as f:
				f.write(f'#include "ane.h"\n')
				f.write(f'#include "{anec_hdr}"\n')

			cmd = f'{CC} -I/{LIBDRM_HDR}' \
				f' -I/{DRIVER_HDR} -I/{LIBANE_HDR}' \
				f' -c -o {init_obj} {init_src}'
			logger.info(cmd)
			subprocess.run(shlex.split(cmd))

			# save init call object
			obj_path = os.path.join(outdir, f'anec_{name}.o')
			shutil.copyfile(init_obj, obj_path)
			logger.info(f'created anec object: {obj_path}')

			# write the header to access the init call
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


		if (python):
			logger.info('compiling for Python...')

			# again, compile the init call
			pyane_obj_name = f'{name}.anec.so'
			pyane_obj = os.path.join(tmpdir, pyane_obj_name)
			pyane_src = os.path.join(tmpdir, f'pyane_{name}.c')  # tmp
			with open(pyane_src, "w") as f:
				f.write(f'#include "pyane.h"\n')  # contains pyane funcs
				f.write(f'#include "{anec_hdr}"\n')
				f.write('void *pyane_init(void) { return ane_init_%s(); }\n' % name)

			# compile completed pyane to dylib
			cmd = f'{CC} -shared -pthread -fPIC -fno-strict-aliasing -I.' \
				f' -I/{PYTHON_HDR} -I/{LIBDRM_HDR}' \
				f' -I/{DRIVER_HDR} -I/{LIBANE_HDR}' \
				f' {LIBANE_OBJ} {anec_obj}' \
				f' {pyane_src} -o {pyane_obj}'
			logger.info(cmd)
			subprocess.run(shlex.split(cmd))

			# save the thing
			obj_path = os.path.join(outdir, pyane_obj_name)
			shutil.copyfile(pyane_obj, obj_path)
			logger.info(f'created dylib oject: {obj_path}')
