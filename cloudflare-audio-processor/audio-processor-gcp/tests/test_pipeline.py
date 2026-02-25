"""Tests for audio_processor.pipeline module."""

from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from audio_processor.asr.interface import Transcript, TranscriptSegment, TranscriptWord
from audio_processor.audio.denoise.interface import DenoiseResult
from audio_processor.audio.transcode import TranscodeResult
from audio_processor.audio.vad.interface import SpeechSegment, VADResult
from audio_processor.emotion.interface import EmotionResult, EmotionSegment
from audio_processor.pipeline import (
    SPEECHMATICS_COST_PER_SECOND,
    ProcessingResult,
    _build_batch_metrics,
    _build_completion_event,
    _build_stage_rows,
    _determine_error_stage,
    process_batch,
)
from audio_processor.utils.errors import ASRError, AudioFetchError, StorageError


def _make_transcript() -> Transcript:
    """Create a minimal valid Transcript for testing."""
    return Transcript(
        segments=[
            TranscriptSegment(
                speaker_label="Speaker 1",
                words=[
                    TranscriptWord(
                        text="Hello",
                        start_time=0.0,
                        end_time=0.5,
                        confidence=0.99,
                    ),
                    TranscriptWord(
                        text="world",
                        start_time=0.5,
                        end_time=1.0,
                        confidence=0.98,
                    ),
                ],
            ),
        ],
        raw_response={"results": [{"type": "word", "alternatives": [{"content": "Hello"}]}]},
    )


def _make_vad_result(has_speech: bool = True) -> VADResult:
    """Create a VADResult for testing."""
    if has_speech:
        return VADResult(
            segments=[SpeechSegment(0, 16000, 0.0, 1.0)],
            total_duration_seconds=2.0,
            speech_duration_seconds=1.0,
            speech_ratio=0.5,
            output_path="/tmp/test_speech.wav",
        )
    return VADResult(
        segments=[],
        total_duration_seconds=2.0,
        speech_duration_seconds=0.0,
        speech_ratio=0.0,
        output_path="/tmp/test_speech.wav",
    )


def _make_transcode_result() -> TranscodeResult:
    """Create a TranscodeResult for testing."""
    return TranscodeResult(
        input_path="/tmp/recording.m4a",
        output_path="/tmp/recording.wav",
        input_size_bytes=100000,
        output_size_bytes=320000,
        duration_seconds=10.0,
    )


def _make_denoise_result() -> DenoiseResult:
    """Create a DenoiseResult for testing."""
    return DenoiseResult(
        input_size_bytes=320000,
        output_size_bytes=320000,
        output_path="/tmp/cleaned.wav",
    )


def _make_emotion_result() -> EmotionResult:
    """Create an EmotionResult for testing."""
    return EmotionResult(
        provider="google-cloud-nl",
        provider_version="v2",
        analyzed_at="2026-02-24T10:00:00Z",
        batch_id="batch-123",
        segments=[
            EmotionSegment(
                segment_index=0,
                start_seconds=0.0,
                end_seconds=1.0,
                speaker="Speaker 1",
                text="Hello world",
                analysis={"sentiment": "positive", "score": 0.8},
            ),
        ],
    )


@pytest.fixture
def mock_r2_client():
    """Create a mock R2Client."""
    client = MagicMock()
    client.fetch_object.return_value = b"fake-audio-bytes"
    client.put_object.return_value = None
    return client


@pytest.fixture
def mock_d1_client():
    """Create a mock D1Client."""
    client = AsyncMock()
    client.update_batch_status.return_value = None
    client.publish_completion_event.return_value = None
    return client


