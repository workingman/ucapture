"""Pluggable noise suppression engines.

Public API:
    DenoiseEngine    — Abstract base class for denoise implementations.
    DenoiseResult    — Result of denoise processing.
    NullDenoiseEngine — Passthrough engine (no noise suppression).
    get_denoise_engine — Factory to create engines by provider name.
"""

from audio_processor.audio.denoise.interface import DenoiseEngine, DenoiseResult
from audio_processor.audio.denoise.null import NullDenoiseEngine
from audio_processor.audio.denoise.registry import get_denoise_engine

__all__ = [
    "DenoiseEngine",
    "DenoiseResult",
    "NullDenoiseEngine",
    "get_denoise_engine",
]
