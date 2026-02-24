"""Tests for emotion analysis interface, GoogleNLEngine, and runner."""

import json
import sys
from dataclasses import asdict
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from audio_processor.asr.interface import TranscriptSegment, TranscriptWord
from audio_processor.emotion.interface import (
    EmotionEngine,
    EmotionResult,
    EmotionSegment,
)
from audio_processor.utils.errors import EmotionAnalysisError, PipelineError

# Mock google.cloud.language_v2 before importing GoogleNLEngine so tests
# work without the google-cloud-language package installed.
_mock_language_v2 = MagicMock()
sys.modules.setdefault("google", MagicMock())
sys.modules.setdefault("google.cloud", MagicMock())
sys.modules.setdefault("google.cloud.language_v2", _mock_language_v2)


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


# ---------------------------------------------------------------------------
# Sub-issue #33: GoogleNLEngine
# ---------------------------------------------------------------------------


def _make_segment(
    speaker: str, words: list[tuple[str, float, float]]
) -> TranscriptSegment:
    """Helper to create a TranscriptSegment from word tuples."""
    return TranscriptSegment(
        speaker_label=speaker,
        words=[
            TranscriptWord(text=t, start_time=s, end_time=e, confidence=0.99)
            for t, s, e in words
        ],
    )


def _mock_sentiment(score: float, magnitude: float) -> MagicMock:
    """Create a mock sentiment response from the Google NL API."""
    sentiment = MagicMock()
    sentiment.score = score
    sentiment.magnitude = magnitude

    response = MagicMock()
    response.document_sentiment = sentiment
    return response


class TestGoogleNLEngine:
    """Tests for GoogleNLEngine implementation."""

    def _make_engine(self, client: MagicMock) -> "GoogleNLEngine":
        """Create a GoogleNLEngine with an injected mock client."""
        from audio_processor.emotion.google_nl import GoogleNLEngine

        return GoogleNLEngine(client=client)

    async def test_analysis_contains_score_and_magnitude(self) -> None:
        mock_client = MagicMock()
        mock_client.analyze_sentiment.return_value = _mock_sentiment(0.7, 0.5)

        engine = self._make_engine(mock_client)
        segments = [_make_segment("S1", [("hello", 0.0, 0.5)])]
        result = await engine.analyze(segments)

        assert len(result.segments) == 1
        analysis = result.segments[0].analysis
        assert isinstance(analysis["score"], float)
        assert isinstance(analysis["magnitude"], float)
        assert analysis["score"] == 0.7
        assert analysis["magnitude"] == 0.5

    async def test_multiple_segments_each_get_api_call(self) -> None:
        mock_client = MagicMock()
        mock_client.analyze_sentiment.side_effect = [
            _mock_sentiment(0.3, 0.2),
            _mock_sentiment(-0.5, 0.8),
        ]

        engine = self._make_engine(mock_client)
        segments = [
            _make_segment("S1", [("hello", 0.0, 0.5)]),
            _make_segment("S2", [("world", 1.0, 1.5)]),
        ]
        result = await engine.analyze(segments)

        assert len(result.segments) == 2
        assert mock_client.analyze_sentiment.call_count == 2
        assert result.segments[0].analysis["score"] == 0.3
        assert result.segments[1].analysis["score"] == -0.5

    async def test_provider_fields_correct(self) -> None:
        mock_client = MagicMock()
        mock_client.analyze_sentiment.return_value = _mock_sentiment(0.0, 0.0)

        engine = self._make_engine(mock_client)
        result = await engine.analyze(
            [_make_segment("S1", [("test", 0.0, 0.5)])]
        )

        assert result.provider == "google-cloud-nl"
        assert result.provider_version == "v2"
        assert result.batch_id == ""

    async def test_analyzed_at_is_valid_iso8601_utc(self) -> None:
        mock_client = MagicMock()
        mock_client.analyze_sentiment.return_value = _mock_sentiment(0.0, 0.0)

        engine = self._make_engine(mock_client)
        result = await engine.analyze(
            [_make_segment("S1", [("test", 0.0, 0.5)])]
        )

        # Should parse without error and contain UTC info
        parsed = datetime.fromisoformat(result.analyzed_at)
        assert parsed.tzinfo is not None

    async def test_api_exception_raises_emotion_analysis_error(self) -> None:
        mock_client = MagicMock()
        mock_client.analyze_sentiment.side_effect = RuntimeError("API down")

        engine = self._make_engine(mock_client)
        with pytest.raises(EmotionAnalysisError, match="API down"):
            await engine.analyze(
                [_make_segment("S1", [("test", 0.0, 0.5)])]
            )

    async def test_segment_text_built_from_words(self) -> None:
        mock_client = MagicMock()
        mock_client.analyze_sentiment.return_value = _mock_sentiment(0.1, 0.2)

        engine = self._make_engine(mock_client)
        segments = [
            _make_segment("S1", [("hello", 0.0, 0.3), ("world", 0.4, 0.7)])
        ]
        result = await engine.analyze(segments)

        assert result.segments[0].text == "hello world"
        assert result.segments[0].start_seconds == 0.0
        assert result.segments[0].end_seconds == 0.7
        assert result.segments[0].speaker == "S1"


