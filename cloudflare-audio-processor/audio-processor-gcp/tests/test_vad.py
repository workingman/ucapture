"""Tests for pluggable VAD engine interface, NullVADEngine, SileroVADEngine, and registry."""

import os
import struct
import wave
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from audio_processor.audio.vad import (
    NullVADEngine,
    SileroVADEngine,
    SpeechSegment,
    VADEngine,
    VADResult,
    get_vad_engine,
)
from audio_processor.audio.vad.registry import VAD_ENGINES
from audio_processor.audio.vad.silero import FRAME_SIZE
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


class TestVADEngineABC:
    """Tests for the VADEngine abstract base class."""

    def test_cannot_instantiate_abc(self) -> None:
        """VADEngine cannot be instantiated directly."""
        with pytest.raises(TypeError, match="abstract"):
            VADEngine()  # type: ignore[abstract]

    def test_concrete_subclass_instantiates(self) -> None:
        """A concrete subclass that implements process() can be instantiated."""

        class StubEngine(VADEngine):
            def process(self, input_path: str, output_dir: str) -> VADResult:
                return VADResult(
                    segments=[],
                    total_duration_seconds=0.0,
                    speech_duration_seconds=0.0,
                    speech_ratio=0.0,
                    output_path="",
                )

        engine = StubEngine()
        assert isinstance(engine, VADEngine)


class TestNullVADEngine:
    """Tests for NullVADEngine passthrough behavior."""

    def test_returns_single_segment_spanning_all_audio(
        self, tmp_path: object
    ) -> None:
        """NullVADEngine returns one segment covering the entire file."""
        num_samples = 16000  # 1 second
        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        engine = NullVADEngine()
        result = engine.process(input_path, os.path.join(str(tmp_path), "out"))

        assert isinstance(result, VADResult)
        assert len(result.segments) == 1
        assert result.segments[0].start_sample == 0
        assert result.segments[0].end_sample == num_samples
        assert abs(result.segments[0].start_seconds - 0.0) < 1e-6
        assert abs(result.segments[0].end_seconds - 1.0) < 1e-6

    def test_speech_ratio_is_one(self, tmp_path: object) -> None:
        """NullVADEngine always reports speech_ratio=1.0."""
        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, 8000)

        engine = NullVADEngine()
        result = engine.process(input_path, os.path.join(str(tmp_path), "out"))

        assert result.speech_ratio == 1.0
        assert abs(result.speech_duration_seconds - result.total_duration_seconds) < 1e-6

    def test_output_file_is_copy_of_input(self, tmp_path: object) -> None:
        """Output WAV is a faithful copy of the input."""
        num_samples = 3200
        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        engine = NullVADEngine()
        result = engine.process(input_path, os.path.join(str(tmp_path), "out"))

        assert os.path.exists(result.output_path)
        with wave.open(result.output_path, "rb") as wf:
            assert wf.getnframes() == num_samples
            assert wf.getframerate() == 16000
            assert wf.getnchannels() == 1


def _make_mock_session(probabilities: list[float]) -> MagicMock:
    """Create a mock ONNX InferenceSession returning predetermined probabilities.

    Each call to session.run() returns the next probability and a fresh state tensor.
    """
    mock_session = MagicMock()
    call_count = [0]

    def mock_run(output_names, feed_dict):
        idx = call_count[0]
        call_count[0] += 1
        prob = probabilities[idx] if idx < len(probabilities) else 0.0
        output = np.array([[prob]], dtype=np.float32)
        new_state = np.zeros((2, 1, 128), dtype=np.float32)
        return [output, new_state]

    mock_session.run = MagicMock(side_effect=mock_run)
    return mock_session


