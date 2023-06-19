
# anecc

`anecc`, short for "ANE CoreML converter/compiler", cuts the middleman to let you directly run a CoreML MLModel on the Neural Engine with [my reverse-engineered Linux driver](https://github.com/eiln/ane).


# Installation

From pip:

```
pip install anecc
```

From source:

```
git clone https://github.com/eiln/anecc.git
cd anecc
make install
```

Verify installation:

```
Usage: anecc [OPTIONS] PATH

Options:
  -n, --name TEXT  Model name
  -o, --out TEXT   Output file name (default $name.anec)
  -w, --write      Write anec.
  -p, --print      Print struct.
  -f, --force      Bypass warnings.
  --help           Show this message and exit.
```


# What It Does

On macOS, an MLModel file would be loaded with:

```
import coremltools as ct
model = ct.models.MLModel("yolov5.mlmodel")
```

`anecc` converts the MLModel into a custom `anec` format that's even easier to load on Linux:

```
import ane
model = ane.model("yolov5.anec")
```

You'll notice load times are a lot faster than CoreML. And the Python "library" being a mere [50 LOC](https://github.com/eiln/ane/blob/main/bindings/python/python/ane/__init__.py) wrapper around the lightweight gnu99 [C userspace driver library](https://github.com/eiln/ane/blob/main/libane). That's because you actually own your own model.

```
#include "ane.h"

int main(void) {
	struct ane_nn *nn = ane_init("yolov5.anec");
	if (nn == NULL) {
		return -1;
	}
	// ...
	ane_free(nn);
	return 0;
}
```

Compile with `gcc` or `g++`:

```
g++ -I/usr/include/libane main.c -o main -lane
```


# CoreML Conversion

To create or convert your own MLModel, you need to start in macOS, where a CoreML runtime is available. You do not need macOS to run a pre-converted ".anec" model.

[TLDR](#tldr) at the bottom.


### Step 0. obtain MLModel

Starting in macOS-land. You should have a "*.mlmodel" file ready. Do not use "mlpackages".

See [coreml101.md](coreml101.md).


### Step 1. `tohwx`: Compile mlmodel -> hwx

Still in macOS-land.

I kinda lied about the MLModel part. When an MLModel is loaded,

```
mlmodel = ct.models.MLModel("yolov5.mlmodel")
```

the CoreML backend is called to deserialize, convert, and compile the model into a microcode executable on the ANE. Every. Time. I'm unsure whether the concept of "caching" is absent out of apathy, inability, or secrecy. The compiled model, which we must extract, is embedded in a macho suffixed "*.hwx". My guess is "hardware executable".

Extract the hwx **under macOS** using `tohwx`, a slimmed down version of [freedomtan's](https://github.com/freedomtan/coreml_to_ane_hwx) obj-c conversion script. Install `tohwx` with:

```
git clone https://github.com/eiln/anecc.git
cd anecc
make -C tohwx
make -C tohwx install
```

Use `tohwx` to convert mlmodel -> hwx:

```
$ tohwx yolov5.mlmodel
tohwx: input mlmodel: /Users/eileen/yolov5.mlmodel
tohwx: output hwx: /Users/eileen/yolov5.hwx
```

If it fails, sorry, I don't know. Make a pull, attach the mlmodel, and I'll take a look at it.


### Step 2. `anecc`: convert hwx -> anec

`anecc` is platform independent. You can also use it to check conversion ability or debug the model.

```
anecc yolov5.hwx -o yolov5.anec
```


# TLDR

In macOS:

```
tohwx yolov5.mlmodel
```

In macOS or Linux or Windows or whatever:

```
anecc yolov5.hwx -o yolov5.anec
```

Use the yolov5.anec with libane.
