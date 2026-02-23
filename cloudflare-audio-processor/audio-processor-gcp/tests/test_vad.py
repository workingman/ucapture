"""Tests for Picovoice Cobra VAD integration."""

import os
import struct
import sys
import wave
from unittest.mock import MagicMock, patch

import pytest

from audio_processor.audio.vad import (
    SAMPLE_RATE,
    VADResult,
    run_vad,
)
from audio_processor.utils.errors import VADError


def _create_wav(path: str, num_samples: int, sample_rate: int = 16000) -> None:
    """Create a minimal 16kHz mono 16-bit WAV with given number of samples."""
    samples = [1000] * num_samples
    raw = struct.pack(f"<{num_samples}h", *samples)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)


def _make_mock_cobra(
    frame_length: int, probabilities: list[float]
) -> MagicMock:
    """Create a mock Cobra instance with predetermined voice probabilities."""
    mock = MagicMock()
    mock.frame_length = frame_length
    mock.process = MagicMock(side_effect=probabilities)
    mock.delete = MagicMock()
    return mock


@pytest.fixture(autouse=True)
def _mock_pvcobra_module():
    """Install a mock pvcobra module in sys.modules so the lazy import works."""
    mock_module = MagicMock()
    sys.modules["pvcobra"] = mock_module
    yield mock_module
    del sys.modules["pvcobra"]


class TestRunVAD:
    """Tests for run_vad with mocked Cobra."""

    def test_detects_speech_segments(
        self, _mock_pvcobra_module: MagicMock, tmp_path: object
    ) -> None:
        """Mock Cobra with known probabilities; verify correct segments."""
        frame_length = 512
        probabilities = [0.8, 0.9, 0.1, 0.7]
        num_samples = frame_length * 4

        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        mock_cobra = _make_mock_cobra(frame_length, probabilities)
        _mock_pvcobra_module.create.return_value = mock_cobra

        result = run_vad(
            input_path,
            os.path.join(str(tmp_path), "out"),
            access_key="test-key",
        )

        assert isinstance(result, VADResult)
        assert len(result.speech_segments) == 2
        assert result.speech_duration_seconds > 0
        assert result.output_path is not None

    def test_zero_speech_returns_empty_result(
        self, _mock_pvcobra_module: MagicMock, tmp_path: object
    ) -> None:
        """Mock Cobra returning all zeros; verify zero-speech result."""
        frame_length = 512
        probabilities = [0.0, 0.0, 0.0, 0.0]
        num_samples = frame_length * 4

        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        mock_cobra = _make_mock_cobra(frame_length, probabilities)
        _mock_pvcobra_module.create.return_value = mock_cobra

        result = run_vad(
            input_path,
            os.path.join(str(tmp_path), "out"),
            access_key="test-key",
        )

        assert result.speech_segments == []
        assert result.speech_duration_seconds == 0.0
        assert result.speech_ratio == 0.0
        assert result.output_path is None

    def test_speech_ratio_calculation(
        self, _mock_pvcobra_module: MagicMock, tmp_path: object
    ) -> None:
        """Verify speech_ratio is speech_duration / total_duration."""
        frame_length = 512
        # 4 frames: 2 speech, 2 silence => ratio ~0.5
        probabilities = [0.8, 0.9, 0.1, 0.2]
        num_samples = frame_length * 4

        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        mock_cobra = _make_mock_cobra(frame_length, probabilities)
        _mock_pvcobra_module.create.return_value = mock_cobra

        result = run_vad(
            input_path,
            os.path.join(str(tmp_path), "out"),
            access_key="test-key",
        )

        assert abs(result.speech_ratio - 0.5) < 0.01

    def test_delete_called_on_success(
        self, _mock_pvcobra_module: MagicMock, tmp_path: object
    ) -> None:
        """Verify .delete() called on success."""
        frame_length = 512
        probabilities = [0.8]
        num_samples = frame_length

        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        mock_cobra = _make_mock_cobra(frame_length, probabilities)
        _mock_pvcobra_module.create.return_value = mock_cobra

        run_vad(
            input_path,
            os.path.join(str(tmp_path), "out"),
            access_key="test-key",
        )

        mock_cobra.delete.assert_called_once()

    def test_delete_called_on_exception(
        self, _mock_pvcobra_module: MagicMock, tmp_path: object
    ) -> None:
        """Verify .delete() called even when processing raises."""
        frame_length = 512
        num_samples = frame_length

        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        mock_cobra = _make_mock_cobra(frame_length, [])
        mock_cobra.process.side_effect = RuntimeError("boom")
        _mock_pvcobra_module.create.return_value = mock_cobra

        with pytest.raises(RuntimeError, match="boom"):
            run_vad(
                input_path,
                os.path.join(str(tmp_path), "out"),
                access_key="test-key",
            )

        mock_cobra.delete.assert_called_once()

    def test_vad_error_on_init_failure(
        self, _mock_pvcobra_module: MagicMock, tmp_path: object
    ) -> None:
        """VADError raised on Cobra init failure."""
        _mock_pvcobra_module.create.side_effect = RuntimeError("bad key")

        with pytest.raises(VADError, match="Failed to initialize Cobra"):
            run_vad(
                os.path.join(str(tmp_path), "input.wav"),
                os.path.join(str(tmp_path), "out"),
                access_key="bad-key",
            )

    def test_output_wav_contains_only_speech_frames(
        self, _mock_pvcobra_module: MagicMock, tmp_path: object
    ) -> None:
        """Output WAV should contain only speech frames."""
        frame_length = 512
        # 3 frames: speech, silence, speech
        probabilities = [0.9, 0.1, 0.8]
        num_samples = frame_length * 3

        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        mock_cobra = _make_mock_cobra(frame_length, probabilities)
        _mock_pvcobra_module.create.return_value = mock_cobra

        result = run_vad(
            input_path,
            os.path.join(str(tmp_path), "out"),
            access_key="test-key",
        )

        assert result.output_path is not None

        with wave.open(result.output_path, "rb") as wf:
            assert wf.getframerate() == SAMPLE_RATE
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            # 2 speech frames * frame_length samples
            assert wf.getnframes() == frame_length * 2