class TestProcessBatchHappyPath:
    """Tests for the happy path through process_batch()."""

    @patch("audio_processor.pipeline.run_emotion_analysis")
    @patch("audio_processor.pipeline.insert_timestamp_markers")
    @patch("audio_processor.pipeline.get_asr_engine")
    @patch("audio_processor.pipeline.get_denoise_engine")
    @patch("audio_processor.pipeline.get_vad_engine")
    @patch("audio_processor.pipeline.transcode_to_wav")
    async def test_happy_path_returns_completed(
        self,
        mock_transcode,
        mock_get_vad,
        mock_get_denoise,
        mock_get_asr,
        mock_insert_markers,
        mock_run_emotion,
        mock_r2_client,
        mock_d1_client,
    ):
        """Full happy path produces completed result with all artifacts."""
        # Arrange
        mock_transcode.return_value = _make_transcode_result()

        mock_vad_engine = MagicMock()
        mock_vad_engine.process.return_value = _make_vad_result(has_speech=True)
        mock_get_vad.return_value = mock_vad_engine

        mock_denoise_engine = MagicMock()
        mock_denoise_engine.process.return_value = _make_denoise_result()
        mock_get_denoise.return_value = mock_denoise_engine

        mock_asr_engine = AsyncMock()
        mock_asr_engine.transcribe.return_value = _make_transcript()
        mock_get_asr.return_value = mock_asr_engine

        mock_insert_markers.return_value = "[00:00] Speaker 1: Hello world"
        mock_run_emotion.return_value = _make_emotion_result()

        # Mock file reads for store stage
        mock_open_data = b"cleaned-wav-data"
        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_open.return_value.__exit__ = MagicMock(return_value=False)

            # We need to handle multiple open() calls
            file_mock_write = MagicMock()
            file_mock_read = MagicMock()
            file_mock_read.read.return_value = mock_open_data

            call_count = [0]

            def side_effect(path, mode="r"):
                call_count[0] += 1
                ctx = MagicMock()
                if "w" in mode:
                    ctx.__enter__ = MagicMock(return_value=file_mock_write)
                else:
                    ctx.__enter__ = MagicMock(return_value=file_mock_read)
                ctx.__exit__ = MagicMock(return_value=False)
                return ctx

            mock_open.side_effect = side_effect

            with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                mock_tmpdir.return_value.__enter__ = MagicMock(
                    return_value="/tmp/test_pipeline"
                )
                mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)

                # Act
                result = await process_batch(
                    batch_id="batch-123",
                    user_id="user-1",
                    r2_client=mock_r2_client,
                    d1_client=mock_d1_client,
                )

        # Assert
        assert result.status == "completed"
        assert result.batch_id == "batch-123"
        assert "transcript_formatted" in result.artifact_paths
        assert "transcript_raw" in result.artifact_paths
        assert "raw_audio" in result.artifact_paths
        assert result.metrics.raw_audio_duration_seconds == 10.0
        assert result.error is None

    @patch("audio_processor.pipeline.run_emotion_analysis")
    @patch("audio_processor.pipeline.insert_timestamp_markers")
    @patch("audio_processor.pipeline.get_asr_engine")
    @patch("audio_processor.pipeline.get_denoise_engine")
    @patch("audio_processor.pipeline.get_vad_engine")
    @patch("audio_processor.pipeline.transcode_to_wav")
    async def test_happy_path_publishes_completion_event(
        self,
        mock_transcode,
        mock_get_vad,
        mock_get_denoise,
        mock_get_asr,
        mock_insert_markers,
        mock_run_emotion,
        mock_r2_client,
        mock_d1_client,
    ):
        """Happy path publishes a completion event with status 'completed'."""
        mock_transcode.return_value = _make_transcode_result()
        mock_vad_engine = MagicMock()
        mock_vad_engine.process.return_value = _make_vad_result(has_speech=True)
        mock_get_vad.return_value = mock_vad_engine
        mock_denoise_engine = MagicMock()
        mock_denoise_engine.process.return_value = _make_denoise_result()
        mock_get_denoise.return_value = mock_denoise_engine
        mock_asr_engine = AsyncMock()
        mock_asr_engine.transcribe.return_value = _make_transcript()
        mock_get_asr.return_value = mock_asr_engine
        mock_insert_markers.return_value = "Hello world"
        mock_run_emotion.return_value = None

        with patch("builtins.open", create=True) as mock_open:
            file_mock = MagicMock()
            file_mock.read.return_value = b"data"

            def side_effect(path, mode="r"):
                ctx = MagicMock()
                ctx.__enter__ = MagicMock(return_value=file_mock)
                ctx.__exit__ = MagicMock(return_value=False)
                return ctx

            mock_open.side_effect = side_effect

            with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                mock_tmpdir.return_value.__enter__ = MagicMock(
                    return_value="/tmp/test"
                )
                mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
                await process_batch(
                    "batch-123", "user-1", mock_r2_client, mock_d1_client
                )

        mock_d1_client.publish_completion_event.assert_called_once()
        event = mock_d1_client.publish_completion_event.call_args[0][0]
        assert event["status"] == "completed"
        assert event["batch_id"] == "batch-123"
        assert event["user_id"] == "user-1"

    @patch("audio_processor.pipeline.run_emotion_analysis")
    @patch("audio_processor.pipeline.insert_timestamp_markers")
    @patch("audio_processor.pipeline.get_asr_engine")
    @patch("audio_processor.pipeline.get_denoise_engine")
    @patch("audio_processor.pipeline.get_vad_engine")
    @patch("audio_processor.pipeline.transcode_to_wav")
    async def test_stage_timings_recorded(
        self,
        mock_transcode,
        mock_get_vad,
        mock_get_denoise,
        mock_get_asr,
        mock_insert_markers,
        mock_run_emotion,
        mock_r2_client,
        mock_d1_client,
    ):
        """Stage timings are recorded in metrics."""
        mock_transcode.return_value = _make_transcode_result()
        mock_vad_engine = MagicMock()
        mock_vad_engine.process.return_value = _make_vad_result(has_speech=True)
        mock_get_vad.return_value = mock_vad_engine
        mock_denoise_engine = MagicMock()
        mock_denoise_engine.process.return_value = _make_denoise_result()
        mock_get_denoise.return_value = mock_denoise_engine
        mock_asr_engine = AsyncMock()
        mock_asr_engine.transcribe.return_value = _make_transcript()
        mock_get_asr.return_value = mock_asr_engine
        mock_insert_markers.return_value = "text"
        mock_run_emotion.return_value = None

        with patch("builtins.open", create=True) as mock_open:
            file_mock = MagicMock()
            file_mock.read.return_value = b"data"

            def side_effect(path, mode="r"):
                ctx = MagicMock()
                ctx.__enter__ = MagicMock(return_value=file_mock)
                ctx.__exit__ = MagicMock(return_value=False)
                return ctx

            mock_open.side_effect = side_effect

            with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                mock_tmpdir.return_value.__enter__ = MagicMock(
                    return_value="/tmp/test"
                )
                mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
                result = await process_batch(
                    "batch-123", "user-1", mock_r2_client, mock_d1_client
                )

        timings = result.metrics.stage_timings
        assert "fetch" in timings
        assert "transcode" in timings
        assert "vad" in timings
        assert "denoise" in timings
        assert "asr" in timings
        assert "postprocess" in timings
        assert "store" in timings


