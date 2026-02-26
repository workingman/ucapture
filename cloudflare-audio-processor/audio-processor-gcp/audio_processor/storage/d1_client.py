"""Cloudflare D1 database client.

Provides batch status updates, metrics persistence, and completion event
publishing by calling internal endpoints on the Cloudflare Worker. The
Worker owns D1 access; GCP communicates through the Worker's internal API.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

import httpx

from audio_processor.utils.errors import StorageError

logger = logging.getLogger(__name__)


class D1Client:
    """Client for D1 operations via the Cloudflare Worker internal API.

    Reads configuration from environment variables:
        CLOUDFLARE_WORKER_URL, CLOUDFLARE_INTERNAL_SECRET
    """

    def __init__(
        self,
        worker_url: str | None = None,
        internal_secret: str | None = None,
    ) -> None:
        self.worker_url = (
            worker_url or os.environ.get("CLOUDFLARE_WORKER_URL", "")
        ).rstrip("/")
        self.internal_secret = internal_secret or os.environ.get(
            "CLOUDFLARE_INTERNAL_SECRET", ""
        )

        if not self.worker_url:
            raise StorageError(
                "CLOUDFLARE_WORKER_URL is required", operation="init"
            )
        if not self.internal_secret:
            raise StorageError(
                "CLOUDFLARE_INTERNAL_SECRET is required", operation="init"
            )

        self._client = httpx.AsyncClient(timeout=30.0)

    def _headers(self) -> dict[str, str]:
        """Build authentication headers for internal Worker endpoints."""
        return {
            "X-Internal-Secret": self.internal_secret,
            "Content-Type": "application/json",
        }

    async def close(self) -> None:
        """Close the shared HTTP client and release connection pool."""
        await self._client.aclose()

    async def update_batch_status(
        self,
        batch_id: str,
        status: str,
        error_stage: str | None = None,
        error_message: str | None = None,
        retry_count: int | None = None,
        artifact_paths: dict[str, str] | None = None,
    ) -> None:
        """Update batch processing status via the Worker internal API.

        Args:
            batch_id: The batch identifier.
            status: New status (e.g., "processing", "completed", "failed").
            error_stage: Pipeline stage where failure occurred (on failure).
            error_message: Human-readable error description (on failure).
            retry_count: Number of retry attempts exhausted (on failure).
            artifact_paths: Dict of artifact type to R2 key (on completion).

        Raises:
            StorageError: If the Worker API call fails.
        """
        payload: dict[str, Any] = {
            "batch_id": batch_id,
            "status": status,
        }
        if error_stage is not None:
            payload["error_stage"] = error_stage
        if error_message is not None:
            payload["error_message"] = error_message
        if retry_count is not None:
            payload["retry_count"] = retry_count
        if artifact_paths is not None:
            payload["artifact_paths"] = artifact_paths

        url = f"{self.worker_url}/internal/batch-status"
        try:
            response = await self._client.post(
                url,
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise StorageError(
                f"D1 status update failed for batch '{batch_id}': "
                f"HTTP {exc.response.status_code}",
                batch_id=batch_id,
                operation="update_batch_status",
            ) from exc
        except httpx.RequestError as exc:
            raise StorageError(
                f"D1 status update failed for batch '{batch_id}': {exc}",
                batch_id=batch_id,
                operation="update_batch_status",
            ) from exc

    async def publish_completion_event(self, event: dict[str, Any]) -> None:
        """Publish a completion event via the Worker internal API.

        The Worker receives this event and publishes it to Pub/Sub.

        Args:
            event: CompletionEvent dict per TDD Section 4.3.

        Raises:
            StorageError: If the Worker API call fails.
        """
        url = f"{self.worker_url}/internal/publish-event"
        batch_id = event.get("batch_id", "unknown")
        try:
            response = await self._client.post(
                url,
                headers=self._headers(),
                json=event,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise StorageError(
                f"Completion event publish failed for batch '{batch_id}': "
                f"HTTP {exc.response.status_code}",
                batch_id=batch_id,
                operation="publish_completion_event",
            ) from exc
        except httpx.RequestError as exc:
            raise StorageError(
                f"Completion event publish failed for batch '{batch_id}': "
                f"{exc}",
                batch_id=batch_id,
                operation="publish_completion_event",
            ) from exc

    async def update_batch_metrics(
        self,
        batch_id: str,
        status: str,
        processing_wall_time_seconds: float,
        raw_audio_duration_seconds: float = 0.0,
        speech_duration_seconds: float = 0.0,
        speech_ratio: float = 0.0,
        raw_audio_size_bytes: int = 0,
        cleaned_audio_size_bytes: int = 0,
        speechmatics_job_id: str = "",
        speechmatics_cost_estimate: float = 0.0,
        error_stage: str | None = None,
        error_message: str | None = None,
        retry_count: int = 0,
    ) -> None:
        """Update batch record with processing metrics via the Worker.

        Sets processing_started_at, processing_completed_at, and all
        audio/ASR metrics columns on the batches row.

        Args:
            batch_id: The batch identifier.
            status: Final status ("completed" or "failed").
            processing_wall_time_seconds: Total wall-clock processing time.
            raw_audio_duration_seconds: Duration of raw audio input.
            speech_duration_seconds: Duration of detected speech.
            speech_ratio: Ratio of speech to total audio.
            raw_audio_size_bytes: Size of raw audio from R2.
            cleaned_audio_size_bytes: Size of denoised audio.
            speechmatics_job_id: Speechmatics job ID for reconciliation.
            speechmatics_cost_estimate: Estimated ASR cost.
            error_stage: Pipeline stage where failure occurred (on failure).
            error_message: Human-readable error description (on failure).
            retry_count: Number of retry attempts.

        Raises:
            StorageError: If the Worker API call fails.
        """
        now = datetime.now(UTC).isoformat()
        payload: dict[str, Any] = {
            "batch_id": batch_id,
            "status": status,
            "processing_completed_at": now,
            "processing_wall_time_seconds": processing_wall_time_seconds,
            "raw_audio_duration_seconds": raw_audio_duration_seconds,
            "speech_duration_seconds": speech_duration_seconds,
            "speech_ratio": speech_ratio,
            "raw_audio_size_bytes": raw_audio_size_bytes,
            "cleaned_audio_size_bytes": cleaned_audio_size_bytes,
            "speechmatics_job_id": speechmatics_job_id,
            "speechmatics_cost_estimate": speechmatics_cost_estimate,
            "retry_count": retry_count,
        }
        if error_stage is not None:
            payload["error_stage"] = error_stage
        if error_message is not None:
            payload["error_message"] = error_message

        url = f"{self.worker_url}/internal/batch-status"
        try:
            response = await self._client.post(
                url,
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise StorageError(
                f"D1 metrics update failed for batch '{batch_id}': "
                f"HTTP {exc.response.status_code}",
                batch_id=batch_id,
                operation="update_batch_metrics",
            ) from exc
        except httpx.RequestError as exc:
            raise StorageError(
                f"D1 metrics update failed for batch '{batch_id}': {exc}",
                batch_id=batch_id,
                operation="update_batch_metrics",
            ) from exc

    async def insert_processing_stages(
        self,
        batch_id: str,
        stages: list[dict[str, Any]],
    ) -> None:
        """Write per-stage timing rows via the Worker.

        Each stage dict should contain:
            stage: str          - stage name (e.g., "transcode", "vad")
            duration_seconds: float - wall-clock time for the stage
            success: bool       - whether the stage completed successfully
            error_message: str | None - error message on failure

        Args:
            batch_id: The batch identifier.
            stages: List of stage dicts to insert.

        Raises:
            StorageError: If the Worker API call fails.
        """
        if not stages:
            return

        payload: dict[str, Any] = {
            "batch_id": batch_id,
            "stages": stages,
        }

        url = f"{self.worker_url}/internal/processing-stages"
        try:
            response = await self._client.post(
                url,
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise StorageError(
                f"D1 stage insert failed for batch '{batch_id}': "
                f"HTTP {exc.response.status_code}",
                batch_id=batch_id,
                operation="insert_processing_stages",
            ) from exc
        except httpx.RequestError as exc:
            raise StorageError(
                f"D1 stage insert failed for batch '{batch_id}': {exc}",
                batch_id=batch_id,
                operation="insert_processing_stages",
            ) from exc
