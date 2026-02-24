"""Abstract denoise engine interface and data models.

Defines the DenoiseEngine ABC and result data class per TDD Decision 10.
Concrete implementations (e.g., Null) subclass DenoiseEngine.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DenoiseResult:
    """Result of noise suppression processing."""

    input_size_bytes: int
    output_size_bytes: int
    output_path: str


class DenoiseEngine(ABC):
    """Abstract base class for denoise engine implementations.

    Subclasses must implement the process() method.
    """

    @abstractmethod
    def process(self, input_path: str, output_dir: str) -> DenoiseResult:
        """Run noise suppression on a 16kHz mono 16-bit PCM WAV file.

        Args:
            input_path: Path to the input WAV file.
            output_dir: Directory for the denoised output WAV.

        Returns:
            DenoiseResult with input/output sizes and output path.
        """
