"""Main process_batch() orchestrator for the audio processing pipeline.

Contains data models for processing results and metrics as defined in TDD Section 4.4.
Orchestrates: fetch -> transcode -> VAD -> denoise -> ASR -> post-process -> emotion
-> store -> update D1 -> publish completion event.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from audio_processor.asr.interface import Transcript
from audio_processor.asr.postprocess import insert_timestamp_markers
from audio_processor.asr.registry import get_asr_engine
from audio_processor.audio.denoise import get_denoise_engine
from audio_processor.audio.transcode import transcode_to_wav
from audio_processor.audio.vad import get_vad_engine
from audio_processor.emotion.runner import run_emotion_analysis
from audio_processor.observability.metrics import BatchMetrics, log_batch_metrics
from audio_processor.storage.d1_client import D1Client
from audio_processor.storage.r2_client import R2Client
from audio_processor.utils.errors import ASRError, PipelineError
from audio_processor.utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)

# Speechmatics cost estimate: $0.24/hr = $0.004/min = ~$0.0000667/sec
SPEECHMATICS_COST_PER_SECOND = 0.24 / 3600

# Batch ID format: YYYYMMDD-HHMMSS-GMT-{uuid4}
_BATCH_ID_PATTERN = re.compile(
    r"^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})-GMT-"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _parse_recording_started_at(batch_id: str) -> str:
    """Extract recording_started_at ISO 8601 timestamp from a batch ID.

    Batch ID format: YYYYMMDD-HHMMSS-GMT-{uuid4}. The timestamp portion
    encodes the recording start time in UTC.

    Args:
        batch_id: Batch identifier in standard format.

    Returns:
        ISO 8601 UTC string (e.g., "2026-02-22T14:30:27Z").
        Empty string if batch_id does not match expected format.
    """
    match = _BATCH_ID_PATTERN.match(batch_id)
    if not match:
        logger.warning(
            "Cannot parse recording_started_at from batch_id: %s", batch_id
        )
        return ""
    year, month, day, hours, minutes, seconds = match.groups()[:6]
    return f"{year}-{month}-{day}T{hours}:{minutes}:{seconds}Z"


@dataclass
class ProcessingError:
    """Details about a processing failure."""

    stage: str
    message: str
    exception_type: str


@dataclass
class ProcessingMetrics:
    """Metrics collected during batch processing."""

    raw_audio_duration_seconds: float
    speech_duration_seconds: float
    speech_ratio: float
    cleaned_audio_size_bytes: int
    speechmatics_job_id: str
    speechmatics_cost_estimate: float
    processing_wall_time_seconds: float
    stage_timings: dict[str, float] = field(default_factory=dict)


@dataclass
class ProcessingResult:
    """Result of processing a single audio batch."""

    status: Literal["completed", "failed"]
    batch_id: str
    artifact_paths: dict[str, str]
    metrics: ProcessingMetrics
    error: ProcessingError | None = None


class _StageTimer:
    """Context manager for recording stage timings."""

    def __init__(self, stage_name: str, timings: dict[str, float]) -> None:
        self._stage_name = stage_name
        self._timings = timings
        self._start: float = 0.0

    def __enter__(self) -> _StageTimer:
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        elapsed = time.monotonic() - self._start
        # Always record timing; mark failed stages with negative sentinel
        if exc_type is not None:
            self._timings[f"_{self._stage_name}_failed"] = elapsed
        else:
            self._timings[self._stage_name] = elapsed


class _EmotionConfig:
    """Simple config object for emotion runner."""

    def __init__(self, emotion_provider: str | None) -> None:
        self.emotion_provider = emotion_provider


async def process_batch(
    batch_id: str,
    user_id: str,
    r2_client: R2Client | None = None,
    d1_client: D1Client | None = None,
    queue_wait_time_seconds: float = 0.0,
) -> ProcessingResult:
    """Orchestrate processing of a single audio batch.

    Pipeline stages: fetch -> transcode -> VAD -> denoise -> ASR ->
    post-process -> emotion -> store -> update D1 -> publish event.

    Args:
        batch_id: Unique identifier for the batch to process.
        user_id: User identifier for R2 path construction.
        r2_client: Optional R2Client (creates default if not provided).
        d1_client: Optional D1Client (creates default if not provided).
        queue_wait_time_seconds: Time spent waiting in queue before
            processing started (passed by the consumer).

    Returns:
        ProcessingResult with status, artifacts, and metrics.
    """
    wall_start = time.monotonic()
    stage_timings: dict[str, float] = {}
    artifact_paths: dict[str, str] = {}
    retry_count = 0
    current_stage = "init"

    if r2_client is None:
        r2_client = R2Client()
    if d1_client is None:
        d1_client = D1Client()

    # R2 path prefix for this batch
    path_prefix = f"{user_id}/{batch_id}"

    # Extract recording_started_at from batch_id timestamp
    recording_started_at = _parse_recording_started_at(batch_id)

    try:
        result = await _run_pipeline(
            batch_id=batch_id,
            user_id=user_id,
            path_prefix=path_prefix,
            r2_client=r2_client,
            d1_client=d1_client,
            stage_timings=stage_timings,
            artifact_paths=artifact_paths,
            queue_wait_time_seconds=queue_wait_time_seconds,
            recording_started_at=recording_started_at,
        )
        return result

    except Exception as exc:
        wall_time = time.monotonic() - wall_start
        current_stage = _determine_error_stage(exc, stage_timings)
        error_message = str(exc)

        logger.error(
            "Pipeline failed at stage '%s' for batch %s: %s",
            current_stage,
            batch_id,
            error_message,
            exc_info=True,
        )

        # Determine retry count from the exception if available
        retry_count = getattr(exc, "_retry_count", 0)

        # Update D1 with failure status and partial metrics
        try:
            await d1_client.update_batch_status(
                batch_id=batch_id,
                status="failed",
                error_stage=current_stage,
                error_message=error_message,
                retry_count=retry_count,
            )
            await d1_client.update_batch_metrics(
                batch_id=batch_id,
                status="failed",
                processing_wall_time_seconds=wall_time,
                error_stage=current_stage,
                error_message=error_message,
                retry_count=retry_count,
            )
            stage_rows = _build_stage_rows(stage_timings)
            await d1_client.insert_processing_stages(
                batch_id=batch_id,
                stages=stage_rows,
            )
        except Exception:
            logger.error(
                "Failed to update D1 failure status for batch %s",
                batch_id,
                exc_info=True,
            )

        # Publish failure completion event
        failure_event = _build_completion_event(
            batch_id=batch_id,
            user_id=user_id,
            status="failed",
            artifact_paths=artifact_paths,
            recording_started_at=recording_started_at,
            error_message=error_message,
        )
        try:
            await d1_client.publish_completion_event(failure_event)
        except Exception:
            logger.error(
                "Failed to publish failure event for batch %s",
                batch_id,
                exc_info=True,
            )

        error = ProcessingError(
            stage=current_stage,
            message=error_message,
            exception_type=type(exc).__name__,
        )

        metrics = ProcessingMetrics(
            raw_audio_duration_seconds=0.0,
            speech_duration_seconds=0.0,
            speech_ratio=0.0,
            cleaned_audio_size_bytes=0,
            speechmatics_job_id="",
            speechmatics_cost_estimate=0.0,
            processing_wall_time_seconds=wall_time,
            stage_timings=stage_timings,
        )

        # Emit observability metrics for the failed batch
        batch_metrics = _build_batch_metrics(
            batch_id=batch_id,
            user_id=user_id,
            status="failed",
            stage_timings=stage_timings,
            wall_time=wall_time,
            queue_wait_time_seconds=queue_wait_time_seconds,
            raw_audio_size_bytes=0,
            retry_count=retry_count,
            error_stage=current_stage,
            error_message=error_message,
        )
        log_batch_metrics(batch_metrics)

        return ProcessingResult(
            status="failed",
            batch_id=batch_id,
            artifact_paths=artifact_paths,
            metrics=metrics,
            error=error,
        )


async def _run_pipeline(
    batch_id: str,
    user_id: str,
    path_prefix: str,
    r2_client: R2Client,
    d1_client: D1Client,
    stage_timings: dict[str, float],
    artifact_paths: dict[str, str],
    queue_wait_time_seconds: float = 0.0,
    recording_started_at: str = "",
) -> ProcessingResult:
    """Execute the full pipeline stages. Raises on failure."""
    wall_start = time.monotonic()

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Stage 1: Fetch raw audio from R2
        raw_audio_key = f"{path_prefix}/raw-audio/recording.m4a"
        with _StageTimer("fetch", stage_timings):
            audio_data = await _fetch_with_retry(r2_client, raw_audio_key)

        raw_audio_size_bytes = len(audio_data)

        # Write raw audio to temp file for processing
        raw_audio_path = os.path.join(tmp_dir, "recording.m4a")
        with open(raw_audio_path, "wb") as f:
            f.write(audio_data)

        # Stage 2: Transcode M4A -> WAV 16kHz mono PCM
        with _StageTimer("transcode", stage_timings):
            transcode_result = transcode_to_wav(raw_audio_path, tmp_dir)

        raw_duration = transcode_result.duration_seconds

        # Stage 3: VAD (voice activity detection)
        with _StageTimer("vad", stage_timings):
            vad_provider = os.environ.get("VAD_PROVIDER", "silero")
            vad_kwargs: dict[str, object] = {}
            vad_threshold_str = os.environ.get("VAD_THRESHOLD")
            if vad_threshold_str is not None:
                vad_kwargs["threshold"] = float(vad_threshold_str)
            vad_engine = get_vad_engine(vad_provider, **vad_kwargs)
            vad_result = vad_engine.process(
                transcode_result.output_path, tmp_dir
            )

        speech_duration = vad_result.speech_duration_seconds
        speech_ratio = vad_result.speech_ratio
        has_speech = len(vad_result.segments) > 0 and speech_duration > 0

        # Zero-speech handling: skip denoise/ASR/emotion
        if not has_speech:
            return await _handle_zero_speech(
                batch_id=batch_id,
                user_id=user_id,
                path_prefix=path_prefix,
                r2_client=r2_client,
                d1_client=d1_client,
                raw_duration=raw_duration,
                stage_timings=stage_timings,
                artifact_paths=artifact_paths,
                wall_start=wall_start,
                queue_wait_time_seconds=queue_wait_time_seconds,
                raw_audio_size_bytes=raw_audio_size_bytes,
                recording_started_at=recording_started_at,
            )

        # Stage 4: Denoise (passthrough with null provider)
        with _StageTimer("denoise", stage_timings):
            denoise_provider = os.environ.get("DENOISE_PROVIDER", "null")
            denoise_engine = get_denoise_engine(denoise_provider)
            denoise_result = denoise_engine.process(
                vad_result.output_path, tmp_dir
            )

        cleaned_audio_size = denoise_result.output_size_bytes

        # Stage 5: ASR (speech recognition)
        with _StageTimer("asr", stage_timings):
            asr_api_key = os.environ.get("SPEECHMATICS_API_KEY", "")
            asr_engine = get_asr_engine("speechmatics", api_key=asr_api_key)
            transcript = await _transcribe_with_retry(
                asr_engine, denoise_result.output_path, {}
            )

        # Stage 6: Post-process transcript
        with _StageTimer("postprocess", stage_timings):
            formatted_text = insert_timestamp_markers(transcript)

        # Stage 7: Emotion analysis (best-effort)
        emotion_result = None
        with _StageTimer("emotion", stage_timings):
            emotion_provider = os.environ.get("EMOTION_PROVIDER", None)
            emotion_config = _EmotionConfig(emotion_provider=emotion_provider)
            try:
                emotion_result = await run_emotion_analysis(
                    transcript, denoise_result.output_path, emotion_config
                )
            except Exception:
                logger.warning(
                    "Emotion analysis failed for batch %s, continuing",
                    batch_id,
                    exc_info=True,
                )

        # Stage 8: Store results to R2
        with _StageTimer("store", stage_timings):
            # Store cleaned audio
            cleaned_key = f"{path_prefix}/cleaned-audio/cleaned.wav"
            with open(denoise_result.output_path, "rb") as f:
                cleaned_data = f.read()
            await _put_with_retry(
                r2_client, cleaned_key, cleaned_data, "audio/wav"
            )
            artifact_paths["cleaned_audio"] = cleaned_key

            # Store formatted transcript
            formatted_key = f"{path_prefix}/transcript/formatted.txt"
            await _put_with_retry(
                r2_client,
                formatted_key,
                formatted_text.encode("utf-8"),
                "text/plain",
            )
            artifact_paths["transcript_formatted"] = formatted_key

            # Store raw ASR response
            raw_transcript_key = (
                f"{path_prefix}/transcript/raw-speechmatics.json"
            )
            raw_json = json.dumps(
                transcript.raw_response, ensure_ascii=False
            ).encode("utf-8")
            await _put_with_retry(
                r2_client, raw_transcript_key, raw_json, "application/json"
            )
            artifact_paths["transcript_raw"] = raw_transcript_key

            # Store emotion result if available
            if emotion_result is not None:
                emotion_key = f"{path_prefix}/transcript/emotion.json"
                import dataclasses

                emotion_json = json.dumps(
                    dataclasses.asdict(emotion_result), ensure_ascii=False
                ).encode("utf-8")
                await _put_with_retry(
                    r2_client, emotion_key, emotion_json, "application/json"
                )
                artifact_paths["transcript_emotion"] = emotion_key

        # Raw audio path (never deleted)
        artifact_paths["raw_audio"] = raw_audio_key

        # Compute metrics
        speechmatics_job_id = ""
        speechmatics_cost = raw_duration * SPEECHMATICS_COST_PER_SECOND
        wall_time = time.monotonic() - wall_start

        metrics = ProcessingMetrics(
            raw_audio_duration_seconds=raw_duration,
            speech_duration_seconds=speech_duration,
            speech_ratio=speech_ratio,
            cleaned_audio_size_bytes=cleaned_audio_size,
            speechmatics_job_id=speechmatics_job_id,
            speechmatics_cost_estimate=speechmatics_cost,
            processing_wall_time_seconds=wall_time,
            stage_timings=stage_timings,
        )

        # Stage 9: Update D1 with completion status and metrics
        with _StageTimer("d1_update", stage_timings):
            await d1_client.update_batch_status(
                batch_id=batch_id,
                status="completed",
                artifact_paths=artifact_paths,
            )
            await d1_client.update_batch_metrics(
                batch_id=batch_id,
                status="completed",
                processing_wall_time_seconds=wall_time,
                raw_audio_duration_seconds=raw_duration,
                speech_duration_seconds=speech_duration,
                speech_ratio=speech_ratio,
                raw_audio_size_bytes=raw_audio_size_bytes,
                cleaned_audio_size_bytes=cleaned_audio_size,
                speechmatics_job_id=speechmatics_job_id,
                speechmatics_cost_estimate=speechmatics_cost,
            )
            stage_rows = _build_stage_rows(stage_timings)
            await d1_client.insert_processing_stages(
                batch_id=batch_id,
                stages=stage_rows,
            )

        # Stage 10: Publish completion event
        with _StageTimer("publish_event", stage_timings):
            event = _build_completion_event(
                batch_id=batch_id,
                user_id=user_id,
                status="completed",
                artifact_paths=artifact_paths,
                recording_started_at=recording_started_at,
            )
            await d1_client.publish_completion_event(event)

        # Emit observability metrics for the completed batch
        batch_metrics = _build_batch_metrics(
            batch_id=batch_id,
            user_id=user_id,
            status="completed",
            stage_timings=stage_timings,
            wall_time=wall_time,
            queue_wait_time_seconds=queue_wait_time_seconds,
            raw_audio_size_bytes=raw_audio_size_bytes,
            raw_audio_duration_seconds=raw_duration,
            speech_duration_seconds=speech_duration,
            speech_ratio=speech_ratio,
            cleaned_audio_size_bytes=cleaned_audio_size,
            speechmatics_job_id=speechmatics_job_id,
            speechmatics_cost_estimate=speechmatics_cost,
        )
        log_batch_metrics(batch_metrics)

        return ProcessingResult(
            status="completed",
            batch_id=batch_id,
            artifact_paths=artifact_paths,
            metrics=metrics,
        )


async def _handle_zero_speech(
    batch_id: str,
    user_id: str,
    path_prefix: str,
    r2_client: R2Client,
    d1_client: D1Client,
    raw_duration: float,
    stage_timings: dict[str, float],
    artifact_paths: dict[str, str],
    wall_start: float,
    queue_wait_time_seconds: float = 0.0,
    raw_audio_size_bytes: int = 0,
    recording_started_at: str = "",
) -> ProcessingResult:
    """Handle a batch with no detected speech.

    Writes empty formatted transcript, skips cleaned audio and emotion.
    """
    with _StageTimer("store", stage_timings):
        # Store empty formatted transcript
        formatted_key = f"{path_prefix}/transcript/formatted.txt"
        await _put_with_retry(
            r2_client, formatted_key, b"", "text/plain"
        )
        artifact_paths["transcript_formatted"] = formatted_key
        artifact_paths["raw_audio"] = f"{path_prefix}/raw-audio/recording.m4a"

    wall_time = time.monotonic() - wall_start

    metrics = ProcessingMetrics(
        raw_audio_duration_seconds=raw_duration,
        speech_duration_seconds=0.0,
        speech_ratio=0.0,
        cleaned_audio_size_bytes=0,
        speechmatics_job_id="",
        speechmatics_cost_estimate=0.0,
        processing_wall_time_seconds=wall_time,
        stage_timings=stage_timings,
    )

    # Update D1 with completion and metrics
    with _StageTimer("d1_update", stage_timings):
        await d1_client.update_batch_status(
            batch_id=batch_id,
            status="completed",
            artifact_paths=artifact_paths,
        )
        await d1_client.update_batch_metrics(
            batch_id=batch_id,
            status="completed",
            processing_wall_time_seconds=wall_time,
            raw_audio_duration_seconds=raw_duration,
            raw_audio_size_bytes=raw_audio_size_bytes,
        )
        stage_rows = _build_stage_rows(stage_timings)
        await d1_client.insert_processing_stages(
            batch_id=batch_id,
            stages=stage_rows,
        )

    # Publish completion event
    with _StageTimer("publish_event", stage_timings):
        event = _build_completion_event(
            batch_id=batch_id,
            user_id=user_id,
            status="completed",
            artifact_paths=artifact_paths,
            recording_started_at=recording_started_at,
        )
        await d1_client.publish_completion_event(event)

    # Emit observability metrics for zero-speech batch
    batch_metrics = _build_batch_metrics(
        batch_id=batch_id,
        user_id=user_id,
        status="completed",
        stage_timings=stage_timings,
        wall_time=wall_time,
        queue_wait_time_seconds=queue_wait_time_seconds,
        raw_audio_size_bytes=raw_audio_size_bytes,
        raw_audio_duration_seconds=raw_duration,
        speech_duration_seconds=0.0,
        speech_ratio=0.0,
    )
    log_batch_metrics(batch_metrics)

    return ProcessingResult(
        status="completed",
        batch_id=batch_id,
        artifact_paths=artifact_paths,
        metrics=metrics,
    )


def _determine_error_stage(
    exc: Exception, stage_timings: dict[str, float]
) -> str:
    """Determine which pipeline stage failed based on completed timings.

    The last stage that started but is NOT in stage_timings is the
    failure stage. If the exception is a PipelineError subclass, use
    its class name as a hint.
    """
    stages = [
        "fetch",
        "transcode",
        "vad",
        "denoise",
        "asr",
        "postprocess",
        "emotion",
        "store",
        "d1_update",
        "publish_event",
    ]

    # Check for a stage marked as failed (sentinel key from _StageTimer)
    for stage in stages:
        if f"_{stage}_failed" in stage_timings:
            return stage

    # Find the first stage that hasn't completed timing
    for stage in stages:
        if stage not in stage_timings:
            return stage

    # All stages completed -- error in cleanup/post
    if isinstance(exc, PipelineError):
        return type(exc).__name__.lower().replace("error", "")

    return "unknown"


def _build_stage_rows(
    stage_timings: dict[str, float],
) -> list[dict[str, Any]]:
    """Convert _StageTimer timings dict to processing_stages rows.

    Maps internal stage names to the canonical stage names used in D1:
    transcode, vad, denoise, asr_submit, asr_wait, post_process.
    Failed stages (prefixed with underscore) are included with
    success=False.

    Returns:
        List of dicts with stage, duration_seconds, success, error_message.
    """
    # Map pipeline stage keys to D1 canonical names
    stage_name_map = {
        "transcode": "transcode",
        "vad": "vad",
        "denoise": "denoise",
        "asr": "asr_submit",
        "postprocess": "post_process",
    }

    rows: list[dict[str, Any]] = []
    for key, duration in stage_timings.items():
        # Handle failed stage sentinel keys (e.g., "_fetch_failed")
        if key.startswith("_") and key.endswith("_failed"):
            raw_name = key[1:].replace("_failed", "")
            canonical = stage_name_map.get(raw_name, raw_name)
            rows.append({
                "stage": canonical,
                "duration_seconds": duration,
                "success": False,
                "error_message": None,
            })
        else:
            canonical = stage_name_map.get(key, key)
            rows.append({
                "stage": canonical,
                "duration_seconds": duration,
                "success": True,
                "error_message": None,
            })
    return rows


def _build_batch_metrics(
    batch_id: str,
    user_id: str,
    status: str,
    stage_timings: dict[str, float],
    wall_time: float,
    queue_wait_time_seconds: float = 0.0,
    raw_audio_size_bytes: int = 0,
    raw_audio_duration_seconds: float = 0.0,
    speech_duration_seconds: float = 0.0,
    speech_ratio: float = 0.0,
    cleaned_audio_size_bytes: int = 0,
    speechmatics_job_id: str = "",
    speechmatics_cost_estimate: float = 0.0,
    retry_count: int = 0,
    error_stage: str | None = None,
    error_message: str | None = None,
) -> BatchMetrics:
    """Build a BatchMetrics from pipeline data.

    Maps _StageTimer keys to individual BatchMetrics timing fields.
    Uses 0.0 for stages that did not execute.
    """
    return BatchMetrics(
        batch_id=batch_id,
        user_id=user_id,
        status=status,
        raw_audio_duration_seconds=raw_audio_duration_seconds,
        speech_duration_seconds=speech_duration_seconds,
        speech_ratio=speech_ratio,
        processing_wall_time_seconds=wall_time,
        queue_wait_time_seconds=queue_wait_time_seconds,
        raw_audio_size_bytes=raw_audio_size_bytes,
        cleaned_audio_size_bytes=cleaned_audio_size_bytes,
        speechmatics_job_id=speechmatics_job_id,
        speechmatics_cost_estimate=speechmatics_cost_estimate,
        transcode_duration_seconds=stage_timings.get("transcode", 0.0),
        vad_duration_seconds=stage_timings.get("vad", 0.0),
        denoise_duration_seconds=stage_timings.get("denoise", 0.0),
        asr_submit_duration_seconds=stage_timings.get("asr", 0.0),
        asr_wait_duration_seconds=0.0,
        post_process_duration_seconds=stage_timings.get("postprocess", 0.0),
        retry_count=retry_count,
        error_stage=error_stage,
        error_message=error_message,
    )


def _build_completion_event(
    batch_id: str,
    user_id: str,
    status: str,
    artifact_paths: dict[str, str],
    recording_started_at: str = "",
    error_message: str | None = None,
) -> dict[str, Any]:
    """Build a CompletionEvent dict per TDD Section 4.3."""
    event: dict[str, Any] = {
        "batch_id": batch_id,
        "user_id": user_id,
        "status": status,
        "recording_started_at": recording_started_at,
        "artifact_paths": artifact_paths,
        "published_at": datetime.now(UTC).isoformat(),
    }
    if error_message:
        event["error_message"] = error_message
    return event


@retry_with_backoff(
    max_retries=3,
    base_delay=1.0,
    retryable_exceptions=(httpx.RequestError, httpx.HTTPStatusError),
)
async def _fetch_with_retry(r2_client: R2Client, key: str) -> bytes:
    """Fetch an object from R2 with retry."""
    return r2_client.fetch_object(key)


@retry_with_backoff(
    max_retries=3,
    base_delay=1.0,
    retryable_exceptions=(ASRError, httpx.RequestError),
)
async def _transcribe_with_retry(
    asr_engine: Any, audio_path: str, metadata: dict
) -> Transcript:
    """Run ASR transcription with retry."""
    return await asr_engine.transcribe(audio_path, metadata)


@retry_with_backoff(
    max_retries=3,
    base_delay=1.0,
    retryable_exceptions=(httpx.RequestError, httpx.HTTPStatusError),
)
async def _put_with_retry(
    r2_client: R2Client,
    key: str,
    data: bytes,
    content_type: str = "",
) -> None:
    """Put an object to R2 with retry."""
    r2_client.put_object(key, data, content_type)
