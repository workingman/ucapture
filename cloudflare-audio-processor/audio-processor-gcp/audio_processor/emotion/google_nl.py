"""Google Cloud Natural Language emotion analysis engine.

Implements sentiment analysis per transcript segment using the
Google Cloud NL API v2. Each segment's text is analyzed individually,
producing a score (-1.0 to 1.0) and magnitude (0.0+).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from audio_processor.asr.interface import TranscriptSegment
from audio_processor.emotion.interface import (
    EmotionEngine,
    EmotionResult,
    EmotionSegment,
)
from audio_processor.utils.errors import EmotionAnalysisError

logger = logging.getLogger(__name__)


class GoogleNLEngine(EmotionEngine):
    """Google Cloud Natural Language sentiment analysis engine.

    Analyzes each transcript segment individually via the NL API,
    producing per-segment score and magnitude values.

    Args:
        client: Optional pre-configured LanguageServiceClient.
            If None, creates one via google.cloud.language_v2.
    """

    @property
    def provider_name(self) -> str:
        return "google-cloud-nl"

    @property
    def provider_version(self) -> str:
        return "v2"

    def __init__(self, client: Any = None) -> None:
        if client is not None:
            self._client = client
        else:
            from google.cloud import language_v2

            self._client = language_v2.LanguageServiceClient()

    async def analyze(
        self,
        segments: list[TranscriptSegment],
        audio_path: str | None = None,
    ) -> EmotionResult:
        """Analyze transcript segments for sentiment.

        Args:
            segments: Transcript segments with speaker labels and words.
            audio_path: Ignored (text-based provider).

        Returns:
            EmotionResult with per-segment sentiment score and magnitude.

        Raises:
            EmotionAnalysisError: If the Google NL API call fails.
        """
        analyzed_at = datetime.now(UTC).isoformat()
        emotion_segments: list[EmotionSegment] = []

        for index, segment in enumerate(segments):
            text = " ".join(w.text for w in segment.words)
            start_seconds = segment.words[0].start_time if segment.words else 0.0
            end_seconds = segment.words[-1].end_time if segment.words else 0.0

            score, magnitude = self._analyze_segment_text(text)

            emotion_segments.append(
                EmotionSegment(
                    segment_index=index,
                    start_seconds=start_seconds,
                    end_seconds=end_seconds,
                    speaker=segment.speaker_label,
                    text=text,
                    analysis={"score": score, "magnitude": magnitude},
                )
            )

        return EmotionResult(
            provider=self.provider_name,
            provider_version=self.provider_version,
            analyzed_at=analyzed_at,
            batch_id="",
            segments=emotion_segments,
        )

    def _analyze_segment_text(self, text: str) -> tuple[float, float]:
        """Call the Google NL API to analyze sentiment for a text string.

        Args:
            text: The text to analyze.

        Returns:
            Tuple of (score, magnitude).

        Raises:
            EmotionAnalysisError: If the API call fails.
        """
        try:
            from google.cloud import language_v2

            document = language_v2.Document(
                content=text,
                type_=language_v2.Document.Type.PLAIN_TEXT,
            )
            response = self._client.analyze_sentiment(
                request={"document": document}
            )
        except EmotionAnalysisError:
            raise
        except Exception as exc:
            raise EmotionAnalysisError(
                f"Google NL API sentiment analysis failed: {exc}",
            ) from exc

        sentiment = response.document_sentiment
        return sentiment.score, sentiment.magnitude
