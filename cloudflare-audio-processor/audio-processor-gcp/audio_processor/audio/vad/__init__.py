"""Pluggable voice activity detection engines.

Public API:
    VADEngine       — Abstract base class for VAD implementations.
    SpeechSegment   — A contiguous segment of detected speech.
    VADResult       — Result of VAD processing.
    NullVADEngine   — Passthrough engine (marks entire audio as speech).
    SileroVADEngine — Silero VAD v6 engine using ONNX runtime.
    get_vad_engine  — Factory to create engines by provider name.
"""

from audio_processor.audio.vad.interface import SpeechSegment, VADEngine, VADResult
from audio_processor.audio.vad.null import NullVADEngine
from audio_processor.audio.vad.registry import get_vad_engine
from audio_processor.audio.vad.silero import SileroVADEngine

__all__ = [
    "VADEngine",
    "SpeechSegment",
    "VADResult",
    "NullVADEngine",
    "SileroVADEngine",
    "get_vad_engine",
]