class TestProcessBatchZeroSpeech:
    """Tests for zero-speech batch handling."""

    @patch("audio_processor.pipeline.get_vad_engine")
    @patch("audio_processor.pipeline.transcode_to_wav")
    async def test_zero_speech_completes_with_empty_transcript(
        self,
        mock_transcode,
        mock_get_vad,
        mock_r2_client,
        mock_d1_client,
    ):
        """Zero-speech batch completes with empty formatted transcript."""
        mock_transcode.return_value = _make_transcode_result()
        mock_vad_engine = MagicMock()
        mock_vad_engine.process.return_value = _make_vad_result(has_speech=False)
        mock_get_vad.return_value = mock_vad_engine

        with patch("builtins.open", create=True) as mock_open:
            file_mock = MagicMock()

            def side_effect(path, mode="r"):
                ctx = MagicMock()
                ctx.__enter__ = MagicMock(return_value=file_mock)
                ctx.__exit__ = MagicMock(return_value=False)
                return ctx

            mock_open.side_effect = side_effect

            with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                mock_tmpdir.return_value.__enter__ = MagicMock(
                    return_value="/tmp/test"
                )
                mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
                result = await process_batch(
                    "batch-123", "user-1", mock_r2_client, mock_d1_client
                )

        assert result.status == "completed"
        assert result.metrics.speech_duration_seconds == 0.0
        assert result.metrics.speech_ratio == 0.0
        assert result.metrics.cleaned_audio_size_bytes == 0
        assert "transcript_formatted" in result.artifact_paths
        # No cleaned_audio for zero-speech
        assert "cleaned_audio" not in result.artifact_paths
        # No emotion for zero-speech
        assert "transcript_emotion" not in result.artifact_paths

    @patch("audio_processor.pipeline.get_vad_engine")
    @patch("audio_processor.pipeline.transcode_to_wav")
    async def test_zero_speech_stores_empty_formatted_txt(
        self,
        mock_transcode,
        mock_get_vad,
        mock_r2_client,
        mock_d1_client,
    ):
        """Zero-speech batch stores empty bytes as formatted.txt."""
        mock_transcode.return_value = _make_transcode_result()
        mock_vad_engine = MagicMock()
        mock_vad_engine.process.return_value = _make_vad_result(has_speech=False)
        mock_get_vad.return_value = mock_vad_engine

        with patch("builtins.open", create=True) as mock_open:
            file_mock = MagicMock()

            def side_effect(path, mode="r"):
                ctx = MagicMock()
                ctx.__enter__ = MagicMock(return_value=file_mock)
                ctx.__exit__ = MagicMock(return_value=False)
                return ctx

            mock_open.side_effect = side_effect

            with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                mock_tmpdir.return_value.__enter__ = MagicMock(
                    return_value="/tmp/test"
                )
                mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
                await process_batch(
                    "batch-123", "user-1", mock_r2_client, mock_d1_client
                )

        # Verify put_object was called with empty bytes for formatted.txt
        put_calls = mock_r2_client.put_object.call_args_list
        formatted_call = [
            c for c in put_calls if "formatted.txt" in str(c)
        ]
        assert len(formatted_call) == 1
        assert formatted_call[0][0][1] == b""  # empty bytes


