"""Processing metrics collection and reporting.

Provides BatchMetrics dataclass for structured observability data,
StageTimer context manager for measuring pipeline stage durations,
and log_batch_metrics() for emitting metrics as structured JSON to stdout.

Metrics are ingested by GCP Cloud Logging and exported to BigQuery
per TDD Decision 7.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass
class BatchMetrics:
    """All metrics collected for a single batch processing run.

    Fields align with the BigQuery `audio_pipeline.batch_metrics` schema.
    """

    batch_id: str
    user_id: str
    status: str
    raw_audio_duration_seconds: float
    speech_duration_seconds: float
    speech_ratio: float
    processing_wall_time_seconds: float
    queue_wait_time_seconds: float
    raw_audio_size_bytes: int
    cleaned_audio_size_bytes: int
    speechmatics_job_id: str
    speechmatics_cost_estimate: float
    transcode_duration_seconds: float
    vad_duration_seconds: float
    denoise_duration_seconds: float
    asr_submit_duration_seconds: float
    asr_wait_duration_seconds: float
    post_process_duration_seconds: float
    retry_count: int = 0
    error_stage: str | None = None
    error_message: str | None = None


class StageTimer:
    """Context manager that records wall-clock duration of a pipeline stage.

    Captures stage_name, start_time, end_time (as UTC datetimes),
    and duration_seconds (as a monotonic float).

    Usage:
        timer = StageTimer("transcode")
        with timer:
            do_work()
        print(timer.duration_seconds)
    """

    def __init__(self, stage_name: str) -> None:
        self.stage_name = stage_name
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None
        self.duration_seconds: float = 0.0
        self._mono_start: float = 0.0

    def __enter__(self) -> StageTimer:
        self.start_time = datetime.now(UTC)
        self._mono_start = time.monotonic()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        elapsed = time.monotonic() - self._mono_start
        self.end_time = datetime.now(UTC)
        self.duration_seconds = elapsed


def log_batch_metrics(metrics: BatchMetrics) -> None:
    """Emit batch metrics as a single structured JSON line to stdout.

    The JSON envelope includes timestamp, severity, and metric_type
    fields for GCP Cloud Logging structured log parsing. All
    BatchMetrics fields are spread into the top level.

    Args:
        metrics: Populated BatchMetrics dataclass.
    """
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "severity": "INFO",
        "metric_type": "batch_completion",
        **asdict(metrics),
    }
    print(json.dumps(entry))
