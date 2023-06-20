
# coreml101: Conversion Options

Conversion is:

	import coremltools as ct  # pip install coremltools
	model = ct.convert(source_model)

With three options for `source_model`:

1. [From pytorch](#from-pytorch) -- recommended for neural networks
2. [From mb](#from-mb) -- recommended for simpler compute passes
3. [From builder](#from-builder)


**WARNING:** Do NOT pass additional params for `ct.convert()`, notably

	convert_to="mlprogram",
	minimum_deployment_target=ct.target.iOS15,
	compute_precision=ct.precision.FLOAT32,

Playing with the Python coremltools frontend won't increase chances of ANE compilation. CoreML *always* prioritizes ANE execution, without you telling it, because it's inherently more speed and energy efficient. Additional flags passed will only be an unintentional CPU-only signal. When conversion fails, the model suffers from a hardware limitation, requiring surgery. For that, see [coreml102.md](https://github.com/eiln/anecc/blob/main/coreml102.md). Only pass what's needed.

Create a pull if these methods don't work. I'll look at it and update docs.



### From PyTorch

Load a torch model as normal, e.g. pretrained from torch hub:

	model = torch.hub.load('pytorch/vision:v0.11.0', 'fcn_resnet50', pretrained=True).eval()
	model = torchvision.models.mobilenet_v2(pretrained=True).eval()


Or a custom torch.nn module:

	class Log10(nn.Module):
	    def __init__(self):
		super(Log10, self).__init__()
	    def forward(self, x):
		x = torch.log10(x)  # pure torch functions
		return x
	model = Log10().eval()


The forward pass must be composed of pure torch functions, i.e. no numpy or len(). To see all available torch ops:

	curl https://raw.githubusercontent.com/apple/coremltools/main/coremltools/converters/mil/frontend/torch/ops.py  \
		| grep "@register_torch_op" -A 1 | grep "^def"


Finally, convert:

	input = torch.rand(1, 3, 224, 224)  # use correct shape
	trace = torch.jit.trace(model, input)

	mlmodel = ct.convert(trace, inputs=[ct.TensorType(name="x", shape=input.shape)])
	mlmodel.save("model.mlmodel")


Simple runnable example using pretrained weights:

	import coremltools as ct
	import torch
	import torchvision

	model = torchvision.models.mobilenet_v2(pretrained=True).eval()
	input = torch.rand(1, 3, 224, 224) 
	trace = torch.jit.trace(model, input)

	mlmodel = ct.convert(trace, inputs=[ct.TensorType(name="x", shape=input.shape)])
	mlmodel.save("mobilenet.mlmodel")


Another runnable example using two inputs:

	import coremltools as ct
	import torch
	import torch.nn as nn

	class Atan2(nn.Module):
	    def __init__(self):
	        super(Atan2, self).__init__()
	    def forward(self, x, y):
	        x = torch.atan2(x, y)
	        return x
	model = Atan2().eval()

	input = [torch.rand(1024, 2048), torch.rand(1024, 2048)]  # list of tensors
	trace = torch.jit.trace(model, input)

	mlmodel = ct.convert(trace, inputs=[ct.TensorType(name="x", shape=input[0].shape),
                                            ct.TensorType(name="y", shape=input[1].shape)])
	mlmodel.save("atan2.mlmodel")



### From MB

	from coremltools.converters.mil import Builder as mb


Torch conversion comes down to resolving torch ops into MB ops:

	@register_torch_op
	def true_divide(context, node):
	    inputs = _get_inputs(context, node, expected=2)
	    res = mb.real_div(x=inputs[0], y=inputs[1], name=node.name)
	    context.add(res)


MB is a convinience decorator around Builder. It's nice for extracting isolated compute passes like:

	@mb.program(input_specs=[mb.TensorSpec(shape=(512, 640))])
	def sqrt(x):
	    x = mb.sqrt(x=x)
	    return x


Two inputs:

	@mb.program(input_specs=[mb.TensorSpec(shape=(123, 456)),
				 mb.TensorSpec(shape=(456, 789)),])
	def matmul(x, y):
	    x = mb.matmul(x=x, y=y)
	    return x


Convert with decorated function name:

	mlmodel = ct.convert(matmul)


To see all MB ops,

	curl https://raw.githubusercontent.com/apple/coremltools/main/coremltools/converters/mil/backend/nn/op_mapping.py \
		| grep "@register_mil_to_nn_mapping" -A 1 | grep "^def"


Runnable example for element-wise addition:

	import coremltools as ct
	from coremltools.converters.mil import Builder as mb

	@mb.program(input_specs=[mb.TensorSpec(shape=(123, 456)),
				 mb.TensorSpec(shape=(123, 456)),])
	def add(x, y):
	    x = mb.add(x=x, y=y)
	    return x

	mlmodel = ct.convert(add)



### From Builder

	from coremltools.models.neural_network import NeuralNetworkBuilder
	from coremltools.models import neural_network, datatypes


All the conversion methods essentially come down to building the model "spec", a DAG (graph) of passes connected by dict keys. When ct.models.MLModel(spec) is called, the spec, formatted as an XML/plist, is fed into ANECompiler.

The raw interface to this spec-building is NeuralNetworkBuilder. True to its name, it's verbose as fuck and really fucking anal about dict key names. Perhaps there is a deeper philosophy behind passes not being positional. MB was most definitely born out of the misery of Builder. Use MB if you can, but Builder, the lowest level, does grant the finest control.

	input_features = [("x", datatypes.Array(*(10, 20, 30)))]
	output_features = [("output", None)]
	builder = NeuralNetworkBuilder(input_features, output_features, disable_rank5_shape_mapping=True)
	builder.add_unary(
	            name="cube",
	            mode="power",
	            alpha=3,
	            input_name="x",
	            output_name="output",
	        )

There is no conversion

	mlmodel = ct.models.MLModel(builder.spec)

because it's the raw entrypoint to the xml IR.

