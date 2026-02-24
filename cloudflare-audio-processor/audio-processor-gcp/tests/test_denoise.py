"""Tests for pluggable denoise engine interface, NullDenoiseEngine, and registry."""

import os
import struct
import wave

import pytest

from audio_processor.audio.denoise import (
    DenoiseEngine,
    DenoiseResult,
    NullDenoiseEngine,
    get_denoise_engine,
)
from audio_processor.audio.denoise.registry import DENOISE_ENGINES
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


class TestDenoiseEngineABC:
    """Tests for the DenoiseEngine abstract base class."""

    def test_cannot_instantiate_abc(self) -> None:
        """DenoiseEngine cannot be instantiated directly."""
        with pytest.raises(TypeError, match="abstract"):
            DenoiseEngine()  # type: ignore[abstract]

    def test_concrete_subclass_instantiates(self) -> None:
        """A concrete subclass that implements process() can be instantiated."""

        class StubEngine(DenoiseEngine):
            def process(self, input_path: str, output_dir: str) -> DenoiseResult:
                return DenoiseResult(
                    input_size_bytes=0,
                    output_size_bytes=0,
                    output_path="",
                )

        engine = StubEngine()
        assert isinstance(engine, DenoiseEngine)


class TestNullDenoiseEngine:
    """Tests for NullDenoiseEngine passthrough behavior."""

    def test_copies_input_to_output_unchanged(self, tmp_path: object) -> None:
        """NullDenoiseEngine copies input file with matching sizes."""
        num_samples = 8000
        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        engine = NullDenoiseEngine()
        result = engine.process(input_path, os.path.join(str(tmp_path), "out"))

        assert isinstance(result, DenoiseResult)
        assert result.input_size_bytes == result.output_size_bytes
        assert os.path.exists(result.output_path)

    def test_output_wav_readable_and_matches_input(
        self, tmp_path: object
    ) -> None:
        """Output WAV is readable and has same sample count as input."""
        num_samples = 3200
        input_path = os.path.join(str(tmp_path), "input.wav")
        _create_wav(input_path, num_samples)

        engine = NullDenoiseEngine()
        result = engine.process(input_path, os.path.join(str(tmp_path), "out"))

        with wave.open(result.output_path, "rb") as wf:
            assert wf.getnframes() == num_samples
            assert wf.getframerate() == 16000
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2


class TestDenoiseRegistry:
    """Tests for the denoise engine registry."""

    def test_get_null_engine(self) -> None:
        """get_denoise_engine('null') returns a NullDenoiseEngine instance."""
        engine = get_denoise_engine("null")
        assert isinstance(engine, NullDenoiseEngine)

    def test_unknown_provider_raises_denoise_error(self) -> None:
        """get_denoise_engine('unknown') raises DenoiseError."""
        with pytest.raises(DenoiseError, match="Unknown denoise provider: 'unknown'"):
            get_denoise_engine("unknown")

    def test_error_lists_available_providers(self) -> None:
        """Error message includes names of all registered providers."""
        with pytest.raises(DenoiseError) as exc_info:
            get_denoise_engine("nonexistent")
        message = str(exc_info.value)
        assert "null" in message
        assert "Available:" in message
