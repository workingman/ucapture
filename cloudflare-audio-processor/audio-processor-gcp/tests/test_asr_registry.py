"""Tests for ASR engine registry and provider selection."""

from unittest.mock import patch

import pytest

from audio_processor.asr.interface import ASREngine, Transcript
from audio_processor.asr.registry import ASR_ENGINES, get_asr_engine
from audio_processor.asr.speechmatics import SpeechmaticsEngine
from audio_processor.utils.errors import ASRError


class TestGetASREngine:
    """Tests for get_asr_engine factory function."""

    def test_speechmatics_returns_instance(self) -> None:
        """get_asr_engine('speechmatics') returns a SpeechmaticsEngine."""
        with patch.object(SpeechmaticsEngine, "__init__", lambda self, **kw: None):
            engine = get_asr_engine("speechmatics")
        assert isinstance(engine, SpeechmaticsEngine)

    def test_unknown_provider_raises_asr_error(self) -> None:
        """get_asr_engine('unknown') raises ASRError."""
        with pytest.raises(ASRError, match="Unknown ASR provider: 'unknown'"):
            get_asr_engine("unknown")

    def test_error_message_lists_available_providers(self) -> None:
        """Error message includes names of all registered providers."""
        with pytest.raises(ASRError) as exc_info:
            get_asr_engine("nonexistent")
        message = str(exc_info.value)
        assert "speechmatics" in message
        assert "Available:" in message

    def test_mock_engine_retrievable_from_registry(self) -> None:
        """A dynamically added engine class is retrievable."""

        class MockEngine(ASREngine):
            async def transcribe(
                self, audio_path: str, metadata: dict
            ) -> Transcript:
                return Transcript(segments=[], raw_response={})

        original = ASR_ENGINES.copy()
        try:
            ASR_ENGINES["mock"] = MockEngine
            engine = get_asr_engine("mock")
            assert isinstance(engine, MockEngine)
        finally:
            ASR_ENGINES.clear()
            ASR_ENGINES.update(original)

    def test_returned_engine_is_asr_engine_instance(self) -> None:
        """Returned engine satisfies isinstance(engine, ASREngine)."""
        with patch.object(SpeechmaticsEngine, "__init__", lambda self, **kw: None):
            engine = get_asr_engine("speechmatics")
        assert isinstance(engine, ASREngine)
