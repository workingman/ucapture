"""Emotion analysis runner with provider registry.

Best-effort emotion analysis: failures are logged and return None rather
than raising exceptions. This allows the pipeline to continue even if
emotion analysis is unavailable or fails.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Protocol

from audio_processor.asr.interface import Transcript
from audio_processor.emotion.google_nl import GoogleNLEngine
from audio_processor.emotion.interface import EmotionEngine, EmotionResult

logger = logging.getLogger(__name__)

EMOTION_ENGINES: dict[str, type[EmotionEngine]] = {
    "google-cloud-nl": GoogleNLEngine,
}


class EmotionConfig(Protocol):
    """Protocol for config objects that carry an emotion_provider field."""

    emotion_provider: str | None


async def run_emotion_analysis(
    transcript: Transcript,
    audio_path: str | None,
    config: Any,
) -> EmotionResult | None:
    """Run emotion analysis on a transcript (best-effort).

    Args:
        transcript: The ASR transcript to analyze.
        audio_path: Optional path to audio file for audio-based providers.
        config: Configuration object with an emotion_provider attribute.

    Returns:
        EmotionResult on success, None if skipped or on failure.
    """
    provider = getattr(config, "emotion_provider", None)

    if not provider:
        return None

    engine_cls = EMOTION_ENGINES.get(provider)
    if not engine_cls:
        logger.warning("Unknown emotion provider: '%s'", provider)
        return None

    if not transcript.segments:
        return _empty_result(engine_cls)

    try:
        engine = engine_cls()
        return await engine.analyze(transcript.segments, audio_path)
    except Exception:
        logger.error(
            "Emotion analysis failed for provider '%s'",
            provider,
            exc_info=True,
        )
        return None


def _empty_result(engine_cls: type[EmotionEngine]) -> EmotionResult:
    """Create an EmotionResult with empty segments for a valid provider.

    Per PRD: produce result with segments=[] when transcript has no segments.
    """
    engine = engine_cls()
    return EmotionResult(
        provider=engine.provider_name,
        provider_version=engine.provider_version,
        analyzed_at=datetime.now(UTC).isoformat(),
        batch_id="",
        segments=[],
    )
