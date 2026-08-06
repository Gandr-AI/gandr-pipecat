# Add Gandr as a provider-maintained TTS integration

## Summary

This adds Gandr to Pipecat's list of third-party, provider-maintained TTS
integrations, alongside the existing partner packages.

The integration ships as its own package, `pipecat-gandr`, following the
structure Murf uses for `pipecat-murf-tts`: a standalone repo, a single
`GandrTTSService` built on `WebsocketTTSService`, a foundational example, and a
version range pinned to `pipecat-ai>=0.0.108,<2.0.0`. Nothing in Pipecat core
changes; this is a docs entry plus a package we maintain.

We are the provider of the service, and we maintain the integration.

## What the package contains

```
pipecat-gandr/
├── pyproject.toml
├── README.md
├── LICENSE
├── .env.example
├── src/pipecat_gandr/
│   ├── __init__.py            lazy re-export (PEP 562)
│   ├── _text.py               transcript splitting, no dependencies
│   └── tts.py                 GandrTTSService
├── tests/
│   └── test_text.py           11 tests, no network, no Pipecat needed
└── examples/foundational/
    └── gandr_tts_basic.py     local audio + STT + LLM + TTS
```

Importing `pipecat_gandr` does not import Pipecat or a websocket stack until
`GandrTTSService` is actually referenced, which is what lets the transcript
tests run on a bare interpreter.

## Design

`GandrTTSService` subclasses `WebsocketTTSService` and holds one connection for
the life of the pipeline.

**Wire protocol.** Each utterance is one JSON message. The server answers with
binary frames of raw PCM16LE mono audio as it renders, then a JSON frame that
closes the utterance. Errors arrive as `{"error": "..."}`.

**Serialised sends.** The connection carries many utterances but renders one at
a time. `run_tts` queues the utterance and returns; a single sender task
delivers it, waits for the closing frame, and only then sends the next. This is
the piece that keeps the server's `busy` backpressure from becoming the normal
case rather than the exception. When it does occur, the send is retried.

**Audio contexts.** Audio is delivered through
`append_to_audio_context` / `remove_audio_context`, so frames stay bound to the
turn that requested them, and a cancelled turn drops its audio cleanly.

**Interruptions.** The protocol has no cancel message. On barge-in the service
abandons the in-flight utterance, drains anything still queued, and by default
reopens the connection, so the next turn's first byte is not queued behind
audio the listener already interrupted. `reconnect_on_interruption=False` keeps
the connection instead, at the cost of that wait.

**TTFB.** `stop_ttfb_metrics()` fires on the first audio byte off the wire, not
on the frame that closes the utterance. That makes the number in a user's
dashboard the same event we publish a figure for.

**Long text.** The API caps a request at 2000 characters. Longer text is split
on a sentence boundary where one exists and a word boundary otherwise, sent
back to back on the same connection under one turn, with only the last piece
closing the turn. The splitter is lossless.

**Cloned voices.** A cloned voice is registered per connection. Reference audio
is attached to the first utterance on each connection and re-attached
automatically after a reconnect; a `need_voice` response triggers one
re-registration attempt rather than a silent failure.

**Failure path.** Every failure surfaces as an `ErrorFrame` via `push_error`
and always closes the turn with a `TTSStoppedFrame`, so a pipeline never hangs
waiting for audio that is not coming.

## Numbers

- **146 ms to first audio byte** over the open internet. Client-measured p50,
  n=25 interleaved runs against each named competitor in the same hours, from a
  neutral US vantage over a held WebSocket. All pairwise gaps significant
  (p=0.0009 / 0.0041 / <0.001). This is the first audio byte, not the moment a
  listener hears speech.
- **116 ms server-side p50**, min 104 / max 130.
- **WER 1.982%** against a **2.171%** human baseline, one `whisper-large-v3`
  scorer used for everything including the human baseline, n=1,088, zero render
  errors.

Under load, overflow spills to a fallback lane that can take longer on its
first request.

Pricing is $10 per million characters on prepaid packs, and $150 per stream per
month.

## Verification

What has been done:

- The service is written against the documented wire protocol at
  gandr.ai/docs and against our existing LiveKit Agents integration, which
  speaks to the same API.
- Structure, base class, lifecycle methods, audio-context usage and metrics
  calls follow `pipecat-murf-tts` as the reference provider-maintained
  integration.
- The request splitter has 11 unit tests covering the cap, losslessness,
  sentence and word boundaries, and a single token longer than the cap. They
  were then checked against eight mutations of the splitter — removing the
  sentence rule, removing the word rule, dropping the terminator adjustment,
  dropping the limit guard, losing the trailing remainder, and three
  off-by-ones. All eight turn the suite red, so the green result is load
  bearing rather than incidental. Two of the tests were rewritten during that
  check because their original fixtures passed under a mutant.
- The module compiles clean and carries no placeholder code.

What is still owed before this merges, and is not claimed here:

- A recorded end-to-end run of `examples/foundational/gandr_tts_basic.py`,
  including a barge-in, a mid-session voice change, and a forced reconnect.
- Confirmation of the pipecat-ai version range against the latest release.
- A published `pipecat-gandr` on PyPI for the docs entry to link.

## Checklist

- [ ] Docs entry added to the third-party TTS services list
- [ ] `pipecat-gandr` published to PyPI
- [ ] End-to-end run recorded, including interruption and reconnect
- [ ] Maintainer contact confirmed: contact@gandr.ai
