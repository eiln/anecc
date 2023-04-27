
# anecc

# WIP (but works on my machine)

> Run a CoreML MLModel on the Asahi Neural Engine

`anecc`, short for "ANE CoreML converter/compiler",
converts and compiles an Apple CoreML MLModel
to a Linux executable compatible with [my new driver](https://github.com/eiln/ane).


# Installation

From pip:

	pip install anecc


From source:

	git clone https://github.com/eiln/anecc
	cd anecc
	make install


Verify installation with:

	$ anecc --help
	Usage: anecc [OPTIONS] PATH

	Options:
	  -n, --name TEXT    Model name.
	  -o, --outdir TEXT  Output directory prefix.
	  -f, --flags TEXT   Additional compiler flags.
	  -c, --c            Compile to C/C++.
	  -p, --python       Compile to Python.
	  -a, --all          Compile to all.
	  --help             Show this message and exit.


# What It Does

On MacOS you can execute a MLModel with:

	import coremltools as ct
	model = ct.models.MLModel("yolov5.mlmodel")


`anecc` compiles a MLModel into either a shared object for Python:

	import ane
	model = ane.Model("yolov5.anec.so")


Or the real deal, a header + object for C/C++/C-likes:

	#include "ane.h"
	#include "anec_yolov5.h"

	int main(void) {
		struct ane_nn *nn = ane_init_yolov5();
		if (nn == NULL) {
			return -1;
		}
		// ...
		ane_free(nn);
		return 0;
	}

Compiles with `gcc` or `g++`:

	g++ -I/usr/include/libane yolov5.anec.o main.c -o main -lane

For details, see [libane.md](https://github.com/eiln/ane/blob/main/libane.md).



# CoreML Conversion

To create or convert your own MLModel,
you need to start in MacOS, where a CoreML runtime is available.

You don't need MacOS to run a pre-converted model.
For that, again, see [libane.md](https://github.com/eiln/ane/blob/main/libane.md).

[TLDR](#tldr) below.


## Step 0. Obtain MLModel

Starting in MacOS-land.
You should have a "*.mlmodel" file ready.
See [coreml101.md](coreml101.md).
I'm continuing "mobilenet.mlmodel" from the torch example.


## Step 1. `tohwx`: Compile MLModel -> hwx


Still in MacOS-land.

I kinda lied about the MLModel part.
When a MLModel file is loaded,

	mlmodel = ct.models.MLModel("mobilenet.mlmodel")

the CoreML backend is called to re-compile the
[model specs](coreml101.md#from-builder)
into one executable on the ANE. Every. Time.
The compiled model is embedded in a macho suffixed "*.hwx".
My guess for the name is "hardware executable".
Sorry "hwx" just isn't as catchy.

Obtain the hwx **under MacOS** using `tohwx`, a slimmed down version of [freedomtan's](https://github.com/freedomtan/coreml_to_ane_hwx) conversion script. Install `tohwx` with:

	git clone https://github.com/eiln/anecc.git
	cd anecc
	make -C tohwx
	make -C tohwx install

Use `tohwx` to convert mlmodel -> hwx:

	$ tohwx mobilenet.mlmodel
	tohwx: input mlmodel: /Users/eileen/mobilenet.mlmodel
	tohwx: output hwx: /Users/eileen/mobilenet.hwx

If it fails, it's usually because of CPU layers, which I can't do anything about. Make a pull, attach the mlmodel, and I'll take a look at it.

You can also call `tohwx` in Python:

	import subprocess
	mlmodel.save("mobilenet.mlmodel")
	subprocess.run(["tohwx", "mobilenet.mlmodel"])


## Step 2. `anecc`: Convert & Compile

`anecc` first internally [converts](anect/anect/__init__.py) the hwx
into a data structure needed by the driver.
Then, the "compilation" portion consists of miscellaneous
`gcc/ld` commands that wrap the data structure nicely.

In other words, the actual work is the conversion.
Since the hwx format is RE'd, the conversion module
runs a lot of asserts/checks.
**Please PR if the conversion fails.**

You can run `anecc` in MacOS to ensure it properly converts,
but it won't generate the compiled objects.
E.g., MacOS:

	$ anecc mobilenet.hwx -a
	anecc::warn: compiling is only supported on Linux.
	anect::info: using name: mobilenet
	anect::info: found input 1/1: (1, 3, 224, 224)
	anect::info: found output 1/1: (1, 1, 1, 1000)
	anecc::warn: Model can convert successfully. Re-run anecc in Linux.

v.s. Linux:

	$ anecc mobilenet.hwx -a
	anect::info: using name: mobilenet
	anect::info: found input 1/1: (1, 3, 224, 224)
	anect::info: found output 1/1: (1, 1, 1, 1000)
	anecc::info: ld -r -b binary -o mobilenet.anec.o mobilenet.anec
	anecc::info: compiling for C/C++...
	anecc::info: gcc -I. -std=gnu99  -I//usr/include/libane -c -o /tmp/tmpffcgxefw/anec_mobilenet.o /tmp/tmpffcgxefw/anec_mobilenet.c
	anecc::info: created object: /home/eileen/mobilenet.anec.o
	anecc::info: created header: /home/eileen/anec_mobilenet.h
	anecc::info: compiling for Python...
	anecc::info: gcc -I. -std=gnu99  -shared -pthread -fPIC -fno-strict-aliasing -I//usr/include/python3.10 -I//usr/include/libane mobilenet.krn.o /tmp/tmpffcgxefw/pyane_mobilenet.c -o /tmp/tmpffcgxefw/mobilenet.anec.so /usr/lib/libane.a
	anecc::info: created dylib: /home/eileen/mobilenet.anec.so


## TLDR

In MacOS,

	tohwx mobilenet.mlmodel

Save the resulting "mobilenet.hwx" to Linux partition.

Then, in Linux,

	anecc mobilenet.hwx -a

