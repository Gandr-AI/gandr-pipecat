# Pipecat Gandr TTS

Official [Gandr](https://gandr.ai) text-to-speech integration for
[Pipecat](https://github.com/pipecat-ai/pipecat), the framework for building
voice and multimodal conversational agents.

> **Note**: This integration is maintained by Gandr. As the provider of the TTS
> service, we keep it current with Pipecat releases and with our own API.

## Table of Contents

- [Why Gandr](#why-gandr)
- [Pipecat compatibility](#pipecat-compatibility)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Voices](#voices)
- [How the integration works](#how-the-integration-works)
- [Interruptions](#interruptions)
- [Long text](#long-text)
- [Errors](#errors)
- [Metrics](#metrics)
- [Pricing](#pricing)
- [Environment variables](#environment-variables)
- [Examples](#examples)
- [Requirements](#requirements)
- [License](#license)
- [Support](#support)

---

## Why Gandr

**Audio streams back as it is generated.** The first bytes arrive while the rest
of the utterance is still rendering, so a pipeline can start playback instead of
waiting on a finished clip.

**WER 1.982%, against a 2.171% human baseline.** One `whisper-large-v3` scorer
transcribed everything, including the human baseline, so the two numbers are
comparable. n=1,088, zero render errors.

## Pipecat compatibility

**Tested with Pipecat v1.7.0** on Python 3.12.11 (2026-08-07): clean virtual
environment, `pip install` exit 0, imports, 11/11 unit tests pass, service
constructs.

Built against the `WebsocketTTSService` base class and the audio-context API,
so it supports `pipecat-ai` from `0.0.108` up to (but not including) `2.0.0`.
The declared floor is `0.0.108` because that is what it was written against;
the tested figure above crosses a major version and about a year of API drift,
which is the number worth trusting.

Not claimed: no live socket has been opened against the service in that test.
It covers install, import, unit tests and construction. Rendering audio costs
money, so it is left to whoever runs it.

## Installation

```bash
uv add pipecat-gandr
```

or with pip:

```bash
pip install pipecat-gandr
```

### From source

```bash
git clone https://github.com/Gandr-AI/gandr-pipecat.git
cd gandr-pipecat
pip install -e .
```

## Quick start

### 1. Get an API key

Keys are `gnd_…` strings. See [gandr.ai/docs](https://gandr.ai/docs).

### 2. Basic usage

```python
import os

from pipecat_gandr import GandrTTSService

tts = GandrTTSService(
    api_key=os.getenv("GANDR_API_KEY"),
    params=GandrTTSService.InputParams(
        voice_id="gandr-mia",
        language="en",
        sample_rate=24000,
    ),
)
```

### 3. In a pipeline

```python
pipeline = Pipeline(
    [
        transport.input(),
        stt,
        context_aggregator.user(),
        llm,
        tts,
        transport.output(),
        context_aggregator.assistant(),
    ]
)
```

A complete runnable pipeline is in
[`examples/foundational/gandr_tts_basic.py`](./examples/foundational/gandr_tts_basic.py).

## Configuration

`GandrTTSService.InputParams`:

| Parameter | Type | Default | Range / options | Description |
|---|---|---|---|---|
| `voice_id` | `str` | `"gandr-mia"` | a stock id, or a `gnd:` clone id | Voice for synthesis |
| `language` | `str` | `"en"` | ISO language code | Language of the input text |
| `sample_rate` | `int` | `24000` | `8000`, `16000`, `22050`, `24000` | Output rate. Takes priority over a `sample_rate` passed to the constructor |
| `speed` | `float` | `None` | `0.6` to `1.5` | Playback speed, pitch preserving |
| `volume` | `float` | `None` | `0.5` to `2.0` | Output gain, soft-ceiling mastered |
| `temperature` | `float` | `None` |, | Expression control. Omit and the API chooses |
| `cfg_weight` | `float` | `None` |, | Expression control. Omit and nothing is sent |
| `seed` | `int` | `None` |, | Fixes the render for a reproducible result |
| `voice_wav_b64` | `str` | `None` | base64 WAV | Reference audio for a cloned voice |

Constructor arguments beyond `api_key` and `params`:

| Argument | Default | Description |
|---|---|---|
| `url` | `wss://tts.gandr.ai/ws` | Streaming endpoint |
| `text_aggregation_mode` | `None` | How Pipecat aggregates text before synthesis |
| `utterance_timeout_s` | `30.0` | How long to wait for an utterance's closing frame |
| `busy_retry_s` | `0.5` | Wait before retrying after the server answers `busy` |
| `max_attempts` | `3` | Attempts per utterance, retries included |
| `reconnect_on_interruption` | `True` | See [Interruptions](#interruptions) |

**On `sample_rate`:** 24000 is the API's default output rate and the right
choice for almost every agent, including telephony. If your transport needs
narrowband, let the transport resample, Pipecat does it for free, rather than
asking the server for a narrowband stream.

### Changing voice mid-session

Voice, language and expression controls are read per utterance, so a
`TTSUpdateSettingsFrame` takes effect on the next thing the bot says:

```python
from pipecat.frames.frames import TTSUpdateSettingsFrame

await task.queue_frame(TTSUpdateSettingsFrame(settings={"voice": "gandr-leo"}))
```

### Cloned voices

A cloned voice is registered **per connection**. Pass the reference audio once
and the service attaches it to the first utterance on each connection, and
re-attaches it automatically if the connection is reopened:

```python
tts = GandrTTSService(
    api_key=os.getenv("GANDR_API_KEY"),
    params=GandrTTSService.InputParams(
        voice_id="gnd:your-clone-id",
        voice_wav_b64=reference_wav_base64,
    ),
)
```

If the server asks for a voice and none was configured, the service raises a
clear error naming `voice_wav_b64` rather than going silent.

## Voices

Stock voices: `gandr-mia`, `gandr-ava`, `gandr-jenny`, `gandr-dane`,
`gandr-leo`, `gandr-lewis`. Cloned voices are `gnd:` identifiers.

## How the integration works

The service holds one WebSocket to `wss://tts.gandr.ai/ws` for the life of
the pipeline. Each utterance is a JSON message; the server answers with binary
frames of raw PCM16LE mono audio as it renders, then a JSON frame that closes
the utterance.

The connection carries many utterances but renders one at a time, so the
service serialises sends: `run_tts` queues an utterance and a single sender
task delivers it, waits for the closing frame, and only then sends the next.
That is what keeps the server's `busy` backpressure from ever becoming the
normal case. If it happens anyway, the send is retried after `busy_retry_s`.

Audio is delivered through Pipecat's audio-context API, so frames stay bound to
the turn that requested them and are dropped cleanly when that turn is
cancelled.

## Interruptions

The wire protocol has no cancel message. When the user barges in, audio already
rendering is discarded client-side, but it would still occupy the connection,
and the next turn's first byte would queue behind audio nobody is listening to.

So by default (`reconnect_on_interruption=True`) the service reopens the
connection on interruption. Set it to `False` to keep the connection and accept
that the next turn waits for the interrupted render to drain.

## Long text

The API caps a single request's transcript at 2000 characters. Pipecat normally
hands over a sentence at a time, so this rarely comes up; when it does, the
service splits the text on the cleanest boundary it can find, sentence end
first, then a word boundary, and sends the pieces back to back on the same
connection under the same turn. Nothing is dropped, and only the last piece
closes the turn.

## Errors

Failures surface as Pipecat `ErrorFrame`s through `push_error`, and the turn is
always closed with a `TTSStoppedFrame` so the pipeline never hangs waiting for
audio that is not coming. Connection loss is handled by reopening and, where
the utterance had not yet reached the wire, resending it.

## Metrics

`can_generate_metrics()` is `True`.

Time to first byte is stopped on **the first audio byte off the wire**, so what
your dashboard shows is the same event the service itself measures. Usage metrics
are reported per request from the full text of the turn.

The server reports its own timings on the frame that closes each utterance.
This service neither consumes nor logs them, so the only latency it ever
reports is the one it measured itself.

## Pricing

- **$10 a month for one million tokens** (one token is one character), resets monthly.
- **$150 per stream per month.**

See [gandr.ai/pricing](https://gandr.ai/pricing).

## Environment variables

```env
GANDR_API_KEY=your_gandr_api_key_here
OPENAI_API_KEY=your_openai_key_here      # if using with an LLM
DEEPGRAM_API_KEY=your_deepgram_key_here  # if using with STT
```

## Examples

- [`examples/foundational/gandr_tts_basic.py`](./examples/foundational/gandr_tts_basic.py), full pipeline with STT, LLM and TTS over the local audio transport.

```bash
uv add "pipecat-ai[deepgram,openai,silero,local]"
python examples/foundational/gandr_tts_basic.py
```

## Tests

```bash
pytest tests
```

The transcript tests import `pipecat_gandr._text` directly and need neither
Pipecat nor a network, so they run anywhere.

## Requirements

- Python >= 3.11
- pipecat-ai >= 0.0.108, < 2.0.0
- websockets >= 15.0.1, < 16.0
- pydantic >= 2.0
- loguru >= 0.7.3
- python-dotenv >= 1.1.1

## License

MIT. See [LICENSE](./LICENSE).

## Support

- Documentation: [gandr.ai/docs](https://gandr.ai/docs)
- Email: contact@gandr.ai
- Website: [gandr.ai](https://gandr.ai)