class TestProcessBatchEmotionFailure:
    """Tests for emotion failure graceful degradation."""

    @patch("audio_processor.pipeline.run_emotion_analysis")
    @patch("audio_processor.pipeline.insert_timestamp_markers")
    @patch("audio_processor.pipeline.get_asr_engine")
    @patch("audio_processor.pipeline.get_denoise_engine")
    @patch("audio_processor.pipeline.get_vad_engine")
    @patch("audio_processor.pipeline.transcode_to_wav")
    async def test_emotion_failure_still_completes(
        self,
        mock_transcode,
        mock_get_vad,
        mock_get_denoise,
        mock_get_asr,
        mock_insert_markers,
        mock_run_emotion,
        mock_r2_client,
        mock_d1_client,
    ):
        """Batch completes even if emotion analysis raises an exception."""
        mock_transcode.return_value = _make_transcode_result()
        mock_vad_engine = MagicMock()
        mock_vad_engine.process.return_value = _make_vad_result(has_speech=True)
        mock_get_vad.return_value = mock_vad_engine
        mock_denoise_engine = MagicMock()
        mock_denoise_engine.process.return_value = _make_denoise_result()
        mock_get_denoise.return_value = mock_denoise_engine
        mock_asr_engine = AsyncMock()
        mock_asr_engine.transcribe.return_value = _make_transcript()
        mock_get_asr.return_value = mock_asr_engine
        mock_insert_markers.return_value = "formatted text"

        # Emotion raises exception
        mock_run_emotion.side_effect = RuntimeError("Emotion service down")

        with patch("builtins.open", create=True) as mock_open:
            file_mock = MagicMock()
            file_mock.read.return_value = b"data"

            def side_effect(path, mode="r"):
                ctx = MagicMock()
                ctx.__enter__ = MagicMock(return_value=file_mock)
                ctx.__exit__ = MagicMock(return_value=False)
                return ctx

            mock_open.side_effect = side_effect

            with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                mock_tmpdir.return_value.__enter__ = MagicMock(
                    return_value="/tmp/test"
                )
                mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
                result = await process_batch(
                    "batch-123", "user-1", mock_r2_client, mock_d1_client
                )

        assert result.status == "completed"
        assert "transcript_emotion" not in result.artifact_paths
        assert result.error is None


class TestProcessBatchFailure:
    """Tests for pipeline failure handling."""

    async def test_fetch_failure_returns_failed_result(
        self, mock_r2_client, mock_d1_client
    ):
        """AudioFetchError during fetch returns failed result with error_stage."""
        mock_r2_client.fetch_object.side_effect = AudioFetchError(
            "Object not found", key="user-1/batch-123/raw-audio/recording.m4a"
        )

        with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
            mock_tmpdir.return_value.__enter__ = MagicMock(
                return_value="/tmp/test"
            )
            mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
            result = await process_batch(
                "batch-123", "user-1", mock_r2_client, mock_d1_client
            )

        assert result.status == "failed"
        assert result.error is not None
        assert result.error.stage == "fetch"
        assert "Object not found" in result.error.message

    async def test_failure_updates_d1_with_error_fields(
        self, mock_r2_client, mock_d1_client
    ):
        """Pipeline failure updates D1 with error_stage and error_message."""
        mock_r2_client.fetch_object.side_effect = AudioFetchError(
            "Not found", key="key"
        )

        with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
            mock_tmpdir.return_value.__enter__ = MagicMock(
                return_value="/tmp/test"
            )
            mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
            await process_batch(
                "batch-123", "user-1", mock_r2_client, mock_d1_client
            )

        mock_d1_client.update_batch_status.assert_called_once()
        call_kwargs = mock_d1_client.update_batch_status.call_args[1]
        assert call_kwargs["status"] == "failed"
        assert call_kwargs["error_stage"] == "fetch"
        assert "Not found" in call_kwargs["error_message"]

    async def test_failure_publishes_failure_event(
        self, mock_r2_client, mock_d1_client
    ):
        """Pipeline failure publishes completion event with status 'failed'."""
        mock_r2_client.fetch_object.side_effect = AudioFetchError(
            "Not found", key="key"
        )

        with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
            mock_tmpdir.return_value.__enter__ = MagicMock(
                return_value="/tmp/test"
            )
            mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
            await process_batch(
                "batch-123", "user-1", mock_r2_client, mock_d1_client
            )

        mock_d1_client.publish_completion_event.assert_called_once()
        event = mock_d1_client.publish_completion_event.call_args[0][0]
        assert event["status"] == "failed"
        assert "error_message" in event

    @patch("audio_processor.pipeline.get_vad_engine")
    @patch("audio_processor.pipeline.transcode_to_wav")
    async def test_raw_audio_never_deleted_on_failure(
        self,
        mock_transcode,
        mock_get_vad,
        mock_r2_client,
        mock_d1_client,
    ):
        """Raw audio R2 key is never passed to a delete operation on failure."""
        mock_transcode.return_value = _make_transcode_result()
        mock_vad_engine = MagicMock()
        mock_vad_engine.process.side_effect = RuntimeError("VAD crashed")
        mock_get_vad.return_value = mock_vad_engine

        with patch("builtins.open", create=True) as mock_open:
            file_mock = MagicMock()

            def side_effect(path, mode="r"):
                ctx = MagicMock()
                ctx.__enter__ = MagicMock(return_value=file_mock)
                ctx.__exit__ = MagicMock(return_value=False)
                return ctx

            mock_open.side_effect = side_effect

            with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                mock_tmpdir.return_value.__enter__ = MagicMock(
                    return_value="/tmp/test"
                )
                mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
                result = await process_batch(
                    "batch-123", "user-1", mock_r2_client, mock_d1_client
                )

        assert result.status == "failed"
        # Verify no delete_object calls were made on the R2 client
        assert not hasattr(mock_r2_client, "delete_object") or \
            not mock_r2_client.delete_object.called


