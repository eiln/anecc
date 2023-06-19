#!/usr/bin/python3

# SPDX-License-Identifier: MIT
# Copyright 2022 Eileen Yoon <eyn@gmx.com>

from construct import Struct, Array, Int32ul, Int64ul
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
TILE_COUNT = 0x20
DMA0_GRAN = 16
TD_MAGIC = 0xf401f800

NCHW_COUNT = 0x6
HEADER_SIZE = 0x1000

class dotdict(dict):  # https://stackoverflow.com/a/23689767/20891128
	__getattr__ = dict.get
	__setattr__ = dict.__setitem__
	__delattr__ = dict.__delitem__

def ntiles(size): return (size // TILE_SIZE)
def round_up(x, y): return ((x + (y - 1)) & (-y))
def round_down(x, y): return (x - (x % y))


# https://stackoverflow.com/a/17197027
def _get_strings(filename, min_len=4):
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


def _anecc_get_nchw(hwx_path):
	# strings -n 50 "model.hwx" | grep ":t.*:5$"
	lines = list(_get_strings(hwx_path, min_len=50))
	stabs = [line for line in lines if re.search(re.compile(":t.*:5$"), line)]
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


def anecc_convert(hwx_path, name="model", force=False):
	if (os.path.splitext(hwx_path)[1] == ".mlmodel"):
		logger.warn("pass the hwx output of coreml2hwx")

	res = dotdict({"path": hwx_path})

	res.name = os.path.splitext(os.path.basename(hwx_path))[0] if (not name) else name
	res.name = "model" if not res.name else res.name

	res.data = open(hwx_path, "rb").read()
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
	res.itm_sizes = [0] * TILE_COUNT
	res.src_sizes = [0] * TILE_COUNT
	res.dst_sizes = [0] * TILE_COUNT
	for n in range(TILE_COUNT):
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


	res.tiles = [0x0] * TILE_COUNT
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


	res.nchw = _anecc_get_nchw(hwx_path)
	assert(len(res.nchw) == (src_count + dst_count))

	for i in range(2):
		try:
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
			break
		except: # on M2 stab order seems to be swapped
			res.nchw = res.nchw[dst_count:] + res.nchw[:dst_count]

	for stab in res.nchw:
		if ("ctx_" in stab.name and (res.src_count > 1)):
			if (force):
				logger.warn("Bypassing suspected intermediate CPU layer warning")
			else:
				raise RuntimeError("Looks like there's an unresolved CPU layer.\n"
						"Did you really mean %d inputs? use the -f flag to bypass this." % (res.src_count))

	res.build = _anecc_build(res)

	return res


def _anecc_build(res):
	my_dict = dotdict({
			"size": res.size,
			"td_size": res.td_size,
			"td_count": res.td_count,
			"tsk_size": res.tsk_size,
			"krn_size": res.krn_size,
			"src_count": res.src_count,
			"dst_count": res.dst_count,
			"tiles": res.tiles,
			"nchw": [0x0] * TILE_COUNT * NCHW_COUNT,
			})

	my_dict.tiles[0] = ntiles(round_up(res.size, TILE_SIZE))

	for n in range(res.dst_count):
		nchw = res.nchw[n + res.src_count]
		my_dict.nchw[(4+n)*NCHW_COUNT:(4+n+1)*NCHW_COUNT] = [nchw.N, nchw.C, nchw.H, nchw.W, nchw.pS, nchw.rS]

	for n in range(res.src_count):
		nchw = res.nchw[n]
		my_dict.nchw[(4+res.dst_count+n)*NCHW_COUNT:(4+res.dst_count+n+1)*NCHW_COUNT] = [nchw.N, nchw.C, nchw.H, nchw.W, nchw.pS, nchw.rS]

	return my_dict


def _get_buf_name(idx, dst_count):
	if (idx == 0): return "cmd"
	if (idx == 1): return "krn"
	if (idx == 2): return "itm1"
	if (idx == 3): return "itm0"
	if (idx >= 4 and idx <  (4 + dst_count)): return "dst%d" % (idx - 4)
	if (idx >= 4 and idx >= (4 + dst_count)): return "src%d" % (idx - 4 - dst_count)


def anecc_print(res):
	print('')
	print('static const struct anec anec_%s = {' % res.name)

	build = res.build
	print('\t.size = 0x%x,' % build.size)
	print('\t.td_size = 0x%x,' % build.td_size)
	print('\t.td_count = 0x%x,' % build.td_count)
	print('\t.tsk_size = 0x%x,' % build.tsk_size)
	print('\t.krn_size = 0x%x,' % build.krn_size)

	print('\t.src_count = %d,' % build.src_count)
	print('\t.dst_count = %d,' % build.dst_count)

	for n in range(TILE_COUNT):
		if (build.tiles[n]):
			print('\t.tiles[%d] = %d, /* %s 0x%x */' % (n, build.tiles[n], _get_buf_name(n, build.dst_count), build.tiles[n] * TILE_SIZE))

	for n in range(TILE_COUNT):
		nchw = build.nchw[n*NCHW_COUNT : (n+1)*NCHW_COUNT]
		if (nchw[0]):
			print('\t.nchw[%d] = {%d, %d, %d, %d, 0x%x, 0x%x}, /* %s */' % (n, nchw[0], nchw[1], nchw[2], nchw[3], nchw[4], nchw[5], _get_buf_name(n, build.dst_count)))

	print('};')
	print('')


def anecc_compile(res, out):
	fmt = Struct(
	    "size" / Int64ul,
	    "td_size" / Int32ul,
	    "td_count" / Int32ul,
	    "tsk_size" / Int64ul,
	    "krn_size" / Int64ul,
	    "src_count" / Int32ul,
	    "dst_count" / Int32ul,
	    "tiles" / Array(TILE_COUNT, Int32ul),
	    "nchw" / Array(TILE_COUNT * NCHW_COUNT, Int64ul),
	)
	header = fmt.build(res.build)

	assert(len(header) <= HEADER_SIZE)
	header += (b'\0' * (HEADER_SIZE - len(header)))
	content = res.data[res.tsk_start:res.tsk_start+res.size]

	outpath = f'{res.name}.anec' if not out else out
	open(outpath, "wb").write(header + content)
	logger.info(f'compiled anec to: {outpath}')
