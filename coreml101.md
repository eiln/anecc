

# coreml101


	import coremltools as ct  # pip install coremltools



## From pytorch

First load a torch model as normal.
E.g. pretrained from hub:

	model = torch.hub.load('pytorch/vision:v0.11.0', 'fcn_resnet50', pretrained=True).eval()
	model = torchvision.models.mobilenet_v2(pretrained=True).eval()

or a custom torch.nn module:

	class Log10(nn.Module):
	    def __init__(self):
		super(Log10, self).__init__()
	    def forward(self, x):
		x = torch.log10(x)  # pure torch functions
		return x
	model = Log10().eval()


The forward pass must be composed of pure torch functions,
i.e. no numpy or python len().
To see all available torch ops:

	curl https://raw.githubusercontent.com/apple/coremltools/main/coremltools/converters/mil/frontend/torch/ops.py  \
		| grep "@register_torch_op" -A 1 | grep "^def"


Extract key in inherited module it complains about dict outputs:

	class FCNWrap(nn.Module):
	    def __init__(self):
	        super(FCNWrap, self).__init__()
	        self.model = torch.hub.load('pytorch/vision:v0.11.0', fcn_resnet50').eval()
	    def forward(self, x):
	        res = self.model(x)
	        x = res["out"]
	        return x
	model = FCNWrap().eval()


Finally, convert:

	input = torch.rand(1, 3, 224, 224)  # use correct shape
	trace = torch.jit.trace(model, input)

	mlmodel = ct.convert(trace, inputs=[name="x", ct.TensorType(shape=input.shape)])
	mlmodel.save("model.mlmodel")


Simple runnable example:

	import torch
	import torchvision
	import coremltools as ct

	model = torchvision.models.mobilenet_v2(pretrained=True).eval()
	input = torch.rand(1, 3, 224, 224) 
	trace = torch.jit.trace(model, input)

	mlmodel = ct.convert(trace, inputs=[name="x", ct.TensorType(shape=input.shape)])
	mlmodel.save("mobilenet.mlmodel")



## From MB


	from coremltools.converters.mil import Builder as mb


As the torch/ops.py source from above shows,
torch conversion comes down to resolving torch ops -> MB ops:

	@register_torch_op
	def true_divide(context, node):
	    inputs = _get_inputs(context, node, expected=2)
	    res = mb.real_div(x=inputs[0], y=inputs[1], name=node.name)
	    context.add(res)


MB is a convinience decorator around Builder.
It's nice for extracting isolated compute passes, e.g.,


	@mb.program(input_specs=[mb.TensorSpec(shape=(512, 640))])
	def sqrt(x):
	    x = mb.sqrt(x=x)
	    return x


Two inputs:

	@mb.program(input_specs=[mb.TensorSpec(shape=(123, 456)), mb.TensorSpec(shape=(456, 789)),])
	def matmul(x, y):
	    x = mb.matmul(x=x, y=y)
	    return x


Convert with decorated function name:

	mlmodel = ct.convert(matmul)


To see all MB ops,

	curl https://raw.githubusercontent.com/apple/coremltools/main/coremltools/converters/mil/backend/nn/op_mapping.py \
		| grep "@register_mil_to_nn_mapping" -A 1 | grep "^def"



P.S. if anyone with enough time and SSD 
is willing to mass convert matmul kernels do lmk.



## From Builder

	from coremltools.models.neural_network import NeuralNetworkBuilder
	from coremltools.models import neural_network, datatypes


All the conversion methods essentially come down to building the model "spec".
The model spec is a DAG graph of passes connected by dict keys.
When ct.models.MLModel(spec) is called, the spec, formatted as an XML/plist,
is fed into ANECompiler.

The raw interface to this spec-building is NeuralNetworkBuilder.
It's verbose as shit and really fucking anal about dict key names.
Why passes aren't positional I don't know.
I totally see MB being born out of this concern.
Use MB if you can, but Builder does grant the finest control.


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
	cube = builder.spec


There is no conversion

	mlmodel = ct.models.MLModel(cube)

because it's the raw entrypoint to the xml IR.

