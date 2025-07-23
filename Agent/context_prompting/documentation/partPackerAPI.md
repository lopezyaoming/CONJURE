API documentation
nvidia/PartPacker

API Recorder

3 API endpoints


Choose one of the following ways to interact with the API.

1. Install the python client (docs) if you don't already have it installed.

copy
$ pip install gradio_client
2. Find the API endpoint below corresponding to your desired function in the app. Copy the code snippet, replacing the placeholder values with your own input data. If this is a private Space, you may need to pass your Hugging Face token as well (read more). Or use the 
API Recorder

 to automatically generate your API requests.

api_name: /process_image
copy
from gradio_client import Client, handle_file

client = Client("nvidia/PartPacker")
result = client.predict(
		image_path=handle_file('https://raw.githubusercontent.com/gradio-app/gradio/main/test/test_files/bus.png'),
		api_name="/process_image"
)
print(result)
Accepts 1 parameter:
image_path dict(path: str | None (Path to a local file), url: str | None (Publicly available url or base64 encoded image), size: int | None (Size of image in bytes), orig_name: str | None (Original filename), mime_type: str | None (mime type of image), is_stream: bool (Can always be set to False), meta: dict(str, Any)) Required

The input value that is provided in the "Input Image" Image component. For input, either path or url must be provided. For output, path is always provided.

Returns 1 element
dict(path: str | None (Path to a local file), url: str | None (Publicly available url or base64 encoded image), size: int | None (Size of image in bytes), orig_name: str | None (Original filename), mime_type: str | None (mime type of image), is_stream: bool (Can always be set to False), meta: dict(str, Any))

The output value that appears in the "Segmentation Result" Image component.

api_name: /get_random_seed
copy
from gradio_client import Client

client = Client("nvidia/PartPacker")
result = client.predict(
		randomize_seed=True,
		seed=0,
		api_name="/get_random_seed"
)
print(result)
Accepts 2 parameters:
randomize_seed bool Default: True

The input value that is provided in the "Randomize seed" Checkbox component.

seed float Default: 0

The input value that is provided in the "Seed" Slider component.

Returns 1 element
float

The output value that appears in the "Seed" Slider component.

api_name: /process_3d
copy
from gradio_client import Client, handle_file

client = Client("nvidia/PartPacker")
result = client.predict(
		input_image=handle_file('https://raw.githubusercontent.com/gradio-app/gradio/main/test/test_files/bus.png'),
		num_steps=50,
		cfg_scale=7,
		grid_res=384,
		seed=0,
		simplify_mesh=False,
		target_num_faces=100000,
		api_name="/process_3d"
)
print(result)
Accepts 7 parameters:
input_image dict(path: str | None (Path to a local file), url: str | None (Publicly available url or base64 encoded image), size: int | None (Size of image in bytes), orig_name: str | None (Original filename), mime_type: str | None (mime type of image), is_stream: bool (Can always be set to False), meta: dict(str, Any)) Required

The input value that is provided in the "Segmentation Result" Image component. For input, either path or url must be provided. For output, path is always provided.

num_steps float Default: 50

The input value that is provided in the "Inference steps" Slider component.

cfg_scale float Default: 7

The input value that is provided in the "CFG scale" Slider component.

grid_res float Default: 384

The input value that is provided in the "Grid resolution" Slider component.

seed float Default: 0

The input value that is provided in the "Seed" Slider component.

simplify_mesh bool Default: False

The input value that is provided in the "Simplify mesh" Checkbox component.

target_num_faces float Default: 100000

The input value that is provided in the "Face number" Slider component.

Returns 1 element
filepath

The output value that appears in the "Geometry" Model3d component.