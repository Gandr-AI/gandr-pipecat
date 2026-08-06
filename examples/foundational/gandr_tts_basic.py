"""Full voice-agent pipeline: local mic in, Gandr TTS out.

Run it with:

    uv add "pipecat-ai[deepgram,openai,silero,local]"
    python examples/foundational/gandr_tts_basic.py

Requires GANDR_API_KEY, OPENAI_API_KEY and DEEPGRAM_API_KEY in a .env file.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMMessagesAppendFrame, LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.local.audio import (
    LocalAudioTransport,
    LocalAudioTransportParams,
)

from pipecat_gandr import GandrTTSService

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

# Gandr renders mono PCM16LE. Ask the transport for the same rate the service
# asks Gandr for, so nothing in the path has to resample.
SAMPLE_RATE = 24000


async def main() -> None:
    """Build and run the pipeline."""
    settings = {
        "gandr_api_key": os.getenv("GANDR_API_KEY"),
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "deepgram_api_key": os.getenv("DEEPGRAM_API_KEY"),
    }

    missing_keys = [key for key, value in settings.items() if not value]
    if missing_keys:
        logger.error(f"Missing required API keys: {', '.join(missing_keys)}")
        logger.error("Please ensure all API keys are set in your .env file")
        sys.exit(1)

    logger.info("All API keys loaded")

    transport = LocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_out_sample_rate=SAMPLE_RATE,
            audio_out_channels=1,
        )
    )

    stt = DeepgramSTTService(api_key=settings["deepgram_api_key"])

    tts = GandrTTSService(
        api_key=settings["gandr_api_key"],
        params=GandrTTSService.InputParams(
            voice_id="gandr-mia",
            language="en",
            sample_rate=SAMPLE_RATE,
        ),
    )

    llm = OpenAILLMService(api_key=settings["openai_api_key"])

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant on a phone call. Keep answers "
                "short. Your output is spoken aloud, so write plain sentences "
                "with no markdown and no special characters."
            ),
        },
    ]

    context = LLMContext(messages)
    context_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

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

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    await task.queue_frames(
        [
            LLMMessagesAppendFrame(
                messages=[
                    {
                        "role": "system",
                        "content": "Please introduce yourself to the user.",
                    }
                ]
            ),
            LLMRunFrame(),
        ]
    )

    runner = PipelineRunner()
    await runner.run(task)


if __name__ == "__main__":
    logger.info("Starting bot")
    asyncio.run(main())
