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
DRIVER_HDR = "/home/eileen/ane/ane/src/include"
LIBANE_HDR = "/usr/include/libane"
LIBANE_OBJ = "/usr/lib/libane.o"


def anecc_compile(path, name="model", outdir="", c=True, cpp=False, python=False):

	if (platform.system() != "Linux"):
		logger.warn("compiling is only supported on Linux.")
	res = anect_convert(path, name=name)
	name = res.name  # override with sanitized name
	if (platform.system() != "Linux"):
		logger.warn("Model can convert successfully. Re-run anecc in Linux.")
		exit(0)

	if (not outdir):
		outdir = os.getcwd()
	else:
		outdir = os.path.abspath(outdir)

	with tempfile.TemporaryDirectory() as tmpdir:
		anect_write(res, prefix=tmpdir)
		os.chdir(tmpdir)

		anec_hdr = f'anec_{name}.h'
		anec_obj = f'{name}.anec.o'
		cmd = f'ld -r -b binary -o {anec_obj} {name}.anec'
		logger.info(cmd)
		subprocess.run(shlex.split(cmd))

		if (c or cpp):
			logger.info('compiling for C...')

			hdr_path = os.path.join(outdir, anec_hdr)
			obj_path = os.path.join(outdir, anec_obj)
			if (c):
				shutil.copyfile(anec_hdr, hdr_path)
				logger.info(f'created header: {hdr_path}')
			shutil.copyfile(anec_obj, obj_path)
			logger.info(f'created object: {obj_path}')

		if (cpp):
			logger.info('compiling for C++...')

			cpp_obj_name = f'anecpp_{name}.o'
			cpp_obj = os.path.join(tmpdir, cpp_obj_name)

			cpp_src = os.path.join(tmpdir, f'anecpp_{name}.c')
			with open(cpp_src, "w") as f:
				f.write(f'#include "ane.h"\n')
				f.write(f'#include "{anec_hdr}"\n')
				f.write('struct ane_nn *anecpp_init_%s(void) { return ane_init_%s(); }\n' % (name, name))
			cmd = f'{CC} -I/{LIBDRM_HDR}' \
				f' -I/{DRIVER_HDR} -I/{LIBANE_HDR}' \
				f' -c -o {cpp_obj} {cpp_src}'
			logger.info(cmd)
			subprocess.run(shlex.split(cmd))

			cpp_obj_path = os.path.join(outdir, cpp_obj_name)
			shutil.copyfile(cpp_obj, cpp_obj_path)
			logger.info(f'created cpp object: {cpp_obj_path}')

			hpp = "#ifndef __ANECPP_%s_HPP__\n" \
				"#define __ANECPP_%s_HPP__\n" \
				"\n" \
				"#if defined(__cplusplus)\n" \
				"extern \"C\" {\n" \
				"#endif\n" \
				"\n" \
				"#include \"ane.h\"\n" \
				"struct ane_nn *anecpp_init_%s(void);\n" \
				"\n" \
				"#if defined(__cplusplus)\n" \
				"}\n" \
				"#endif\n" \
				"\n" \
				"#endif /* __ANECPP_%s_HPP__ */\n" % (name.upper(), name.upper(), name, name.upper())
			hpp_path = os.path.join(outdir, f'anecpp_{name}.hpp')
			with open(hpp_path, "w") as f:
				f.write(hpp)
			logger.info(f'created hpp header: {hpp_path}')

		if (python):
			logger.info('compiling for Python...')

			pyane_obj_name = f'{name}.anec.so'
			pyane_src = os.path.join(tmpdir, f'pyane_{name}.c')
			pyane_obj = os.path.join(tmpdir, pyane_obj_name)
			with open(pyane_src, "w") as f:
				f.write(f'#include "pyane.h"\n')
				f.write(f'#include "{anec_hdr}"\n')
				f.write('void *pyane_init(void) { return ane_init_%s(); }\n' % name)

			cmd = f'{CC} -shared -pthread -fPIC -fno-strict-aliasing -I.' \
				f' -I/{PYTHON_HDR} -I/{LIBDRM_HDR}' \
				f' -I/{DRIVER_HDR} -I/{LIBANE_HDR}' \
				f' {LIBANE_OBJ} {anec_obj}' \
				f' {pyane_src} -o {pyane_obj}'
			logger.info(cmd)
			subprocess.run(shlex.split(cmd))

			obj_path = os.path.join(outdir, pyane_obj_name)
			shutil.copyfile(pyane_obj, obj_path)
			logger.info(f'created dylib oject: {obj_path}')
