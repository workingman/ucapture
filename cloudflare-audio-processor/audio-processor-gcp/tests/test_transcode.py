"""Tests for ffmpeg audio transcoder."""

import os
import shutil
import struct
import subprocess
import tempfile
import wave

import pytest

from audio_processor.audio.transcode import (
    TARGET_CHANNELS,
    TARGET_SAMPLE_RATE,
    TARGET_SAMPLE_WIDTH,
    TranscodeResult,
    transcode_to_wav,
)
from audio_processor.utils.errors import TranscodeError


def _ffmpeg_available() -> bool:
    """Check if ffmpeg is available on the system."""
    return shutil.which("ffmpeg") is not None


# Create a small valid WAV fixture (we use WAV as input since ffmpeg handles it;
# this avoids needing a real M4A file for unit tests)
@pytest.fixture
def valid_audio_file(tmp_path: object) -> str:
    """Create a tiny valid WAV file (1 second, 44100 Hz mono, 16-bit)."""
    filepath = os.path.join(str(tmp_path), "input.wav")
    sample_rate = 44100
    duration = 1.0
    num_samples = int(sample_rate * duration)

    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # Generate a simple sine-like pattern (alternating values)
        samples = struct.pack(f"<{num_samples}h", *([1000, -1000] * (num_samples // 2)))
        wf.writeframes(samples)

    return filepath


@pytest.fixture
def output_dir(tmp_path: object) -> str:
    """Provide a temporary output directory."""
    out = os.path.join(str(tmp_path), "output")
    os.makedirs(out, exist_ok=True)
    return out


@pytest.fixture
def corrupt_audio_file(tmp_path: object) -> str:
    """Create a corrupt file (text renamed to .m4a)."""
    filepath = os.path.join(str(tmp_path), "corrupt.m4a")
    with open(filepath, "w") as f:
        f.write("this is not audio data")
    return filepath


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg not available")
class TestTranscodeToWav:
    """Tests for transcode_to_wav with real ffmpeg."""

    def test_transcode_produces_correct_wav_format(
        self, valid_audio_file: str, output_dir: str
    ) -> None:
        result = transcode_to_wav(valid_audio_file, output_dir)

        assert os.path.exists(result.output_path)

        with wave.open(result.output_path, "rb") as wf:
            assert wf.getframerate() == TARGET_SAMPLE_RATE
            assert wf.getnchannels() == TARGET_CHANNELS
            assert wf.getsampwidth() == TARGET_SAMPLE_WIDTH

    def test_transcode_returns_correct_result_type(
        self, valid_audio_file: str, output_dir: str
    ) -> None:
        result = transcode_to_wav(valid_audio_file, output_dir)

        assert isinstance(result, TranscodeResult)
        assert result.input_path == valid_audio_file
        assert result.output_path.endswith(".wav")
        assert result.input_size_bytes > 0
        assert result.output_size_bytes > 0

    def test_transcode_duration_matches_input(
        self, valid_audio_file: str, output_dir: str
    ) -> None:
        result = transcode_to_wav(valid_audio_file, output_dir)

        # Input is 1 second; output should be within 0.1s tolerance
        assert abs(result.duration_seconds - 1.0) < 0.1

    def test_transcode_output_size_plausible_for_pcm(
        self, valid_audio_file: str, output_dir: str
    ) -> None:
        result = transcode_to_wav(valid_audio_file, output_dir)

        # 16kHz * 2 bytes * 1 channel * 1 second = ~32000 bytes + WAV header
        expected_min = TARGET_SAMPLE_RATE * TARGET_SAMPLE_WIDTH * 1 * 0.8
        expected_max = TARGET_SAMPLE_RATE * TARGET_SAMPLE_WIDTH * 1 * 1.2 + 100
        assert expected_min < result.output_size_bytes < expected_max

    def test_transcode_error_on_corrupt_input(
        self, corrupt_audio_file: str, output_dir: str
    ) -> None:
        with pytest.raises(TranscodeError):
            transcode_to_wav(corrupt_audio_file, output_dir)


class TestTranscodeValidation:
    """Tests for input validation (no ffmpeg needed)."""

    def test_transcode_error_on_missing_input(self, output_dir: str) -> None:
        with pytest.raises(TranscodeError, match="does not exist"):
            transcode_to_wav("/nonexistent/file.m4a", output_dir)

    def test_transcode_error_on_missing_ffmpeg(
        self, valid_audio_file: str, output_dir: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(shutil, "which", lambda _name: None)

        with pytest.raises(TranscodeError, match="ffmpeg binary not found"):
            transcode_to_wav(valid_audio_file, output_dir)
