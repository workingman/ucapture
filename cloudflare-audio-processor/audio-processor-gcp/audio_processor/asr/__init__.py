"""Automatic speech recognition modules."""

from audio_processor.asr.registry import get_asr_engine

__all__ = ["get_asr_engine"]
