#!/usr/bin/python3

# SPDX-License-Identifier: MIT
# Copyright 2022 Eileen Yoon <eyn@gmx.com>

from contextlib import redirect_stdout
import subprocess
import argparse
import logging
import struct
import io
import os
import re

logging.basicConfig()
logger = logging.getLogger('ANEC')
logger.setLevel(logging.INFO)  # DEBUG INFO

TILE_SIZE = 0x4000
BASE_ADDR = 0x30000000
TD_SIZE = 0x274
BAR_SIZE = 0x20
DMA0_GRAN = 16

class dotdict(dict):  # https://stackoverflow.com/a/23689767/20891128
	__getattr__ = dict.get
	__setattr__ = dict.__setitem__
	__delattr__ = dict.__delitem__

def unpack_L(data):
	assert ((isinstance(data, bytes)) and (not len(data) % 4))
	return struct.unpack('<' + 'L'*(len(data) // 4), data)

def round_up(x, y):
	return ((x + (y - 1)) & (-y))

def round_down(x, y):
	return (x - (x % y))

def ntiles(size):
	assert(not (size % TILE_SIZE))
	return (size // TILE_SIZE)

def sanitize(s):  # https://stackoverflow.com/a/3303361/20891128
	s = re.sub('[^0-9a-zA-Z_]', '', s)  # Remove invalid characters
	s = re.sub('^[^a-zA-Z_]+', '', s)  # Remove leading characters until we find a letter or underscore
	return s


def get_nchw(hwxpath):
	stabs = subprocess.Popen(['sh', '-c', 'strings -n 50 "%s" | grep "ar1" | grep ":t.*:5$"' % (hwxpath)], stdout=subprocess.PIPE).communicate()[0].decode().split()
	if (not stabs): raise ValueError("can't find stabs")

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


def hwx2anec(hwxpath, name='', force=False):
	data = open(hwxpath, "rb").read()
	up = unpack_L(data)
	res = dotdict({"path": hwxpath, "name": name})


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
	res["itm_sizes"] = [0] * BAR_SIZE
	res["src_sizes"] = [0] * BAR_SIZE
	res["dst_sizes"] = [0] * BAR_SIZE
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
			res["itm_sizes"][itm_count] = buf_size
			itm_count += 1

		elif (ident == (0x1, 0x1, 0x1, 0x6)):
			buf_name = "src%d" % src_count
			res["src_sizes"][src_count] = buf_size
			src_count += 1

		elif (ident == (0x2, 0x2, 0x1, 0x6)):
			buf_name = "dst%d" % dst_count
			res["dst_sizes"][dst_count] = buf_size
			dst_count += 1

		else:
		    raise ValueError("uh oh")

		logger.debug("BUF[%d]: %s: addr: 0x%x size: 0x%x" % (n, buf_name, buf_addr, buf_size))
		buf_addr += buf_size

	assert((src_count) and (dst_count) and (itm_count <= 1))
	res.update({"itm_count": itm_count, "src_count": src_count,  "dst_count": dst_count})

	rnge = [i for i,x in enumerate(up) if (x == 0xf401f800)]
	assert(len(rnge) == td_count)
	low, high = min(rnge), max(rnge)
	assert(tsk_size - ((high - low) * 4) == td_size)
	tsk_start = round_down((low * 4), 0x1000)
	res.update({"tsk_start": tsk_start})


	res["nchw"] = get_nchw(hwxpath)
	assert(len(res.nchw) == (src_count + dst_count))
	for n in range(src_count):
		nchw = res.nchw[n]
		size = nchw.N * nchw.C * nchw.pS
		assert(round_up(size, TILE_SIZE) == res.src_sizes[n])
		print("found input %d/%d: (%d, %d, %d, %d)" % (n+1, res.src_count, nchw.N, nchw.C, nchw.H, nchw.W))

	for n in range(dst_count):
		nchw = res.nchw[n + src_count]
		size = nchw.N * nchw.C * nchw.pS
		assert(round_up(size, TILE_SIZE) == res.dst_sizes[n])
		print("found output %d/%d: (%d, %d, %d, %d)" % (n+1, res.dst_count, nchw.N, nchw.C, nchw.H, nchw.W))

	for stab in res.nchw:
		if ("ctx_" in stab.name and (res.src_count > 1)):
			if (force):
				print("bypassing suspected CPU layer warning")
			else:
				raise RuntimeError("uh oh, looks like there's an unresolved CPU layer.\n"
						"              did you really mean %d inputs? use the -f flag to bypass this." % (res.src_count))
	return res


def print_struct(res):
	print('')
	print('static const struct ane_model anec_%s = {' % res.name)
	print('        .name = "%s",' % res.name)
	print('        .input_count = %d,' % res.src_count)
	print('        .output_count = %d,' % res.dst_count)

	print('        .anec = {')
	print('                .size = 0x%x,' % res.size)
	print('                .td_size = 0x%x,' % res.td_size)
	print('                .td_count = 0x%x,' % res.td_count)
	print('                .tsk_size = 0x%x,' % res.tsk_size)
	print('                .krn_size = 0x%x,' % res.krn_size)

	print('                .tiles[0] = %d, /* 0x%x */' % (ntiles(round_up(res.size, TILE_SIZE)), round_up(res.size, TILE_SIZE)))
	for n in range(res.itm_count):
		print('                .tiles[%d] = %d, /* itm%d 0x%x */' % 
		      (3 + n, ntiles(res.itm_sizes[n]), n, res.itm_sizes[n]))
	for n in range(res.dst_count):
		print('                .tiles[%d] = %d, /* dst%d 0x%x */' % 
		      (4 + n, ntiles(res.dst_sizes[n]), n, res.dst_sizes[n]))
	for n in range(res.src_count):
		print('                .tiles[%d] = %d, /* src%d 0x%x */' % 
		      (4 + res.dst_count + n, ntiles(res.src_sizes[n]), n, res.src_sizes[n]))

	print('                .types[%d] = ANE_TILE_CMD,' % (0))
	for n in range(res.itm_count):
		print('                .types[%d] = ANE_TILE_ITM,' % (3 + n))
	for n in range(res.dst_count):
		print('                .types[%d] = ANE_TILE_DST,' % (4 + n))
	for n in range(res.src_count):
		print('                .types[%d] = ANE_TILE_SRC,' % (4 + res.dst_count + n))
	print('        },')

	for n in range(res.dst_count):
		nchw = res.nchw[n + res.src_count]
		print('        .nchw[%d] = {%d, %d, %d, %d, 0x%x, 0x%x}, /* dst%d */' % 
		(4 + n, nchw.N, nchw.C, nchw.H, nchw.W, nchw.pS, nchw.rS, n))

	for n in range(res.src_count):
		nchw = res.nchw[n]
		print('        .nchw[%d] = {%d, %d, %d, %d, 0x%x, 0x%x}, /* src%d */' % 
		(4 + res.dst_count + n, nchw.N, nchw.C, nchw.H, nchw.W, nchw.pS, nchw.rS, n))

	print('};')
	print('')
	return


def wstruct(res, fname):
	with open(fname, "w") as f:
		f.write('#ifndef __ANEC_%s_H__\n' % (res.name.upper()))
		f.write('#define __ANEC_%s_H__\n' % (res.name.upper()))

		cap = io.StringIO()
		with redirect_stdout(cap):
			print_struct(res)
		f.write(cap.getvalue())

		f.write('extern char _binary_%s_anec_start[];\n' % (res.name))
		f.write('extern char _binary_%s_anec_end[];\n' % (res.name))
		f.write('\n')
		f.write('#define ane_init_%s() (ane_init(&anec_%s, &_binary_%s_anec_start))\n' % (res.name, res.name, res.name))
		f.write('void *pyane_init_%s(void) { return ane_init_%s(); }\n' % (res.name, res.name))
		f.write('\n')
		f.write('#endif /* __ANEC_%s_H__ */\n' % (res.name.upper()))
	return


def wdata(res, fname):
	data = open(res.path, "rb").read()
	open(fname, "wb").write(data[res.tsk_start:res.tsk_start+res.size])
	return


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='convert hwx to anec')
	parser.add_argument('hwxpath', type=str, help='path to hwx')
	parser.add_argument('-n', '--name', type=str, help='name')
	parser.add_argument('-o', '--out', type=str, default='', help='outdir prefix')
	parser.add_argument('-a', '--all', action='store_true', help='write all')
	parser.add_argument('-s', '--struct', action='store_true', help='write struct')
	parser.add_argument('-d', '--data', action='store_true', help='write data')
	parser.add_argument('-p', '--print', action='store_true', help='print struct')
	parser.add_argument('-f', '--force', action='store_true', help='bypass warnings')

	args = parser.parse_args()

	if (not args.name):
		args.name = ''.join(os.path.basename(args.hwxpath).rsplit('.hwx', 1))
	args.name = sanitize(args.name).lower()
	print("using name: %s" % args.name)

	res = hwx2anec(args.hwxpath, args.name, args.force)
	if (args.print):
		print_struct(res)

	if (args.struct or args.all):
		fname = os.path.join(args.out, "anec_%s.h" % res.name)
		print("writing struct to %s" % fname)
		wstruct(res, fname)

	if (args.data or args.all):
		fname = os.path.join(args.out, "%s.anec" % res.name)
		print("writing data to %s" % fname)
		wdata(res, fname)
