# Introduction

> Welcome to the ElevenLabs API reference.

## Installation

You can interact with the API through HTTP or Websocket requests from any language, via our official Python bindings or our official Node.js libraries.

To install the official Python bindings, run the following command:

```bash
pip install elevenlabs
```

To install the official Node.js library, run the following command in your Node.js project directory:

```bash
npm install @elevenlabs/elevenlabs-js
```

<div id="overview-wave">
  <ElevenLabsWaveform color="gray" />
</div>
---
title: Authentication
hide-feedback: true
---

## API Keys

The ElevenLabs API uses API keys for authentication. Every request to the API must include your API key, used to authenticate your requests and track usage quota.

Each API key can be scoped to one of the following:

1. **Scope restriction:** Set access restrictions by limiting which API endpoints the key can access.
2. **Credit quota:** Define custom credit limits to control usage.

**Remember that your API key is a secret.** Do not share it with others or expose it in any client-side code (browsers, apps).

All API requests should include your API key in an `xi-api-key` HTTP header as follows:

```bash
xi-api-key: ELEVENLABS_API_KEY
```

### Making requests

You can paste the command below into your terminal to run your first API request. Make sure to replace `$ELEVENLABS_API_KEY` with your secret API key.

```bash
curl 'https://api.elevenlabs.io/v1/models' \
  -H 'Content-Type: application/json' \
  -H 'xi-api-key: $ELEVENLABS_API_KEY'
```

Example with the `elevenlabs` Python package:

```python
from elevenlabs.client import ElevenLabs

elevenlabs = ElevenLabs(
  api_key='YOUR_API_KEY',
)
```

Example with the `elevenlabs` Node.js package:

```javascript
import { ElevenLabsClient } from '@elevenlabs/elevenlabs-js';

const elevenlabs = new ElevenLabsClient({
  apiKey: 'YOUR_API_KEY',
});
```
---
title: Streaming
---

The ElevenLabs API supports real-time audio streaming for select endpoints, returning raw audio bytes (e.g., MP3 data) directly over HTTP using chunked transfer encoding. This allows clients to process or play audio incrementally as it is generated.

Our official [Node](https://github.com/elevenlabs/elevenlabs-js) and [Python](https://github.com/elevenlabs/elevenlabs-python) libraries include utilities to simplify handling this continuous audio stream.

Streaming is supported for the [Text to Speech API](/docs/api-reference/streaming), [Voice Changer API](/docs/api-reference/speech-to-speech-streaming) & [Audio Isolation API](/docs/api-reference/audio-isolation-stream). This section focuses on how streaming works for requests made to the Text to Speech API.

In Python, a streaming request looks like:

```python
from elevenlabs import stream
from elevenlabs.client import ElevenLabs

elevenlabs = ElevenLabs()

audio_stream = elevenlabs.text_to_speech.stream(
    text="This is a test",
    voice_id="JBFqnCBsd6RMkjVDRZzb",
    model_id="eleven_multilingual_v2"
)

# option 1: play the streamed audio locally
stream(audio_stream)

# option 2: process the audio bytes manually
for chunk in audio_stream:
    if isinstance(chunk, bytes):
        print(chunk)
```

In Node / Typescript, a streaming request looks like:

```javascript maxLines=0
import { ElevenLabsClient, stream } from '@elevenlabs/elevenlabs-js';
import { Readable } from 'stream';

const elevenlabs = new ElevenLabsClient();

async function main() {
  const audioStream = await elevenlabs.textToSpeech.stream('JBFqnCBsd6RMkjVDRZzb', {
    text: 'This is a test',
    modelId: 'eleven_multilingual_v2',
  });

  // option 1: play the streamed audio locally
  await stream(Readable.from(audioStream));

  // option 2: process the audio manually
  for await (const chunk of audioStream) {
    console.log(chunk);
  }
}

main();
```
https://elevenlabs.io/docs/api-reference/introduction

---
title: Python SDK
subtitle: 'Conversational AI SDK: deploy customized, interactive voice agents in minutes.'
---

<Info>Also see the [Conversational AI overview](/docs/conversational-ai/overview)</Info>

## Installation

Install the `elevenlabs` Python package in your project:

```shell
pip install elevenlabs
# or
poetry add elevenlabs
```

If you want to use the default implementation of audio input/output you will also need the `pyaudio` extra:

```shell
pip install "elevenlabs[pyaudio]"
# or
poetry add "elevenlabs[pyaudio]"
```

<Info>
The `pyaudio` package installation might require additional system dependencies.

See [PyAudio package README](https://pypi.org/project/PyAudio/) for more information.

<Tabs>
<Tab title="Linux">
On Debian-based systems you can install the dependencies with:

```shell
sudo apt-get update
sudo apt-get install libportaudio2 libportaudiocpp0 portaudio19-dev libasound-dev libsndfile1-dev -y
```

</Tab>
<Tab title="macOS">
On macOS with Homebrew you can install the dependencies with:
```shell
brew install portaudio
```
</Tab>
</Tabs>
</Info>

## Usage

In this example we will create a simple script that runs a conversation with the ElevenLabs Conversational AI agent.
You can find the full code in the [ElevenLabs examples repository](https://github.com/elevenlabs/elevenlabs-examples/tree/main/examples/conversational-ai/python).

First import the necessary dependencies:

```python
import os
import signal

from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
```

Next load the agent ID and API key from environment variables:

```python
agent_id = os.getenv("AGENT_ID")
api_key = os.getenv("ELEVENLABS_API_KEY")
```

The API key is only required for non-public agents that have authentication enabled.
You don't have to set it for public agents and the code will work fine without it.

Then create the `ElevenLabs` client instance:

```python
elevenlabs = ElevenLabs(api_key=api_key)
```

Now we initialize the `Conversation` instance:

```python
conversation = Conversation(
    # API client and agent ID.
    elevenlabs,
    agent_id,

    # Assume auth is required when API_KEY is set.
    requires_auth=bool(api_key),

    # Use the default audio interface.
    audio_interface=DefaultAudioInterface(),

    # Simple callbacks that print the conversation to the console.
    callback_agent_response=lambda response: print(f"Agent: {response}"),
    callback_agent_response_correction=lambda original, corrected: print(f"Agent: {original} -> {corrected}"),
    callback_user_transcript=lambda transcript: print(f"User: {transcript}"),

    # Uncomment if you want to see latency measurements.
    # callback_latency_measurement=lambda latency: print(f"Latency: {latency}ms"),
)
```

We are using the `DefaultAudioInterface` which uses the default system audio input/output devices for the conversation.
You can also implement your own audio interface by subclassing `elevenlabs.conversational_ai.conversation.AudioInterface`.

Now we can start the conversation:

```python
conversation.start_session()
```

To get a clean shutdown when the user presses `Ctrl+C` we can add a signal handler which will call `end_session()`:

```python
signal.signal(signal.SIGINT, lambda sig, frame: conversation.end_session())
```

And lastly we wait for the conversation to end and print out the conversation ID (which can be used for reviewing the conversation history and debugging):

```python
conversation_id = conversation.wait_for_session_end()
print(f"Conversation ID: {conversation_id}")
```

All that is left is to run the script and start talking to the agent:

```shell
# For public agents:
AGENT_ID=youragentid python demo.py

# For private agents:
AGENT_ID=youragentid ELEVENLABS_API_KEY=yourapikey python demo.py
```
