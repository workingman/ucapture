"""Tests for shared WAV file I/O helpers."""

import os
import struct
import wave

import pytest

from audio_processor.audio.wav_utils import (
    NUM_CHANNELS,
    SAMPLE_RATE,
    SAMPLE_WIDTH,
    read_wav_samples,
    write_wav_samples,
)


def _create_wav(
    path: str, samples: list[int], sample_rate: int = SAMPLE_RATE
) -> None:
    """Create a WAV file with given samples."""
    raw = struct.pack(f"<{len(samples)}h", *samples)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(NUM_CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)


class TestReadWavSamples:
    """Tests for read_wav_samples."""

    def test_round_trip_preserves_samples(self, tmp_path: object) -> None:
        """Writing then reading samples produces the original values."""
        original = [0, 1000, -1000, 32767, -32768]
        wav_path = os.path.join(str(tmp_path), "test.wav")
        _create_wav(wav_path, original)

        result = read_wav_samples(wav_path)

        assert result == original

    def test_nonexistent_file_raises_value_error(self, tmp_path: object) -> None:
        """Reading a missing file raises ValueError."""
        bad_path = os.path.join(str(tmp_path), "missing.wav")

        with pytest.raises(ValueError, match="Failed to read WAV file"):
            read_wav_samples(bad_path)

    def test_empty_wav_returns_empty_list(self, tmp_path: object) -> None:
        """Reading a WAV with zero samples returns an empty list."""
        wav_path = os.path.join(str(tmp_path), "empty.wav")
        _create_wav(wav_path, [])

        result = read_wav_samples(wav_path)

        assert result == []


class TestWriteWavSamples:
    """Tests for write_wav_samples."""

    def test_output_wav_has_correct_headers(self, tmp_path: object) -> None:
        """Written WAV has correct sample rate, channels, and width."""
        samples = [500] * 1600
        wav_path = os.path.join(str(tmp_path), "output.wav")

        write_wav_samples(wav_path, samples)

        with wave.open(wav_path, "rb") as wf:
            assert wf.getframerate() == SAMPLE_RATE
            assert wf.getnchannels() == NUM_CHANNELS
            assert wf.getsampwidth() == SAMPLE_WIDTH
            assert wf.getnframes() == len(samples)
