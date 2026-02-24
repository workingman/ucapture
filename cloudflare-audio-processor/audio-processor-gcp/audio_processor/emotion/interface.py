"""Abstract emotion analysis interface.

Defines the EmotionEngine ABC and emotion data models per TDD Section 3.5.
Concrete implementations (e.g., GoogleNLEngine) subclass EmotionEngine.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from audio_processor.asr.interface import TranscriptSegment


@dataclass
class EmotionSegment:
    """Emotion analysis result for a single transcript segment."""

    segment_index: int
    start_seconds: float
    end_seconds: float
    speaker: str
    text: str
    analysis: dict[str, Any]


@dataclass
class EmotionResult:
    """Complete emotion analysis result envelope.

    Serializes to JSON matching the TDD 3.5 emotion.json schema:
    {provider, provider_version, analyzed_at, batch_id, segments[]}.
    """

    provider: str
    provider_version: str
    analyzed_at: str
    batch_id: str
    segments: list[EmotionSegment]


class EmotionEngine(ABC):
    """Abstract base class for emotion analysis engine implementations.

    Subclasses must implement the provider_name and provider_version
    properties and the analyze() method.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier (e.g., 'google-cloud-nl')."""

    @property
    @abstractmethod
    def provider_version(self) -> str:
        """Return the provider version string (e.g., 'v2')."""

    @abstractmethod
    async def analyze(
        self,
        segments: list[TranscriptSegment],
        audio_path: str | None = None,
    ) -> EmotionResult:
        """Analyze transcript segments for emotion/sentiment.

        Args:
            segments: Transcript segments with speaker labels and words.
            audio_path: Optional path to audio file (for audio-based providers).

        Returns:
            EmotionResult with per-segment analysis.
        """
