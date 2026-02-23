"""Abstract ASR engine interface.

Defines the ASR engine ABC and transcript data models per TDD Section 6, Decision 4.
Concrete implementations (e.g., Speechmatics) subclass ASREngine.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TranscriptWord:
    """A single word with timing and confidence information."""

    text: str
    start_time: float
    end_time: float
    confidence: float


@dataclass
class TranscriptSegment:
    """A segment of speech from a single speaker."""

    speaker_label: str
    words: list[TranscriptWord]


@dataclass
class Transcript:
    """Complete transcript with speaker-labeled segments."""

    segments: list[TranscriptSegment]
    raw_response: dict


class ASREngine(ABC):
    """Abstract base class for ASR engine implementations.

    Subclasses must implement the transcribe() method.
    """

    @abstractmethod
    async def transcribe(self, audio_path: str, metadata: dict) -> Transcript:
        """Transcribe an audio file and return a structured transcript.

        Args:
            audio_path: Path to the audio file (16kHz mono 16-bit PCM WAV).
            metadata: Batch metadata for context (e.g., language hints).

        Returns:
            Transcript with speaker-labeled segments and raw API response.
        """