# ---------------------------------------------------------------------------
# Sub-issue #34: Emotion runner with provider registry
# ---------------------------------------------------------------------------


from dataclasses import dataclass as _dataclass
from unittest.mock import AsyncMock, patch

from audio_processor.asr.interface import Transcript
from audio_processor.emotion.runner import run_emotion_analysis


@_dataclass
class _FakeConfig:
    """Minimal config object for testing the runner."""

    emotion_provider: str | None = None


def _make_transcript(
    segments: list[TranscriptSegment] | None = None,
) -> Transcript:
    """Create a Transcript with the given segments."""
    return Transcript(segments=segments or [], raw_response={})


class TestEmotionRunner:
    """Tests for run_emotion_analysis runner function."""

    async def test_registered_provider_returns_result(self) -> None:
        mock_result = EmotionResult(
            provider="google-cloud-nl",
            provider_version="v2",
            analyzed_at="2026-01-01T00:00:00Z",
            batch_id="",
            segments=[
                EmotionSegment(
                    segment_index=0,
                    start_seconds=0.0,
                    end_seconds=0.5,
                    speaker="S1",
                    text="hello",
                    analysis={"score": 0.5, "magnitude": 0.3},
                ),
            ],
        )
        mock_engine = AsyncMock()
        mock_engine.analyze.return_value = mock_result

        with patch(
            "audio_processor.emotion.runner.EMOTION_ENGINES",
            {"google-cloud-nl": MagicMock(return_value=mock_engine)},
        ):
            transcript = _make_transcript(
                [_make_segment("S1", [("hello", 0.0, 0.5)])]
            )
            config = _FakeConfig(emotion_provider="google-cloud-nl")
            result = await run_emotion_analysis(transcript, None, config)

        assert result is not None
        assert result.provider == "google-cloud-nl"
        assert len(result.segments) == 1

    async def test_empty_segments_returns_result_with_empty_list(self) -> None:
        with patch(
            "audio_processor.emotion.runner.EMOTION_ENGINES",
            {"google-cloud-nl": MagicMock(return_value=MagicMock(
                provider_name="google-cloud-nl",
                provider_version="v2",
            ))},
        ):
            transcript = _make_transcript([])
            config = _FakeConfig(emotion_provider="google-cloud-nl")
            result = await run_emotion_analysis(transcript, None, config)

        assert result is not None
        assert result.segments == []
        assert result.provider == "google-cloud-nl"

    async def test_engine_exception_returns_none(self) -> None:
        mock_engine = AsyncMock()
        mock_engine.analyze.side_effect = RuntimeError("boom")

        with patch(
            "audio_processor.emotion.runner.EMOTION_ENGINES",
            {"google-cloud-nl": MagicMock(return_value=mock_engine)},
        ):
            transcript = _make_transcript(
                [_make_segment("S1", [("test", 0.0, 0.5)])]
            )
            config = _FakeConfig(emotion_provider="google-cloud-nl")
            result = await run_emotion_analysis(transcript, None, config)

        assert result is None

    async def test_unknown_provider_returns_none(self) -> None:
        transcript = _make_transcript(
            [_make_segment("S1", [("test", 0.0, 0.5)])]
        )
        config = _FakeConfig(emotion_provider="nonexistent-provider")
        result = await run_emotion_analysis(transcript, None, config)

        assert result is None

    async def test_none_provider_returns_none(self) -> None:
        transcript = _make_transcript(
            [_make_segment("S1", [("test", 0.0, 0.5)])]
        )
        config = _FakeConfig(emotion_provider=None)
        result = await run_emotion_analysis(transcript, None, config)

        assert result is None

    async def test_empty_string_provider_returns_none(self) -> None:
        transcript = _make_transcript(
            [_make_segment("S1", [("test", 0.0, 0.5)])]
        )
        config = _FakeConfig(emotion_provider="")
        result = await run_emotion_analysis(transcript, None, config)

        assert result is None

    async def test_unknown_provider_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        with caplog.at_level(logging.WARNING):
            transcript = _make_transcript(
                [_make_segment("S1", [("test", 0.0, 0.5)])]
            )
            config = _FakeConfig(emotion_provider="unknown-thing")
            await run_emotion_analysis(transcript, None, config)

        assert "Unknown emotion provider" in caplog.text
