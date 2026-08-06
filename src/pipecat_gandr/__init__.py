"""Gandr TTS integration for Pipecat.

``GandrTTSService`` is imported lazily (PEP 562), so importing this package
does not pull in Pipecat or a websocket stack until the service is actually
referenced. The transcript helpers below have no dependencies at all.
"""

from typing import Any

from pipecat_gandr._text import MAX_REQUEST_CHARS, split_for_request

__version__ = "0.1.0"

__all__ = [
    "GandrTTSService",
    "DEFAULT_WS_URL",
    "SAMPLE_RATES",
    "MAX_REQUEST_CHARS",
    "STOCK_VOICES",
    "split_for_request",
]

_LAZY = {"GandrTTSService", "DEFAULT_WS_URL", "SAMPLE_RATES", "STOCK_VOICES"}


def __getattr__(name: str) -> Any:
    """Resolve the service-side names on first use.

    Args:
        name: The attribute being looked up.

    Returns:
        The requested attribute from ``pipecat_gandr.tts``.

    Raises:
        AttributeError: If the name is not part of the public API.
    """
    if name in _LAZY:
        from pipecat_gandr import tts

        return getattr(tts, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list:
    """List the public API, lazy names included.

    Returns:
        The sorted public attribute names.
    """
    return sorted(__all__ + ["__version__"])
