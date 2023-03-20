
# anecc

# WIP (but works on my machine)

> Run a CoreML MLModel on the Asahi Neural Engine

`anecc`, short for "ANE CoreML converter/compiler",
converts and compiles an Apple CoreML MLModel
to a Linux executable compatible with [my new driver](https://github.com/eiln/ane).

Bindings are currently available for 
[C](#c),
[C++](#c-1),
[Python](#python).


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
	  -c, --c            Compile to C (default).
	  -d, --cpp          Compile to C++.
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


Or the real deal, a header + object for C/C-likes:

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

Compiled with:

	gcc -I/usr/include/libdrm -I/usr/include/accel?/idk \
		-I/usr/include/libane /usr/lib/libane.o \
		yolov5.anec.o main.c -o main.out


TODO. Resolve kernel driver include path.

For details, see [Usage](#usage).



# Conversion

To create or convert your own MLModel,
you need to start in MacOS, where a CoreML runtime is available.

You don't need MacOS to run a pre-converted model.
For that, see [Usage](#usage).

[TLDR](#tldr) below.


### Step 0. Obtain MLModel

Starting in MacOS-land.
You should have a "*.mlmodel" file ready.
See [coreml101.md](coreml101.md).
I'm continuing "mobilenet.mlmodel" from the torch example.


### Step 1. coreml2hwx: MLModel -> hwx


Still in MacOS-land.

I kinda lied about the MLModel part.
When a MLModel file is loaded,

	mlmodel = ct.models.MLModel("path/to/model.mlmodel")

the CoreML backend is called to re-compile the
model specs into one executable on the ANE. Every. Time.
The compiled model is embedded in a macho suffixed "*.hwx".
My guess for the name is "hardware executable".
Sorry "hwx" just isn't as catchy.

Obtain the hwx **under MacOS** using 
[freedomtan's](https://github.com/freedomtan/coreml_to_ane_hwx) `coreml2hwx`
conversion script, which can be installed with:

	git clone https://github.com/eiln/coreml_to_ane_hwx
	cd coreml_to_ane_hwx
	make install

Use `coreml2hwx` to convert mlmodel -> hwx:

	$ coreml2hwx mobilenet.mlmodel 
	2023-02-15 10:45:59.466 coreml2hwx[986:9634] original mlmodel file: file:///Users/eileen/mobilenet.mlmodel 
	2023-02-15 10:45:59.602 coreml2hwx[986:9634] espresso model in mlmodelc directory: /var/folders/wl/v5_h4f8x7ddc0cr8cpzb0clm0000gn/T/mobilenet.mlmodelc/model.espresso.net 
	2023-02-15 10:45:59.902 coreml2hwx[986:9634] options:
	{
	    InputNetworks =     (
	                {
	            NetworkPlistName = "net.plist";
	            NetworkPlistPath = "/tmp/espresso_ir_dump/";
	        }
	    );
	    OutputFileName = "model.hwx";
	    OutputFilePath = "/tmp/hwx_output/mobilenet/";
	}
	2023-02-15 10:45:59.902 coreml2hwx[986:9634] result at /tmp/hwx_output/mobilenet/model.hwx


On success should print the hwx path:

	cp /tmp/hwx_output/mobilenet/model.hwx mobilenet.hwx

If it doesn't, sorry, I don't know.
Send me the mlmodel and I'll take a look at it.


### Step 2. anecc: Convert & Compile

`anecc` first internally [converts](anect/anect/__init__.py) the hwx
into a [data structure](https://github.com/eiln/ane/blob/main/ane/src/include/drm_ane.h)
needed by the driver.
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
	anect::info: writing header to /tmp/tmpo_kkogf1/anec_mobilenet.h
	anect::info: writing binary to /tmp/tmpo_kkogf1/mobilenet.anec
	anecc::info: ld -r -b binary -o mobilenet.anec.o mobilenet.anec
	anecc::info: compiling for C...
	anecc::info: created header: /home/eileen/anec_mobilenet.h
	anecc::info: created object: /home/eileen/mobilenet.anec.o
	anecc::info: compiling for C++...
	anecc::info: gcc -I//usr/include/libdrm -I//home/eileen/ane/ane/src/include -I//usr/include/libane -c -o /tmp/tmpo_kkogf1/anecpp_mobilenet.o /tmp/tmpo_kkogf1/anecpp_mobilenet.c
	anecc::info: created cpp object: /home/eileen/anecpp_mobilenet.o
	anecc::info: created hpp header: /home/eileen/anecpp_mobilenet.hpp
	anecc::info: compiling for Python...
	anecc::info: gcc -shared -pthread -fPIC -fno-strict-aliasing -I. -I//usr/include/python3.10 -I//usr/include/libdrm -I//home/eileen/ane/ane/src/include -I//usr/include/libane /usr/lib/libane.o mobilenet.anec.o /tmp/tmpo_kkogf1/pyane_mobilenet.c -o /tmp/tmpo_kkogf1/mobilenet.anec.so
	anecc::info: created dylib oject: /home/eileen/mobilenet.anec.so


## TLDR

In MacOS,

	coreml2hwx mobilenet.mlmodel
	cp /tmp/hwx_output/mobilenet/model.hwx mobilenet.hwx

Save the "mobilenet.hwx" to Linux partition. 

Then, in Linux,

	anecc mobilenet.hwx


# Usage

### C

	anecc --c yolov5.hwx

Generates 

	anec_$name.h, $name.anec.o


The header defines `anec_init_$name()`,
which can be used as:

	#include "ane.h"
	#include "anec_yolov5.h" // anec_$name.h 

	int main(void) {
		struct ane_nn *nn = ane_init_yolov5(); // anec_init_$name()
		if (nn == NULL) {
			return -1;
		}
		// ...
		ane_free(nn);
		return 0;
	}

Compile with:

	gcc -I/usr/include/libdrm -I/usr/include/accel?/idk \
		-I/usr/include/libane /usr/lib/libane.o \
		yolov5.anec.o main.c -o main.out

See the `libane` [source](https://github.com/eiln/ane/tree/main/libane).
TODO. Document this.


### C++

	anecc --cpp yolov5.hwx

Generates 

	anecpp_$name.hpp, $name.anec.o, anecpp_$name.o


The header defines `anecpp_init_$name()`,
which can be used as:

	#include "ane.h"
	#include "anecpp_yolov5.hpp" // anecpp_$name.hpp

	int main(void) {
		struct ane_nn *nn = anecpp_init_yolov5(); // anecpp_init_$name()
		if (nn == NULL) {
			return -1;
		}
		// ...
		ane_free(nn);
		return 0;
	}

Compile with:

	g++ -I/usr/include/libdrm -I/usr/include/accel?/idk \
		-I/usr/include/libane /usr/lib/libane.o \
		yolov5.anec.o anecpp_yolov5.o main.cpp -o main.out

Other `libane` functions are the same as C.


### Python

	anecc --python yolov5.hwx

Generates 

	$name.anec.so


Backend is the [ane](https://github.com/eiln/ane/tree/main/python)
package, which can be installed with:

	pip install ane


Load the dylib with:

	import ane  # pip install ane
	model = ane.Model("yolov5.anec.so")  # $name.anec.so 


### Jupyter Notebook

Everything is the same as normal Python,
but you NEED to **RESTART THE KERNEL**
(mine is the circle arrow button on Firefox)
**when finished** or you WILL **RUN OUT OF RESOURCES**.

