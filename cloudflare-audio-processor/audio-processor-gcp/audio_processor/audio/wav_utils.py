"""Shared WAV file I/O helpers for 16kHz mono 16-bit PCM audio.

Extracted from duplicated private functions in vad.py and denoise.py
to satisfy the DRY principle (FP-001).
"""

import struct
import wave

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # 16-bit = 2 bytes
NUM_CHANNELS = 1


def read_wav_samples(wav_path: str) -> list[int]:
    """Read all samples from a 16kHz mono 16-bit WAV file.

    Args:
        wav_path: Path to the WAV file.

    Returns:
        List of int16 sample values.

    Raises:
        ValueError: If the WAV file cannot be read.
    """
    try:
        with wave.open(wav_path, "rb") as wf:
            raw_data = wf.readframes(wf.getnframes())
    except Exception as exc:
        raise ValueError(f"Failed to read WAV file: {wav_path}") from exc

    num_samples = len(raw_data) // SAMPLE_WIDTH
    return list(struct.unpack(f"<{num_samples}h", raw_data))


def write_wav_samples(
    output_path: str, samples: list[int], sample_rate: int = SAMPLE_RATE
) -> None:
    """Write int16 samples to a 16kHz mono 16-bit WAV file.

    Args:
        output_path: Path for the output WAV file.
        samples: List of int16 sample values.
        sample_rate: Sample rate in Hz (default 16000).
    """
    raw_data = struct.pack(f"<{len(samples)}h", *samples)
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(NUM_CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(sample_rate)
        wf.writeframes(raw_data)