class TestDetermineErrorStage:
    """Tests for _determine_error_stage helper."""

    def test_first_incomplete_stage_returned(self):
        """Returns the first stage not in timings."""
        timings = {"fetch": 0.1, "transcode": 0.2}
        exc = RuntimeError("fail")
        assert _determine_error_stage(exc, timings) == "vad"

    def test_no_timings_returns_fetch(self):
        """With no timings, the first stage (fetch) is returned."""
        assert _determine_error_stage(RuntimeError("fail"), {}) == "fetch"


class TestBuildCompletionEvent:
    """Tests for _build_completion_event helper."""

    def test_completed_event_structure(self):
        """Completed event has correct fields."""
        event = _build_completion_event(
            batch_id="b1",
            user_id="u1",
            status="completed",
            artifact_paths={"raw_audio": "u1/b1/raw-audio/recording.m4a"},
        )
        assert event["batch_id"] == "b1"
        assert event["user_id"] == "u1"
        assert event["status"] == "completed"
        assert "published_at" in event
        assert "error_message" not in event

    def test_failed_event_includes_error_message(self):
        """Failed event includes error_message field."""
        event = _build_completion_event(
            batch_id="b1",
            user_id="u1",
            status="failed",
            artifact_paths={},
            error_message="Speechmatics timeout",
        )
        assert event["error_message"] == "Speechmatics timeout"


