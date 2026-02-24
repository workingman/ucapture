"""Abstract VAD engine interface and data models.

Defines the VADEngine ABC and result data classes per TDD Decision 9.
Concrete implementations (e.g., Silero, Null) subclass VADEngine.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SpeechSegment:
    """A contiguous segment of detected speech with sample-level precision."""

    start_sample: int
    end_sample: int
    start_seconds: float
    end_seconds: float


@dataclass
class VADResult:
    """Result of voice activity detection processing."""

    segments: list[SpeechSegment]
    total_duration_seconds: float
    speech_duration_seconds: float
    speech_ratio: float
    output_path: str


class VADEngine(ABC):
    """Abstract base class for VAD engine implementations.

    Subclasses must implement the process() method.
    """

    @abstractmethod
    def process(self, input_path: str, output_dir: str) -> VADResult:
        """Run voice activity detection on a 16kHz mono 16-bit PCM WAV file.

        Args:
            input_path: Path to the input WAV file.
            output_dir: Directory for the speech-only output WAV.

        Returns:
            VADResult with speech segments, durations, and output path.
        """
