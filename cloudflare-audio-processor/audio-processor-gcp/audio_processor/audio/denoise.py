"""Picovoice Koala noise suppression integration.

Processes speech-segment WAV (output from VAD) frame-by-frame using Koala
to produce a denoised output WAV. Partial final frames are zero-padded.
"""

import os
import struct
import wave
from dataclasses import dataclass

from audio_processor.utils.errors import DenoiseError

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # 16-bit = 2 bytes
NUM_CHANNELS = 1


@dataclass
class DenoiseResult:
    """Result of noise suppression processing."""

    input_size_bytes: int
    output_size_bytes: int
    output_path: str


def _read_wav_samples(wav_path: str) -> list[int]:
    """Read all samples from a 16kHz mono 16-bit WAV file.

    Args:
        wav_path: Path to the WAV file.

    Returns:
        List of int16 sample values.

    Raises:
        DenoiseError: If the WAV file cannot be read.
    """
    try:
        with wave.open(wav_path, "rb") as wf:
            raw_data = wf.readframes(wf.getnframes())
    except Exception as exc:
        raise DenoiseError(f"Failed to read WAV file: {wav_path}") from exc

    num_samples = len(raw_data) // SAMPLE_WIDTH
    return list(struct.unpack(f"<{num_samples}h", raw_data))


def _write_wav_samples(output_path: str, samples: list[int]) -> None:
    """Write int16 samples to a 16kHz mono 16-bit WAV file.

    Args:
        output_path: Path for the output WAV file.
        samples: List of int16 sample values.
    """
    raw_data = struct.pack(f"<{len(samples)}h", *samples)
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(NUM_CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(raw_data)


def run_denoise(
    input_path: str,
    output_dir: str,
    access_key: str,
    output_filename: str = "denoised.wav",
) -> DenoiseResult:
    """Run Koala noise suppression on a 16kHz mono WAV file.

    Processes audio frame-by-frame using Koala's frame_length. The final
    partial frame is zero-padded to meet the required frame size.

    Args:
        input_path: Path to 16kHz mono 16-bit PCM WAV input.
        output_dir: Directory for the denoised output WAV.
        access_key: Picovoice access key for Koala initialization.
        output_filename: Name for the output WAV file.

    Returns:
        DenoiseResult with input/output sizes and output path.

    Raises:
        DenoiseError: On Koala init failure or processing errors.
    """
    import pvkoala

    try:
        koala = pvkoala.create(access_key=access_key)
    except Exception as exc:
        raise DenoiseError(
            f"Failed to initialize Koala: {exc}", detail=str(exc)
        ) from exc

    try:
        samples = _read_wav_samples(input_path)
        input_size = os.path.getsize(input_path)
        frame_length = koala.frame_length

        denoised_samples: list[int] = []

        offset = 0
        while offset < len(samples):
            frame = samples[offset : offset + frame_length]

            # Zero-pad partial final frame
            if len(frame) < frame_length:
                frame = frame + [0] * (frame_length - len(frame))

            enhanced = koala.process(frame)
            denoised_samples.extend(enhanced)

            offset += frame_length

        # Trim to original length (remove zero-padding artifacts)
        denoised_samples = denoised_samples[: len(samples)]

        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)
        _write_wav_samples(output_path, denoised_samples)

        return DenoiseResult(
            input_size_bytes=input_size,
            output_size_bytes=os.path.getsize(output_path),
            output_path=output_path,
        )

    finally:
        koala.delete()