class TestSileroVADEngine:
    """Tests for SileroVADEngine with mocked ONNX session."""

    def test_detects_speech_segments(self, tmp_path: object) -> None:
        """Known probabilities produce correct speech segments."""
        # 4 frames: speech, speech, silence, speech
        probabilities = [0.8, 0.9, 0.1, 0.7]
        num_samples = FRAME_SIZE * 4
        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        mock_session = _make_mock_session(probabilities)
        with patch("audio_processor.audio.vad.silero.ort") as mock_ort:
            mock_ort.InferenceSession.return_value = mock_session
            engine = SileroVADEngine(threshold=0.5)
            result = engine.process(
                input_path, os.path.join(str(tmp_path), "out")
            )

        assert isinstance(result, VADResult)
        # Frames 0-1 (speech), gap at frame 2 (0.064s < 0.25s merge threshold),
        # frame 3 (speech) => all merge into 1 segment
        assert len(result.segments) >= 1
        assert result.speech_duration_seconds > 0
        assert os.path.exists(result.output_path)

    def test_all_silence_produces_no_segments(self, tmp_path: object) -> None:
        """All-silence input produces zero segments and zero speech ratio."""
        probabilities = [0.0, 0.0, 0.0, 0.0]
        num_samples = FRAME_SIZE * 4
        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        mock_session = _make_mock_session(probabilities)
        with patch("audio_processor.audio.vad.silero.ort") as mock_ort:
            mock_ort.InferenceSession.return_value = mock_session
            engine = SileroVADEngine(threshold=0.5)
            result = engine.process(
                input_path, os.path.join(str(tmp_path), "out")
            )

        assert result.segments == []
        assert result.speech_duration_seconds == 0.0
        assert result.speech_ratio == 0.0

    def test_speech_ratio_calculation(self, tmp_path: object) -> None:
        """Speech ratio correctly reflects proportion of speech frames."""
        # 4 frames: 2 speech (0,1), 2 silence (2,3) => ratio ~0.5
        # With merging, frames 0-1 form one segment
        probabilities = [0.8, 0.9, 0.1, 0.2]
        num_samples = FRAME_SIZE * 4
        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        mock_session = _make_mock_session(probabilities)
        with patch("audio_processor.audio.vad.silero.ort") as mock_ort:
            mock_ort.InferenceSession.return_value = mock_session
            engine = SileroVADEngine(threshold=0.5)
            result = engine.process(
                input_path, os.path.join(str(tmp_path), "out")
            )

        assert abs(result.speech_ratio - 0.5) < 0.01

    def test_output_wav_contains_only_speech_frames(
        self, tmp_path: object
    ) -> None:
        """Output WAV contains only speech frame samples."""
        # 4 frames: speech, silence, silence, speech
        # Gap between frame 0 and frame 3 is 3*512/16000 = 0.096s < 0.25s
        # So they merge, giving all 4 frames worth of samples
        # Use wider gap to avoid merge: need > 0.25s silence = > 7.8 frames
        # 10 frames: 2 speech, 8 silence => gap = 8*0.032 = 0.256s > 0.25s
        probabilities = [0.8, 0.9] + [0.1] * 8
        num_samples = FRAME_SIZE * 10
        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        mock_session = _make_mock_session(probabilities)
        with patch("audio_processor.audio.vad.silero.ort") as mock_ort:
            mock_ort.InferenceSession.return_value = mock_session
            engine = SileroVADEngine(threshold=0.5)
            result = engine.process(
                input_path, os.path.join(str(tmp_path), "out")
            )

        with wave.open(result.output_path, "rb") as wf:
            # 2 speech frames * FRAME_SIZE samples
            assert wf.getnframes() == FRAME_SIZE * 2

    def test_model_load_failure_raises_vad_error(self) -> None:
        """VADError raised when ONNX model cannot be loaded."""
        with patch("audio_processor.audio.vad.silero.ort") as mock_ort:
            mock_ort.InferenceSession.side_effect = RuntimeError("bad model")
            with pytest.raises(VADError, match="Failed to load Silero VAD model"):
                SileroVADEngine(model_path="/nonexistent/model.onnx")


class TestVADRegistry:
    """Tests for the VAD engine registry."""

    def test_get_null_engine(self) -> None:
        """get_vad_engine('null') returns a NullVADEngine instance."""
        engine = get_vad_engine("null")
        assert isinstance(engine, NullVADEngine)

    def test_get_silero_engine(self) -> None:
        """get_vad_engine('silero') returns a SileroVADEngine instance."""
        with patch("audio_processor.audio.vad.silero.ort") as mock_ort:
            mock_ort.InferenceSession.return_value = MagicMock()
            engine = get_vad_engine("silero")
        assert isinstance(engine, SileroVADEngine)

    def test_unknown_provider_raises_vad_error(self) -> None:
        """get_vad_engine('unknown') raises VADError."""
        with pytest.raises(VADError, match="Unknown VAD provider: 'unknown'"):
            get_vad_engine("unknown")

    def test_error_lists_available_providers(self) -> None:
        """Error message includes names of all registered providers."""
        with pytest.raises(VADError) as exc_info:
            get_vad_engine("nonexistent")
        message = str(exc_info.value)
        assert "null" in message
        assert "silero" in message
        assert "Available:" in message
