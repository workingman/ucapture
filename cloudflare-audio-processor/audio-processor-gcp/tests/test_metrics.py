"""Tests for audio_processor.observability.metrics module."""

from __future__ import annotations

import json
import time
from dataclasses import asdict

import pytest

from audio_processor.observability.metrics import (
    BatchMetrics,
    StageTimer,
    log_batch_metrics,
)


def _make_batch_metrics(**overrides) -> BatchMetrics:
    """Create a BatchMetrics with sensible defaults, applying any overrides."""
    defaults = {
        "batch_id": "batch-001",
        "user_id": "user-1",
        "status": "completed",
        "raw_audio_duration_seconds": 600.0,
        "speech_duration_seconds": 450.0,
        "speech_ratio": 0.75,
        "processing_wall_time_seconds": 32.5,
        "queue_wait_time_seconds": 1.2,
        "raw_audio_size_bytes": 5_000_000,
        "cleaned_audio_size_bytes": 14_400_000,
        "speechmatics_job_id": "sm-job-abc",
        "speechmatics_cost_estimate": 0.04,
        "transcode_duration_seconds": 2.1,
        "vad_duration_seconds": 0.8,
        "denoise_duration_seconds": 0.0,
        "asr_submit_duration_seconds": 25.0,
        "asr_wait_duration_seconds": 0.0,
        "post_process_duration_seconds": 0.3,
        "retry_count": 0,
        "error_stage": None,
        "error_message": None,
    }
    defaults.update(overrides)
    return BatchMetrics(**defaults)


class TestBatchMetrics:
    """Tests for BatchMetrics dataclass."""

    def test_serializes_all_fields_to_dict(self):
        """BatchMetrics serializes all fields via dataclasses.asdict()."""
        metrics = _make_batch_metrics()
        d = asdict(metrics)

        assert d["batch_id"] == "batch-001"
        assert d["user_id"] == "user-1"
        assert d["status"] == "completed"
        assert d["raw_audio_duration_seconds"] == 600.0
        assert d["speech_duration_seconds"] == 450.0
        assert d["speech_ratio"] == 0.75
        assert d["processing_wall_time_seconds"] == 32.5
        assert d["queue_wait_time_seconds"] == 1.2
        assert d["raw_audio_size_bytes"] == 5_000_000
        assert d["cleaned_audio_size_bytes"] == 14_400_000
        assert d["speechmatics_job_id"] == "sm-job-abc"
        assert d["speechmatics_cost_estimate"] == 0.04
        assert d["transcode_duration_seconds"] == 2.1
        assert d["vad_duration_seconds"] == 0.8
        assert d["denoise_duration_seconds"] == 0.0
        assert d["asr_submit_duration_seconds"] == 25.0
        assert d["asr_wait_duration_seconds"] == 0.0
        assert d["post_process_duration_seconds"] == 0.3
        assert d["retry_count"] == 0
        assert d["error_stage"] is None
        assert d["error_message"] is None

    def test_error_case_serializes_with_error_fields(self):
        """Error-case metrics serialize correctly with error_stage and error_message."""
        metrics = _make_batch_metrics(
            status="failed",
            error_stage="asr",
            error_message="Speechmatics timeout",
            speechmatics_job_id="",
            speechmatics_cost_estimate=0.0,
            cleaned_audio_size_bytes=0,
            asr_submit_duration_seconds=0.0,
            post_process_duration_seconds=0.0,
        )
        d = asdict(metrics)

        assert d["status"] == "failed"
        assert d["error_stage"] == "asr"
        assert d["error_message"] == "Speechmatics timeout"
        # Partial metrics: some fields have data, others are zero/empty
        assert d["raw_audio_duration_seconds"] == 600.0
        assert d["speechmatics_job_id"] == ""


class TestLogBatchMetrics:
    """Tests for log_batch_metrics() function."""

    def test_output_is_valid_json_with_envelope_fields(self, capsys):
        """log_batch_metrics() output is valid JSON with expected envelope fields."""
        metrics = _make_batch_metrics()
        log_batch_metrics(metrics)

        output = capsys.readouterr().out.strip()
        parsed = json.loads(output)

        assert "timestamp" in parsed
        assert parsed["severity"] == "INFO"
        assert parsed["metric_type"] == "batch_completion"

    def test_output_contains_all_batch_metrics_fields(self, capsys):
        """log_batch_metrics() output contains every BatchMetrics field."""
        metrics = _make_batch_metrics()
        log_batch_metrics(metrics)

        output = capsys.readouterr().out.strip()
        parsed = json.loads(output)

        # Every field from asdict should be in the output
        for key in asdict(metrics):
            assert key in parsed, f"Missing key: {key}"


class TestStageTimer:
    """Tests for StageTimer context manager."""

    def test_captures_positive_duration(self):
        """StageTimer captures a positive duration when wrapping a timed block."""
        timer = StageTimer("transcode")
        with timer:
            time.sleep(0.01)

        assert timer.duration_seconds > 0.0

    def test_records_correct_stage_name(self):
        """StageTimer records the correct stage name."""
        timer = StageTimer("vad")
        with timer:
            pass

        assert timer.stage_name == "vad"

    def test_captures_start_and_end_times(self):
        """StageTimer captures start_time and end_time as UTC datetimes."""
        timer = StageTimer("asr")
        with timer:
            time.sleep(0.01)

        assert timer.start_time is not None
        assert timer.end_time is not None
        assert timer.end_time >= timer.start_time

    def test_duration_on_exception(self):
        """StageTimer still records duration even if the block raises."""
        timer = StageTimer("fetch")
        with pytest.raises(ValueError, match="boom"):
            with timer:
                time.sleep(0.01)
                raise ValueError("boom")

        assert timer.duration_seconds > 0.0
        assert timer.end_time is not None
