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
LIBANE_HDR = "/usr/include/libane"
LIBANE_LIB = "/usr/lib/libane.a"

def anecc_compile(path, name="model", outdir=""):

	if (platform.system() != "Linux"):
		logger.warn("compiling is only supported on Linux.")

	res = anect_convert(path, name=name)

	if (platform.system() != "Linux"):
		logger.warn("Model can convert successfully. Re-run anecc in Linux.")
		return

	name = res.name  # override with sanitized name
	outdir = os.path.abspath(outdir)

	anect_write(res, prefix=outdir)
