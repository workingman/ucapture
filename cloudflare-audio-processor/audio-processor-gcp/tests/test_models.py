"""Tests for processing data models."""

from audio_processor.pipeline import (
    ProcessingError,
    ProcessingMetrics,
    ProcessingResult,
)


class TestProcessingMetrics:
    """Tests for ProcessingMetrics dataclass."""

    def test_instantiate_with_required_fields(self) -> None:
        metrics = ProcessingMetrics(
            raw_audio_duration_seconds=120.0,
            speech_duration_seconds=90.0,
            speech_ratio=0.75,
            cleaned_audio_size_bytes=2_880_000,
            speechmatics_job_id="job-abc-123",
            speechmatics_cost_estimate=0.50,
            processing_wall_time_seconds=45.0,
        )

        assert metrics.raw_audio_duration_seconds == 120.0
        assert metrics.speech_duration_seconds == 90.0
        assert metrics.speech_ratio == 0.75
        assert metrics.cleaned_audio_size_bytes == 2_880_000
        assert metrics.speechmatics_job_id == "job-abc-123"
        assert metrics.speechmatics_cost_estimate == 0.50
        assert metrics.processing_wall_time_seconds == 45.0

    def test_stage_timings_defaults_to_empty_dict(self) -> None:
        metrics = ProcessingMetrics(
            raw_audio_duration_seconds=10.0,
            speech_duration_seconds=8.0,
            speech_ratio=0.8,
            cleaned_audio_size_bytes=320_000,
            speechmatics_job_id="job-1",
            speechmatics_cost_estimate=0.10,
            processing_wall_time_seconds=5.0,
        )
        assert metrics.stage_timings == {}

    def test_stage_timings_populated(self) -> None:
        timings = {"transcode": 1.2, "vad": 3.4, "denoise": 2.1}
        metrics = ProcessingMetrics(
            raw_audio_duration_seconds=60.0,
            speech_duration_seconds=45.0,
            speech_ratio=0.75,
            cleaned_audio_size_bytes=1_440_000,
            speechmatics_job_id="job-2",
            speechmatics_cost_estimate=0.25,
            processing_wall_time_seconds=15.0,
            stage_timings=timings,
        )
        assert metrics.stage_timings == timings


class TestProcessingResult:
    """Tests for ProcessingResult dataclass."""

    def test_completed_result(self) -> None:
        metrics = ProcessingMetrics(
            raw_audio_duration_seconds=60.0,
            speech_duration_seconds=50.0,
            speech_ratio=0.83,
            cleaned_audio_size_bytes=1_600_000,
            speechmatics_job_id="job-3",
            speechmatics_cost_estimate=0.25,
            processing_wall_time_seconds=20.0,
        )
        result = ProcessingResult(
            status="completed",
            batch_id="batch-abc",
            artifact_paths={"transcript": "/out/transcript.json"},
            metrics=metrics,
        )

        assert result.status == "completed"
        assert result.batch_id == "batch-abc"
        assert result.error is None

    def test_failed_result_with_error(self) -> None:
        metrics = ProcessingMetrics(
            raw_audio_duration_seconds=60.0,
            speech_duration_seconds=0.0,
            speech_ratio=0.0,
            cleaned_audio_size_bytes=0,
            speechmatics_job_id="",
            speechmatics_cost_estimate=0.0,
            processing_wall_time_seconds=5.0,
        )
        error = ProcessingError(
            stage="transcode",
            message="ffmpeg failed",
            exception_type="TranscodeError",
        )
        result = ProcessingResult(
            status="failed",
            batch_id="batch-xyz",
            artifact_paths={},
            metrics=metrics,
            error=error,
        )

        assert result.status == "failed"
        assert result.error is not None
        assert result.error.stage == "transcode"