class TestMetricsIntegration:
    """Tests for BatchMetrics integration into pipeline (#36)."""

    @patch("audio_processor.pipeline.log_batch_metrics")
    @patch("audio_processor.pipeline.run_emotion_analysis")
    @patch("audio_processor.pipeline.insert_timestamp_markers")
    @patch("audio_processor.pipeline.get_asr_engine")
    @patch("audio_processor.pipeline.get_denoise_engine")
    @patch("audio_processor.pipeline.get_vad_engine")
    @patch("audio_processor.pipeline.transcode_to_wav")
    async def test_success_emits_fully_populated_metrics(
        self,
        mock_transcode,
        mock_get_vad,
        mock_get_denoise,
        mock_get_asr,
        mock_insert_markers,
        mock_run_emotion,
        mock_log_metrics,
        mock_r2_client,
        mock_d1_client,
    ):
        """Successful pipeline run emits log_batch_metrics with all fields populated."""
        mock_transcode.return_value = _make_transcode_result()
        mock_vad_engine = MagicMock()
        mock_vad_engine.process.return_value = _make_vad_result(has_speech=True)
        mock_get_vad.return_value = mock_vad_engine
        mock_denoise_engine = MagicMock()
        mock_denoise_engine.process.return_value = _make_denoise_result()
        mock_get_denoise.return_value = mock_denoise_engine
        mock_asr_engine = AsyncMock()
        mock_asr_engine.transcribe.return_value = _make_transcript()
        mock_get_asr.return_value = mock_asr_engine
        mock_insert_markers.return_value = "Hello world"
        mock_run_emotion.return_value = None

        with patch("builtins.open", create=True) as mock_open:
            file_mock = MagicMock()
            file_mock.read.return_value = b"data"

            def side_effect(path, mode="r"):
                ctx = MagicMock()
                ctx.__enter__ = MagicMock(return_value=file_mock)
                ctx.__exit__ = MagicMock(return_value=False)
                return ctx

            mock_open.side_effect = side_effect

            with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                mock_tmpdir.return_value.__enter__ = MagicMock(
                    return_value="/tmp/test"
                )
                mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
                await process_batch(
                    "batch-123",
                    "user-1",
                    mock_r2_client,
                    mock_d1_client,
                    queue_wait_time_seconds=2.5,
                )

        mock_log_metrics.assert_called_once()
        bm = mock_log_metrics.call_args[0][0]
        assert bm.batch_id == "batch-123"
        assert bm.user_id == "user-1"
        assert bm.status == "completed"
        assert bm.raw_audio_duration_seconds == 10.0
        assert bm.speech_duration_seconds == 1.0
        assert bm.speech_ratio == 0.5
        assert bm.processing_wall_time_seconds > 0.0
        assert bm.queue_wait_time_seconds == 2.5
        assert bm.raw_audio_size_bytes == len(b"fake-audio-bytes")
        assert bm.cleaned_audio_size_bytes == 320000
        assert bm.transcode_duration_seconds > 0.0
        assert bm.vad_duration_seconds > 0.0
        assert bm.denoise_duration_seconds > 0.0
        assert bm.asr_submit_duration_seconds > 0.0
        assert bm.asr_wait_duration_seconds == 0.0
        assert bm.post_process_duration_seconds > 0.0
        assert bm.error_stage is None
        assert bm.error_message is None

    @patch("audio_processor.pipeline.log_batch_metrics")
    async def test_failure_emits_metrics_with_error_fields(
        self,
        mock_log_metrics,
        mock_r2_client,
        mock_d1_client,
    ):
        """Pipeline failure emits log_batch_metrics with error_stage and error_message."""
        mock_r2_client.fetch_object.side_effect = AudioFetchError(
            "Not found", key="key"
        )

        with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
            mock_tmpdir.return_value.__enter__ = MagicMock(
                return_value="/tmp/test"
            )
            mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
            await process_batch(
                "batch-123", "user-1", mock_r2_client, mock_d1_client
            )

        mock_log_metrics.assert_called_once()
        bm = mock_log_metrics.call_args[0][0]
        assert bm.status == "failed"
        assert bm.error_stage == "fetch"
        assert "Not found" in bm.error_message
        # Partial metrics: timings for stages that ran
        assert bm.transcode_duration_seconds == 0.0

    def test_cost_estimate_calculation(self):
        """Speechmatics cost estimate uses correct rate."""
        duration_seconds = 3600.0  # 1 hour
        expected_cost = duration_seconds * SPEECHMATICS_COST_PER_SECOND
        assert abs(expected_cost - 0.24) < 0.001

    @patch("audio_processor.pipeline.log_batch_metrics")
    @patch("audio_processor.pipeline.get_vad_engine")
    @patch("audio_processor.pipeline.transcode_to_wav")
    async def test_zero_speech_produces_zero_speech_ratio(
        self,
        mock_transcode,
        mock_get_vad,
        mock_log_metrics,
        mock_r2_client,
        mock_d1_client,
    ):
        """Zero-speech batch emits metrics with speech_ratio 0.0."""
        mock_transcode.return_value = _make_transcode_result()
        mock_vad_engine = MagicMock()
        mock_vad_engine.process.return_value = _make_vad_result(has_speech=False)
        mock_get_vad.return_value = mock_vad_engine

        with patch("builtins.open", create=True) as mock_open:
            file_mock = MagicMock()

            def side_effect(path, mode="r"):
                ctx = MagicMock()
                ctx.__enter__ = MagicMock(return_value=file_mock)
                ctx.__exit__ = MagicMock(return_value=False)
                return ctx

            mock_open.side_effect = side_effect

            with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                mock_tmpdir.return_value.__enter__ = MagicMock(
                    return_value="/tmp/test"
                )
                mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
                await process_batch(
                    "batch-123", "user-1", mock_r2_client, mock_d1_client
                )

        mock_log_metrics.assert_called_once()
        bm = mock_log_metrics.call_args[0][0]
        assert bm.speech_ratio == 0.0
        assert bm.speech_duration_seconds == 0.0

    @patch("audio_processor.pipeline.log_batch_metrics")
    @patch("audio_processor.pipeline.run_emotion_analysis")
    @patch("audio_processor.pipeline.insert_timestamp_markers")
    @patch("audio_processor.pipeline.get_asr_engine")
    @patch("audio_processor.pipeline.get_denoise_engine")
    @patch("audio_processor.pipeline.get_vad_engine")
    @patch("audio_processor.pipeline.transcode_to_wav")
    async def test_each_stage_timing_is_positive(
        self,
        mock_transcode,
        mock_get_vad,
        mock_get_denoise,
        mock_get_asr,
        mock_insert_markers,
        mock_run_emotion,
        mock_log_metrics,
        mock_r2_client,
        mock_d1_client,
    ):
        """Each stage timing in BatchMetrics is a positive float."""
        mock_transcode.return_value = _make_transcode_result()
        mock_vad_engine = MagicMock()
        mock_vad_engine.process.return_value = _make_vad_result(has_speech=True)
        mock_get_vad.return_value = mock_vad_engine
        mock_denoise_engine = MagicMock()
        mock_denoise_engine.process.return_value = _make_denoise_result()
        mock_get_denoise.return_value = mock_denoise_engine
        mock_asr_engine = AsyncMock()
        mock_asr_engine.transcribe.return_value = _make_transcript()
        mock_get_asr.return_value = mock_asr_engine
        mock_insert_markers.return_value = "text"
        mock_run_emotion.return_value = None

        with patch("builtins.open", create=True) as mock_open:
            file_mock = MagicMock()
            file_mock.read.return_value = b"data"

            def side_effect(path, mode="r"):
                ctx = MagicMock()
                ctx.__enter__ = MagicMock(return_value=file_mock)
                ctx.__exit__ = MagicMock(return_value=False)
                return ctx

            mock_open.side_effect = side_effect

            with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                mock_tmpdir.return_value.__enter__ = MagicMock(
                    return_value="/tmp/test"
                )
                mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
                await process_batch(
                    "batch-123", "user-1", mock_r2_client, mock_d1_client
                )

        bm = mock_log_metrics.call_args[0][0]
        assert bm.transcode_duration_seconds > 0.0
        assert bm.vad_duration_seconds > 0.0
        assert bm.denoise_duration_seconds > 0.0
        assert bm.asr_submit_duration_seconds > 0.0
        assert bm.post_process_duration_seconds > 0.0

    @patch("audio_processor.pipeline.log_batch_metrics")
    async def test_queue_wait_time_is_non_negative(
        self,
        mock_log_metrics,
        mock_r2_client,
        mock_d1_client,
    ):
        """queue_wait_time_seconds defaults to non-negative."""
        mock_r2_client.fetch_object.side_effect = AudioFetchError("fail", key="k")

        with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
            mock_tmpdir.return_value.__enter__ = MagicMock(
                return_value="/tmp/test"
            )
            mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
            await process_batch(
                "batch-123", "user-1", mock_r2_client, mock_d1_client
            )

        bm = mock_log_metrics.call_args[0][0]
        assert bm.queue_wait_time_seconds >= 0.0


