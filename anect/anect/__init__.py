#!/usr/bin/python3

# SPDX-License-Identifier: MIT
# Copyright 2022 Eileen Yoon <eyn@gmx.com>

import contextlib
import logging
import string
import struct
import io
import os
import re

logging.basicConfig(
    format='%(name)s::%(levelname)s: %(message)s',
    level=logging.INFO
)
logging.addLevelName(logging.INFO, 'info')
logging.addLevelName(logging.WARNING, 'warn')
logger = logging.getLogger(__name__)

TILE_SIZE = 0x4000
BASE_ADDR = 0x30000000
TD_SIZE = 0x274
BAR_SIZE = 0x20
DMA0_GRAN = 16
TD_MAGIC = 0xf401f800

class dotdict(dict):  # https://stackoverflow.com/a/23689767/20891128
	__getattr__ = dict.get
	__setattr__ = dict.__setitem__
	__delattr__ = dict.__delitem__

def ntiles(size): return (size // TILE_SIZE)
def round_up(x, y): return ((x + (y - 1)) & (-y))
def round_down(x, y): return (x - (x % y))

# https://stackoverflow.com/a/17197027
def strings(filename, min_len=4):
	with open(filename, errors="ignore") as f:
		data = f.read()
		result = ""
		for c in data:
			if c in string.printable:
				result += c
				continue
			if len(result) >= min_len:
				yield result
			result = ""
		if len(result) >= min_len:  # catch result at EOF
			yield result


def _anect_get_name(hwxpath, name):
	if (not name):
		name = os.path.splitext(os.path.basename(hwxpath))[0]
	name = name.replace("-", "_").replace(" ", "_").lower()
	# https://stackoverflow.com/a/3303361
	name = re.sub('[^0-9a-zA-Z_]', '', name)  # Remove invalid characters
	name = re.sub('^[^a-zA-Z_]+', '', name)  # Remove leading characters until we find a letter or underscore
	if (not name):
		name = "model"
	logger.info(f'using name: {name}')
	return name


def _anect_get_nchw(hwxpath):
	# strings -n 50 "model.hwx" | grep ":t.*:5$"
	lines = list(strings(hwxpath, min_len=50))
	regexp = re.compile(":t.*:5$")
	stabs = [line for line in lines if re.search(regexp, line)]
	assert(len(stabs) >= 2)

	nchw_l = []
	for i,stab in enumerate(stabs):
		nchw = stab.split(":")[1:-1]
		assert(len(nchw) == 4)

		assert(nchw[0][-1] == 'n')  # BatchSize
		assert(nchw[1][-1] == 'c')  # InputChannels
		assert(nchw[2][-1] == 'h')  # InputHeight
		assert(nchw[3][-1] == 'w')  # InputWidth

		N = int(nchw[0].split(";")[2])
		C = int(nchw[1].split(";")[2])
		H = int(nchw[2].split(";")[2])
		W = int(nchw[3].split(";")[2])

		rS = round_up((W * 2), 64)   # InputRowStride
		pS = round_up((rS * H), 64)  # InputPlaneStride
		assert(pS == int(nchw[1].split("=s", 1)[1][:-1]))
		assert(rS == int(nchw[2].split("=s", 1)[1][:-1]))

		name = stab.split(":t", 1)[0]
		logger.debug("STAB%d: %s: NCHW: (%d, %d, %d, %d) pS: 0x%x rS: 0x%x" % (i, name, N, C, H, W, pS, rS))
		nchw_l.append(dotdict({"N": N, "C": C, "H": H, "W": W, "pS": pS, "rS": rS, "name": name}))

	return nchw_l


def anect_convert(hwxpath, name="model", force=False):
	if (os.path.splitext(hwxpath)[1] == ".mlmodel"):
		logger.warn("pass the hwx output of coreml2hwx")

	res = dotdict({"path": hwxpath})
	res.name = _anect_get_name(hwxpath, name)

	res.data = open(hwxpath, "rb").read()
	assert ((not len(res.data) % 4))
	up = struct.unpack('<' + 'L'*(len(res.data) // 4), res.data)

	first = next(i for i,x in enumerate(up) if (x == BASE_ADDR))
	pos = next(i for i,x in enumerate(up) if (x == BASE_ADDR) and (i > first))
	tsk_size = up[pos+2]
	assert((tsk_size) and (tsk_size >= TD_SIZE))

	krn_addr = BASE_ADDR + round_up(tsk_size, DMA0_GRAN)
	pos = next(i for i,x in enumerate(up) if (x == krn_addr))
	krn_size = up[pos+2]
	assert((krn_size) and (not krn_size % DMA0_GRAN))

	size = round_up(tsk_size, DMA0_GRAN) + krn_size

	td_size = TD_SIZE  # (0x9c + 1) << 2
	assert((td_size) and (td_size * 2 < TILE_SIZE))

	pos = next(i for i,x in enumerate(up) if (x == 0x9c))
	assert(up[pos-2] == BASE_ADDR)
	td_count = up[pos+1]
	assert((td_count) and (td_count < 0xffff))
	res.update({"size": size, "tsk_size": tsk_size,  "krn_size": krn_size, 
			"td_count": td_count, "td_size": td_size})


	buf_addr = BASE_ADDR + round_up(size, TILE_SIZE)
	itm_count = 0
	src_count = 0
	dst_count = 0
	res.itm_sizes = [0] * BAR_SIZE
	res.src_sizes = [0] * BAR_SIZE
	res.dst_sizes = [0] * BAR_SIZE
	for n in range(BAR_SIZE):
		try:
			pos = next(i for i,x in enumerate(up) if (x == buf_addr))
		except StopIteration:
			break

		buf_size = up[pos+2]
		assert((buf_size) and (not buf_size % TILE_SIZE) and (buf_size < (0x10000 * TILE_SIZE)))

		ident = up[pos+8:pos+12]
		if (ident == (0x3, 0x3, 0x1, 0x4)):
			buf_name = "itm%d" % itm_count
			res.itm_sizes[itm_count] = buf_size
			itm_count += 1

		elif (ident == (0x1, 0x1, 0x1, 0x6)):
			buf_name = "src%d" % src_count
			res.src_sizes[src_count] = buf_size
			src_count += 1

		elif (ident == (0x2, 0x2, 0x1, 0x6)):
			buf_name = "dst%d" % dst_count
			res.dst_sizes[dst_count] = buf_size
			dst_count += 1

		else:
		    raise ValueError("uh oh")

		logger.debug("BUF[%d]: %s: addr: 0x%x size: 0x%x" % (n, buf_name, buf_addr, buf_size))
		buf_addr += buf_size

	assert((src_count) and (dst_count) and (itm_count <= 1))
	res.update({"itm_count": itm_count, "src_count": src_count,  "dst_count": dst_count})


	res.tiles = [0x0] * BAR_SIZE
	for n in range(res.itm_count):
		res.tiles[3 + n] = ntiles(res.itm_sizes[n])
	for n in range(res.dst_count):
		res.tiles[4 + n] = ntiles(res.dst_sizes[n])
	for n in range(res.src_count):
		res.tiles[4 + res.dst_count + n] = ntiles(res.src_sizes[n])


	rnge = [i for i,x in enumerate(up) if (x == TD_MAGIC)]
	assert(len(rnge) == td_count)
	low, high = min(rnge), max(rnge)
	assert(tsk_size - ((high - low) * 4) == td_size)
	tsk_start = round_down((low * 4), 0x1000)
	res.update({"tsk_start": tsk_start})


	res.nchw = _anect_get_nchw(hwxpath)
	assert(len(res.nchw) == (src_count + dst_count))
	for n in range(src_count):
		nchw = res.nchw[n]
		size = nchw.N * nchw.C * nchw.pS
		assert(round_up(size, TILE_SIZE) == res.src_sizes[n])
		logger.info("found input %d/%d: (%d, %d, %d, %d)" % (n+1, res.src_count, nchw.N, nchw.C, nchw.H, nchw.W))

	for n in range(dst_count):
		nchw = res.nchw[n + src_count]
		size = nchw.N * nchw.C * nchw.pS
		assert(round_up(size, TILE_SIZE) == res.dst_sizes[n])
		logger.info("found output %d/%d: (%d, %d, %d, %d)" % (n+1, res.dst_count, nchw.N, nchw.C, nchw.H, nchw.W))

	for stab in res.nchw:
		if ("ctx_" in stab.name and (res.src_count > 1)):
			if (force):
				logger.warn("bypassing suspected CPU layer warning")
			else:
				raise RuntimeError("uh oh, looks like there's an unresolved CPU layer.\n"
						"did you really mean %d inputs? use the -f flag to bypass this." % (res.src_count))
	return res


def anect_print(res):
	print('')
	print('static const struct ane_model anec_%s = {' % res.name)
	print('\t.name = "%s",' % res.name)
	print('\t.input_count = %d,' % res.src_count)
	print('\t.output_count = %d,' % res.dst_count)

	print('\t.anec = {')
	print('\t\t.size = 0x%x,' % res.size)
	print('\t\t.td_size = 0x%x,' % res.td_size)
	print('\t\t.td_count = 0x%x,' % res.td_count)
	print('\t\t.tsk_size = 0x%x,' % res.tsk_size)
	print('\t\t.krn_size = 0x%x,' % res.krn_size)

	print('\t\t.tiles[0] = %d, /* 0x%x */' % (ntiles(round_up(res.size, TILE_SIZE)), round_up(res.size, TILE_SIZE)))
	for n in range(res.itm_count):
		print('\t\t.tiles[%d] = %d, /* itm%d 0x%x */' % 
		      (3 + n, res.tiles[3 + n], n, res.itm_sizes[n]))
	for n in range(res.dst_count):
		print('\t\t.tiles[%d] = %d, /* dst%d 0x%x */' % 
		      (4 + n, res.tiles[4 + n], n, res.dst_sizes[n]))
	for n in range(res.src_count):
		print('\t\t.tiles[%d] = %d, /* src%d 0x%x */' % 
		      (4 + res.dst_count + n, res.tiles[4 + res.dst_count + n], n, res.src_sizes[n]))

	print('\t\t.types[%d] = ANE_TILE_CMD,' % (0))
	for n in range(res.itm_count):
		print('\t\t.types[%d] = ANE_TILE_ITM,' % (3 + n))
	for n in range(res.dst_count):
		print('\t\t.types[%d] = ANE_TILE_DST,' % (4 + n))
	for n in range(res.src_count):
		print('\t\t.types[%d] = ANE_TILE_SRC,' % (4 + res.dst_count + n))
	print('\t},')

	print('\t.data = &_binary_%s_anec_start,' % (res.name))

	for n in range(res.dst_count):
		nchw = res.nchw[n + res.src_count]
		print('\t.nchw[%d] = {%d, %d, %d, %d, 0x%x, 0x%x}, /* dst%d */' % 
		(4 + n, nchw.N, nchw.C, nchw.H, nchw.W, nchw.pS, nchw.rS, n))

	for n in range(res.src_count):
		nchw = res.nchw[n]
		print('\t.nchw[%d] = {%d, %d, %d, %d, 0x%x, 0x%x}, /* src%d */' % 
		(4 + res.dst_count + n, nchw.N, nchw.C, nchw.H, nchw.W, nchw.pS, nchw.rS, n))
	print('};')
	print('')
	return


def _anect_write_hdr(res, prefix=""):
	fname = f'anec_{res.name}.h'
	outpath = os.path.join(prefix, fname)
	logger.debug(f'writing header to {outpath}')
	with open(outpath, "w") as f:
		f.write('#ifndef __ANEC_%s_H__\n' % (res.name.upper()))
		f.write('#define __ANEC_%s_H__\n' % (res.name.upper()))
		f.write('\n')
		f.write('#include "ane.h"\n')
		f.write('\n')
		f.write('extern char _binary_%s_anec_start[];\n' % (res.name))
		f.write('extern char _binary_%s_anec_end[];\n' % (res.name))

		cap = io.StringIO()
		with contextlib.redirect_stdout(cap):
			anect_print(res)
		f.write(cap.getvalue())

		f.write('struct ane_nn *ane_init_%s(void) { return ane_init(&anec_%s); }\n' % (res.name, res.name))
		f.write('\n')
		f.write('#endif /* __ANEC_%s_H__ */\n' % (res.name.upper()))
	return fname


def _anect_write_bin(res, prefix=""):
	fname = f'{res.name}.anec'
	outpath = os.path.join(prefix, fname)
	logger.debug(f'writing kernel to {outpath}')
	open(outpath, "wb").write(res.data[res.tsk_start:res.tsk_start+res.size])
	return fname


def anect_write(res, prefix):
	_anect_write_hdr(res, prefix)
	_anect_write_bin(res, prefix)
