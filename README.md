
# anecc

# UNDER CONSTRUCTION

> Run a CoreML MLModel on the Asahi Neural Engine

`anecc`, short for "ANE CoreML converter/compiler",
converts and compiles an Apple CoreML MLModel
to a Linux executable compatible with [my new driver](https://github.com/eiln/ane).



## Installation

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
	  -p, --python       Compile to python (default C).
	  --help             Show this message and exit.



# What

On MacOS you can execute a MLModel with:

	import coremltools as ct
	model = ct.models.MLModel("yolov5.mlmodel")


`anecc` compiles a MLModel into either a shared object for Python:

	from ane import ANE_MODEL
	model = ANE_MODEL("yolov5.anec.so")


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
		-I/usr/include/anelib -I/usr/bin/anelib/anelib.o \
		yolov5.anec.o main.c -o main.out


Todo. Resolve include paths.



## Conversion

To create or convert your own MLModel,
you need to start in MacOS, where a CoreML runtime is available.
You don't need MacOS to run a pre-converted model.


### Step 0: obtain mlmodel


Starting in MacOS-land.
You should have a "*.mlmodel" file ready.
See [coreml101.md](coreml101.md).
I'm continuing "mobilenet.mlmodel" from the torch example.


### Step 1: mlmodel -> hwx


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


Convert mlmodel -> hwx:


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



### Step 2: hwx -> anec

`anecc` parses the hwx, not mlmodel.
It's nearly free-standing/pure python, with the exception
of `click` to parse command line arguments,
so it's runnable both on macos/Linux. Or Windows. I think.


	$ anecc mobilenet.hwx
	using name: mobilenet
	found input 1/1: (1, 3, 224, 224)
	found output 1/1: (1, 1, 1, 1000)
	writing struct to anec_mobilenet.h
	writing data to mobilenet.anec
	writing pyane to pyane_mobilenet.h


Please PR if you encounter errors.



### Step 3: execute!


On Linux now, obviously ;).

See [aneex](https://github.com/eiln/aneex).

- C-API examples: [aneex/compute](https://github.com/eiln/aneex/tree/main/compute)
- Python/notebook examples: [aneex/vision](https://github.com/eiln/aneex/tree/main/vision)