class TestBuildStageRows:
    """Tests for _build_stage_rows helper (#37)."""

    def test_maps_successful_stages_to_canonical_names(self):
        """Stage rows use canonical names: transcode, vad, denoise, asr_submit, post_process."""
        timings = {
            "transcode": 2.1,
            "vad": 0.8,
            "denoise": 0.1,
            "asr": 25.0,
            "postprocess": 0.3,
        }
        rows = _build_stage_rows(timings)
        names = [r["stage"] for r in rows]
        assert "transcode" in names
        assert "vad" in names
        assert "denoise" in names
        assert "asr_submit" in names
        assert "post_process" in names

    def test_stage_count_matches_executed_stages(self):
        """Row count matches the number of stages in timings."""
        timings = {"fetch": 0.5, "transcode": 2.0, "vad": 0.8}
        rows = _build_stage_rows(timings)
        assert len(rows) == 3

    def test_failed_stage_has_success_false(self):
        """Failed stages (sentinel keys) produce rows with success=False."""
        timings = {"fetch": 0.5, "_transcode_failed": 1.2}
        rows = _build_stage_rows(timings)
        failed = [r for r in rows if r["stage"] == "transcode"]
        assert len(failed) == 1
        assert failed[0]["success"] is False
        assert failed[0]["duration_seconds"] == 1.2

    def test_all_durations_are_positive(self):
        """All stage durations are positive floats."""
        timings = {"fetch": 0.1, "transcode": 0.2, "asr": 5.0}
        rows = _build_stage_rows(timings)
        for row in rows:
            assert row["duration_seconds"] > 0.0


