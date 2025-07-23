API documentation
black-forest-labs/FLUX.1-dev

API Recorder

1 API endpoint


Choose a language to see the code snippets for interacting with the API.

1. Install the python client (docs) if you don't already have it installed.

copy
$ pip install gradio_client
2. Find the API endpoint below corresponding to your desired function in the app. Copy the code snippet, replacing the placeholder values with your own input data. If this is a private Space, you may need to pass your Hugging Face token as well (read more). Or use the 
API Recorder

 to automatically generate your API requests.

api_name: /infer
copy
from gradio_client import Client

client = Client("black-forest-labs/FLUX.1-dev")
result = client.predict(
		prompt="Hello!!",
		seed=0,
		randomize_seed=True,
		width=1024,
		height=1024,
		guidance_scale=3.5,
		num_inference_steps=28,
		api_name="/infer"
)
print(result)
Accepts 7 parameters:
prompt str Required

The input value that is provided in the "Prompt" Textbox component.

seed float Default: 0

The input value that is provided in the "Seed" Slider component.

randomize_seed bool Default: True

The input value that is provided in the "Randomize seed" Checkbox component.

width float Default: 1024

The input value that is provided in the "Width" Slider component.

height float Default: 1024

The input value that is provided in the "Height" Slider component.

guidance_scale float Default: 3.5

The input value that is provided in the "Guidance Scale" Slider component.

num_inference_steps float Default: 28

The input value that is provided in the "Number of inference steps" Slider component.

Returns tuple of 2 elements
[0] dict(path: str | None (Path to a local file), url: str | None (Publicly available url or base64 encoded image), size: int | None (Size of image in bytes), orig_name: str | None (Original filename), mime_type: str | None (mime type of image), is_stream: bool (Can always be set to False), meta: dict(str, Any))

The output value that appears in the "Result" Image component.

[1] float

The output value that appears in the "Seed" Slider component.