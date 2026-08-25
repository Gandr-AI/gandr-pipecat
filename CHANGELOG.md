# Changelog

## 0.1.3

- Word timestamps: set InputParams(word_timestamps=True) and the closing
  frame's per-word offsets are fed into Pipecat's word-timestamp machinery.

All notable changes to `pipecat-gandr` are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Pipecat requires a changelog for community integrations, and the reason is
worth honouring rather than satisfying: a voice pipeline breaks in production
when a dependency changes behaviour, and the person debugging it at 2am is
reading this file to find out what moved.

## [Unreleased]

### Verified

- **Tested against `pipecat-ai` 1.7.0 on Python 3.12.11** (2026-08-07). The
  package was written against `pipecat-ai` 0.0.108, so this crosses a major
  version and roughly a year of API drift: `WebsocketTTSService` is still the
  correct base class and the interface still fits. Clean venv,
  `pip install` exit 0, 11/11 unit tests pass, service constructs.
- **Not yet verified:** no live socket has been opened against the service.
  Install, import, unit tests and construction only. A real turn costs a
  render, so it is deliberately not claimed here.

### Added

- Docstrings on the five `PublicOptions` field validators, so every public
  definition in `tts.py` documents itself as Pipecat's contribution
  guidelines require.

## [0.1.0], 2026-08-06

### Added

- `GandrTTSService`, a `WebsocketTTSService` holding one socket to the Gandr
  door and reusing it across turns.
- `split_for_request`, a lossless splitter for the service's 2,000-character
  per-request cap. Its 11 tests were proved red under 8 mutations; two of
  them survived their first mutant and were rewritten, having been green for
  the wrong reason.
- `STOCK_VOICES`, `SAMPLE_RATES`, `MAX_REQUEST_CHARS`, `DEFAULT_WS_URL`.
- Foundational example at `examples/foundational/gandr_tts_basic.py`.

### Behaviour worth knowing before you upgrade or debug

- **Barge-in abandons and reopens the socket.** The wire protocol has no
  cancel frame, so the alternative was draining audio nobody will hear.
- **The first turn on a fresh socket runs about 700 ms** while the session
  voice cache fills; every turn after is far quicker. This is why the socket
  is held warm across turns rather than opened per utterance, a benchmark
  that measures turn one measures the cache filling, not the engine.
- **Every failure path closes the turn with `TTSStoppedFrame`**, so a
  pipeline cannot hang waiting on a socket that has died.
