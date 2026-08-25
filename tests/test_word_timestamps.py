#
# Copyright (c) 2024-2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Tests for the word-timestamps option of GandrTTSService."""

import json
from unittest.mock import AsyncMock

import pytest
import websockets
from websockets.asyncio.server import serve

from pipecat.frames.frames import ErrorFrame, TTSAudioRawFrame, TTSSpeakFrame
from pipecat.tests.utils import SleepFrame, run_test

from pipecat_gandr.tts import GandrTTSService

AUDIO = b"\x00\x01" * 512

WORDS = [
    {"word": "hello", "start": 0.0},
    {"word": "there", "start": 0.3},
    {"word": ", ", "start": 0.5},
]


def _handler(captured: dict):
    """Echo word timings only when the utterance asked for them."""

    async def handler(ws):
        try:
            async for raw in ws:
                msg = json.loads(raw)
                captured["messages"].append(msg)
                for _ in range(2):
                    await ws.send(AUDIO)
                tail = {"ttfa_ms": 10, "audio_ms": 20}
                if msg.get("add_timestamps"):
                    tail["word_timestamps"] = WORDS
                await ws.send(json.dumps(tail))
        except websockets.ConnectionClosed:
            pass

    return handler


async def _run(captured: dict, tts: GandrTTSService) -> tuple[list, list]:
    async with serve(_handler(captured), "127.0.0.1", 0) as server:
        host, port = next(iter(server.sockets)).getsockname()[:2]
        tts._url = f"ws://{host}:{port}/ws"
        return await run_test(
            tts,
            frames_to_send=[TTSSpeakFrame(text="hello there"), SleepFrame(sleep=0.4)],
        )


@pytest.mark.asyncio
async def test_word_timestamps_requested_and_delivered():
    captured: dict = {"messages": []}
    tts = GandrTTSService(
        api_key="test-key",
        sample_rate=24000,
        params=GandrTTSService.InputParams(word_timestamps=True),
    )
    spy = AsyncMock(wraps=tts.add_word_timestamps)
    tts.add_word_timestamps = spy

    down, up = await _run(captured, tts)

    assert not any(isinstance(f, ErrorFrame) for f in down + up)
    assert captured["messages"][0].get("add_timestamps") is True
    assert any(isinstance(f, TTSAudioRawFrame) for f in down)
    spy.assert_awaited_once()
    args, kwargs = spy.await_args
    pairs = args[0] if args else kwargs.get("word_times")
    assert [w for w, _ in pairs] == ["hello", "there,"]
    assert isinstance(pairs[0][1], float)


@pytest.mark.asyncio
async def test_word_timestamps_off_keeps_wire_clean():
    captured: dict = {"messages": []}
    tts = GandrTTSService(api_key="test-key", sample_rate=24000)
    spy = AsyncMock(wraps=tts.add_word_timestamps)
    tts.add_word_timestamps = spy

    down, up = await _run(captured, tts)

    assert not any(isinstance(f, ErrorFrame) for f in down + up)
    assert "add_timestamps" not in captured["messages"][0]
    spy.assert_not_awaited()
