"""Tests for emotion analysis interface, GoogleNLEngine, and runner."""

import json
from dataclasses import asdict

import pytest

from audio_processor.asr.interface import TranscriptSegment, TranscriptWord
from audio_processor.emotion.interface import (
    EmotionEngine,
    EmotionResult,
    EmotionSegment,
)
from audio_processor.utils.errors import EmotionAnalysisError, PipelineError


# ---------------------------------------------------------------------------
# Sub-issue #32: EmotionEngine ABC, data classes, EmotionAnalysisError
# ---------------------------------------------------------------------------


class TestEmotionSegment:
    """Tests for EmotionSegment dataclass."""

    def test_fields(self) -> None:
        seg = EmotionSegment(
            segment_index=0,
            start_seconds=0.0,
            end_seconds=5.5,
            speaker="S1",
            text="hello world",
            analysis={"score": 0.8, "magnitude": 0.6},
        )
        assert seg.segment_index == 0
        assert seg.start_seconds == 0.0
        assert seg.end_seconds == 5.5
        assert seg.speaker == "S1"
        assert seg.text == "hello world"
        assert seg.analysis == {"score": 0.8, "magnitude": 0.6}


class TestEmotionResult:
    """Tests for EmotionResult dataclass and JSON serialization."""

    def test_serializes_to_tdd_envelope(self) -> None:
        result = EmotionResult(
            provider="google-cloud-nl",
            provider_version="v2",
            analyzed_at="2026-02-23T12:00:00Z",
            batch_id="batch-001",
            segments=[
                EmotionSegment(
                    segment_index=0,
                    start_seconds=0.0,
                    end_seconds=3.0,
                    speaker="S1",
                    text="hello",
                    analysis={"score": 0.5, "magnitude": 0.3},
                ),
            ],
        )
        data = asdict(result)
        serialized = json.dumps(data)
        parsed = json.loads(serialized)

        assert parsed["provider"] == "google-cloud-nl"
        assert parsed["provider_version"] == "v2"
        assert parsed["analyzed_at"] == "2026-02-23T12:00:00Z"
        assert parsed["batch_id"] == "batch-001"
        assert len(parsed["segments"]) == 1
        assert parsed["segments"][0]["analysis"] == {
            "score": 0.5,
            "magnitude": 0.3,
        }

    def test_empty_segments_serializes_correctly(self) -> None:
        result = EmotionResult(
            provider="google-cloud-nl",
            provider_version="v2",
            analyzed_at="2026-02-23T12:00:00Z",
            batch_id="batch-002",
            segments=[],
        )
        data = asdict(result)
        serialized = json.dumps(data)
        parsed = json.loads(serialized)

        assert parsed["segments"] == []
        assert parsed["provider"] == "google-cloud-nl"


class TestEmotionEngineABC:
    """Tests for EmotionEngine abstract base class."""

    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            EmotionEngine()  # type: ignore[abstract]

    def test_incomplete_subclass_raises_type_error(self) -> None:
        class IncompleteEngine(EmotionEngine):
            pass  # Missing all abstract members

        with pytest.raises(TypeError):
            IncompleteEngine()  # type: ignore[abstract]

    async def test_complete_subclass_can_be_instantiated(self) -> None:
        class MockEngine(EmotionEngine):
            @property
            def provider_name(self) -> str:
                return "mock"

            @property
            def provider_version(self) -> str:
                return "v1"

            async def analyze(
                self,
                segments: list[TranscriptSegment],
                audio_path: str | None = None,
            ) -> EmotionResult:
                return EmotionResult(
                    provider=self.provider_name,
                    provider_version=self.provider_version,
                    analyzed_at="2026-01-01T00:00:00Z",
                    batch_id="",
                    segments=[],
                )

        engine = MockEngine()
        assert isinstance(engine, EmotionEngine)
        assert engine.provider_name == "mock"
        result = await engine.analyze([])
        assert isinstance(result, EmotionResult)


class TestEmotionAnalysisError:
    """Tests for EmotionAnalysisError in utils/errors.py."""

    def test_is_subclass_of_pipeline_error(self) -> None:
        assert issubclass(EmotionAnalysisError, PipelineError)

    def test_importable_and_raisable(self) -> None:
        with pytest.raises(EmotionAnalysisError):
            raise EmotionAnalysisError("test error", batch_id="b1")
