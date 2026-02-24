"""Tests for pluggable VAD engine interface, NullVADEngine, and registry."""

import os
import struct
import wave

import pytest

from audio_processor.audio.vad import (
    NullVADEngine,
    SpeechSegment,
    VADEngine,
    VADResult,
    get_vad_engine,
)
from audio_processor.audio.vad.registry import VAD_ENGINES
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


class TestVADRegistry:
    """Tests for the VAD engine registry."""

    def test_get_null_engine(self) -> None:
        """get_vad_engine('null') returns a NullVADEngine instance."""
        engine = get_vad_engine("null")
        assert isinstance(engine, NullVADEngine)

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
        assert "Available:" in message
