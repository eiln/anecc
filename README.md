
# anec.py

> Run a coreml *.mlmodel on the Asahi Neural Engine


`anec.py` is a python script to convert
an Apple CoreML mlmodel to a Linux executable --
[with my new driver, of course :)](https://github.com/eiln/ane).




## Installation

	git clone https://github.com/eiln/anec.py
	cd anec.py
	make install




## Conversion


### Step 0: obtain mlmodel


Starting in macos-land.
You should have a "*.mlmodel" file ready.
See [coreml101.md](coreml101.md).
I'm continuing "mobilenet.mlmodel" from the torch example.


### Step 1: mlmodel -> hwx


Still in macos-land.

I kinda lied about the mlmodel part.
When a mlmodel file is loaded,


	mlmodel = ct.models.MLModel("path/to/model.mlmodel")


the CoreML backend is called to re-compile the
model specs into one executable on the ANE. Every. Time.
The compiled model is embedded in a macho suffixed "*.hwx".
My guess for the name is "hardware executable".

Obtain the hwx **under macos** using 
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


`anec.py` parses the hwx, not mlmodel.
It's free-standing/pure python, so runnable both on macos/Linux.
Or Windows. I think.


	$ anec.py mobilenet.hwx -a
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

