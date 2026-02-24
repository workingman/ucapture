"""Null VAD engine — passthrough that marks entire audio as speech.

Used when VAD is disabled or for testing. Copies the input file
unchanged to the output directory.
"""

import os
import shutil

from audio_processor.audio.vad.interface import SpeechSegment, VADEngine, VADResult
from audio_processor.audio.wav_utils import SAMPLE_RATE, read_wav_samples


class NullVADEngine(VADEngine):
    """Passthrough VAD that treats the entire audio as a single speech segment."""

    def process(self, input_path: str, output_dir: str) -> VADResult:
        """Copy input unchanged and return a single segment spanning all audio.

        Args:
            input_path: Path to the input WAV file.
            output_dir: Directory for the output WAV copy.

        Returns:
            VADResult with one segment covering the entire file, speech_ratio=1.0.
        """
        samples = read_wav_samples(input_path)
        total_samples = len(samples)
        total_duration = total_samples / SAMPLE_RATE

        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "speech.wav")
        shutil.copy2(input_path, output_path)

        segment = SpeechSegment(
            start_sample=0,
            end_sample=total_samples,
            start_seconds=0.0,
            end_seconds=total_duration,
        )

        return VADResult(
            segments=[segment],
            total_duration_seconds=total_duration,
            speech_duration_seconds=total_duration,
            speech_ratio=1.0,
            output_path=output_path,
        )