class TestD1MetricsFromPipeline:
    """Tests for D1 metrics calls from pipeline completion path (#37)."""

    @patch("audio_processor.pipeline.log_batch_metrics")
    @patch("audio_processor.pipeline.run_emotion_analysis")
    @patch("audio_processor.pipeline.insert_timestamp_markers")
    @patch("audio_processor.pipeline.get_asr_engine")
    @patch("audio_processor.pipeline.get_denoise_engine")
    @patch("audio_processor.pipeline.get_vad_engine")
    @patch("audio_processor.pipeline.transcode_to_wav")
    async def test_success_calls_update_batch_metrics(
        self,
        mock_transcode,
        mock_get_vad,
        mock_get_denoise,
        mock_get_asr,
        mock_insert_markers,
        mock_run_emotion,
        mock_log_metrics,
        mock_r2_client,
        mock_d1_client,
    ):
        """Successful pipeline calls d1_client.update_batch_metrics."""
        mock_transcode.return_value = _make_transcode_result()
        mock_vad_engine = MagicMock()
        mock_vad_engine.process.return_value = _make_vad_result(has_speech=True)
        mock_get_vad.return_value = mock_vad_engine
        mock_denoise_engine = MagicMock()
        mock_denoise_engine.process.return_value = _make_denoise_result()
        mock_get_denoise.return_value = mock_denoise_engine
        mock_asr_engine = AsyncMock()
        mock_asr_engine.transcribe.return_value = _make_transcript()
        mock_get_asr.return_value = mock_asr_engine
        mock_insert_markers.return_value = "text"
        mock_run_emotion.return_value = None

        with patch("builtins.open", create=True) as mock_open:
            file_mock = MagicMock()
            file_mock.read.return_value = b"data"

            def side_effect(path, mode="r"):
                ctx = MagicMock()
                ctx.__enter__ = MagicMock(return_value=file_mock)
                ctx.__exit__ = MagicMock(return_value=False)
                return ctx

            mock_open.side_effect = side_effect

            with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                mock_tmpdir.return_value.__enter__ = MagicMock(
                    return_value="/tmp/test"
                )
                mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
                await process_batch(
                    "batch-123", "user-1", mock_r2_client, mock_d1_client
                )

        mock_d1_client.update_batch_metrics.assert_called_once()
        call_kwargs = mock_d1_client.update_batch_metrics.call_args[1]
        assert call_kwargs["batch_id"] == "batch-123"
        assert call_kwargs["status"] == "completed"
        assert call_kwargs["processing_wall_time_seconds"] > 0.0

    @patch("audio_processor.pipeline.log_batch_metrics")
    @patch("audio_processor.pipeline.run_emotion_analysis")
    @patch("audio_processor.pipeline.insert_timestamp_markers")
    @patch("audio_processor.pipeline.get_asr_engine")
    @patch("audio_processor.pipeline.get_denoise_engine")
    @patch("audio_processor.pipeline.get_vad_engine")
    @patch("audio_processor.pipeline.transcode_to_wav")
    async def test_success_calls_insert_processing_stages(
        self,
        mock_transcode,
        mock_get_vad,
        mock_get_denoise,
        mock_get_asr,
        mock_insert_markers,
        mock_run_emotion,
        mock_log_metrics,
        mock_r2_client,
        mock_d1_client,
    ):
        """Successful pipeline calls d1_client.insert_processing_stages."""
        mock_transcode.return_value = _make_transcode_result()
        mock_vad_engine = MagicMock()
        mock_vad_engine.process.return_value = _make_vad_result(has_speech=True)
        mock_get_vad.return_value = mock_vad_engine
        mock_denoise_engine = MagicMock()
        mock_denoise_engine.process.return_value = _make_denoise_result()
        mock_get_denoise.return_value = mock_denoise_engine
        mock_asr_engine = AsyncMock()
        mock_asr_engine.transcribe.return_value = _make_transcript()
        mock_get_asr.return_value = mock_asr_engine
        mock_insert_markers.return_value = "text"
        mock_run_emotion.return_value = None

        with patch("builtins.open", create=True) as mock_open:
            file_mock = MagicMock()
            file_mock.read.return_value = b"data"

            def side_effect(path, mode="r"):
                ctx = MagicMock()
                ctx.__enter__ = MagicMock(return_value=file_mock)
                ctx.__exit__ = MagicMock(return_value=False)
                return ctx

            mock_open.side_effect = side_effect

            with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                mock_tmpdir.return_value.__enter__ = MagicMock(
                    return_value="/tmp/test"
                )
                mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
                await process_batch(
                    "batch-123", "user-1", mock_r2_client, mock_d1_client
                )

        mock_d1_client.insert_processing_stages.assert_called_once()
        call_kwargs = mock_d1_client.insert_processing_stages.call_args[1]
        assert call_kwargs["batch_id"] == "batch-123"
        stages = call_kwargs["stages"]
        # At least fetch, transcode, vad, denoise, asr, postprocess, emotion, store
        assert len(stages) >= 8
