"""Null denoise engine — passthrough that copies audio unchanged.

Used when noise suppression is disabled (Decision 10: denoising degrades
ASR WER 1-47%, and Speechmatics has built-in audio filtering).
"""

import os
import shutil

from audio_processor.audio.denoise.interface import DenoiseEngine, DenoiseResult


class NullDenoiseEngine(DenoiseEngine):
    """Passthrough denoise that copies input to output unchanged."""

    def process(self, input_path: str, output_dir: str) -> DenoiseResult:
        """Copy input file unchanged to the output directory.

        Args:
            input_path: Path to the input WAV file.
            output_dir: Directory for the output WAV copy.

        Returns:
            DenoiseResult with matching input/output sizes.
        """
        input_size = os.path.getsize(input_path)

        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "denoised.wav")
        shutil.copy2(input_path, output_path)

        output_size = os.path.getsize(output_path)

        return DenoiseResult(
            input_size_bytes=input_size,
            output_size_bytes=output_size,
            output_path=output_path,
        )
