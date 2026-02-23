"""Tests for Picovoice Koala noise suppression integration."""

import os
import struct
import sys
import wave
from unittest.mock import MagicMock

import pytest

from audio_processor.audio.denoise import (
    SAMPLE_RATE,
    DenoiseResult,
    run_denoise,
)
from audio_processor.utils.errors import DenoiseError


def _create_wav(path: str, num_samples: int, sample_rate: int = 16000) -> None:
    """Create a minimal 16kHz mono 16-bit WAV with given number of samples."""
    samples = [500] * num_samples
    raw = struct.pack(f"<{num_samples}h", *samples)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)


def _make_mock_koala(frame_length: int) -> MagicMock:
    """Create a mock Koala that acts as identity (returns input unchanged)."""
    mock = MagicMock()
    mock.frame_length = frame_length
    mock.process = MagicMock(side_effect=lambda frame: frame)
    mock.delete = MagicMock()
    return mock


@pytest.fixture(autouse=True)
def _mock_pvkoala_module():
    """Install a mock pvkoala module in sys.modules so the lazy import works."""
    mock_module = MagicMock()
    sys.modules["pvkoala"] = mock_module
    yield mock_module
    del sys.modules["pvkoala"]


class TestRunDenoise:
    """Tests for run_denoise with mocked Koala."""

    def test_output_wav_headers_correct(
        self, _mock_pvkoala_module: MagicMock, tmp_path: object
    ) -> None:
        """Mock Koala process() with identity; verify output WAV headers."""
        frame_length = 256
        num_samples = frame_length * 4

        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        mock_koala = _make_mock_koala(frame_length)
        _mock_pvkoala_module.create.return_value = mock_koala

        result = run_denoise(
            input_path,
            os.path.join(str(tmp_path), "out"),
            access_key="test-key",
        )

        with wave.open(result.output_path, "rb") as wf:
            assert wf.getframerate() == SAMPLE_RATE
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getnframes() == num_samples

    def test_denoise_result_has_correct_sizes(
        self, _mock_pvkoala_module: MagicMock, tmp_path: object
    ) -> None:
        """Verify DenoiseResult has correct size information."""
        frame_length = 256
        num_samples = frame_length * 2

        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        mock_koala = _make_mock_koala(frame_length)
        _mock_pvkoala_module.create.return_value = mock_koala

        result = run_denoise(
            input_path,
            os.path.join(str(tmp_path), "out"),
            access_key="test-key",
        )

        assert isinstance(result, DenoiseResult)
        assert result.input_size_bytes > 0
        assert result.output_size_bytes > 0
        assert os.path.exists(result.output_path)

    def test_partial_final_frame_zero_padded(
        self, _mock_pvkoala_module: MagicMock, tmp_path: object
    ) -> None:
        """Verify zero-padding applied to partial final frame."""
        frame_length = 256
        # 2.5 frames worth of samples => partial last frame
        num_samples = frame_length * 2 + frame_length // 2

        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        received_frames: list[list[int]] = []

        def capture_process(frame: list[int]) -> list[int]:
            received_frames.append(list(frame))
            return frame

        mock_koala = _make_mock_koala(frame_length)
        mock_koala.process.side_effect = capture_process
        _mock_pvkoala_module.create.return_value = mock_koala

        result = run_denoise(
            input_path,
            os.path.join(str(tmp_path), "out"),
            access_key="test-key",
        )

        # Should have 3 calls: 2 full frames + 1 padded frame
        assert len(received_frames) == 3

        # Last frame should be padded to frame_length
        last_frame = received_frames[-1]
        assert len(last_frame) == frame_length

        # First half of last frame should be 500 (original data)
        half = frame_length // 2
        assert all(s == 500 for s in last_frame[:half])

        # Second half should be zeros (padding)
        assert all(s == 0 for s in last_frame[half:])

        # Output should be trimmed to original sample count
        with wave.open(result.output_path, "rb") as wf:
            assert wf.getnframes() == num_samples

    def test_denoise_error_on_init_failure(
        self, _mock_pvkoala_module: MagicMock, tmp_path: object
    ) -> None:
        """DenoiseError raised on Koala init failure."""
        _mock_pvkoala_module.create.side_effect = RuntimeError("bad key")

        with pytest.raises(DenoiseError, match="Failed to initialize Koala"):
            run_denoise(
                os.path.join(str(tmp_path), "input.wav"),
                os.path.join(str(tmp_path), "out"),
                access_key="bad-key",
            )

    def test_delete_called_on_success(
        self, _mock_pvkoala_module: MagicMock, tmp_path: object
    ) -> None:
        """Verify .delete() called on success."""
        frame_length = 256
        num_samples = frame_length

        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        mock_koala = _make_mock_koala(frame_length)
        _mock_pvkoala_module.create.return_value = mock_koala

        run_denoise(
            input_path,
            os.path.join(str(tmp_path), "out"),
            access_key="test-key",
        )

        mock_koala.delete.assert_called_once()

    def test_delete_called_on_exception(
        self, _mock_pvkoala_module: MagicMock, tmp_path: object
    ) -> None:
        """Verify .delete() called even when processing raises."""
        frame_length = 256
        num_samples = frame_length

        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        mock_koala = _make_mock_koala(frame_length)
        mock_koala.process.side_effect = RuntimeError("processing error")
        _mock_pvkoala_module.create.return_value = mock_koala

        with pytest.raises(RuntimeError, match="processing error"):
            run_denoise(
                input_path,
                os.path.join(str(tmp_path), "out"),
                access_key="test-key",
            )

        mock_koala.delete.assert_called_once()

    def test_output_wav_readable_by_wave_module(
        self, _mock_pvkoala_module: MagicMock, tmp_path: object
    ) -> None:
        """Output WAV should be readable by the standard wave module."""
        frame_length = 256
        num_samples = frame_length * 3

        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        mock_koala = _make_mock_koala(frame_length)
        _mock_pvkoala_module.create.return_value = mock_koala

        result = run_denoise(
            input_path,
            os.path.join(str(tmp_path), "out"),
            access_key="test-key",
        )

        # Verify the output is a valid WAV that wave module can fully read
        with wave.open(result.output_path, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
            samples = struct.unpack(f"<{wf.getnframes()}h", raw)
            assert len(samples) == num_samples
