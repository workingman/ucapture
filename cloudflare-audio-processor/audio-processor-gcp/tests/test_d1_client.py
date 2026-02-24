"""Tests for audio_processor.storage.d1_client module."""

import json

import pytest
import httpx

from audio_processor.storage.d1_client import D1Client
from audio_processor.utils.errors import StorageError


class TestD1ClientInit:
    """Tests for D1Client initialization."""

    def test_init_with_explicit_params(self):
        """D1Client initializes with explicit parameters."""
        client = D1Client(
            worker_url="https://worker.example.com",
            internal_secret="test-secret-123",
        )
        assert client.worker_url == "https://worker.example.com"
        assert client.internal_secret == "test-secret-123"

    def test_init_strips_trailing_slash(self):
        """D1Client strips trailing slash from worker_url."""
        client = D1Client(
            worker_url="https://worker.example.com/",
            internal_secret="secret",
        )
        assert client.worker_url == "https://worker.example.com"

    def test_init_missing_worker_url_raises_storage_error(self):
        """D1Client raises StorageError if worker_url is missing."""
        with pytest.raises(StorageError, match="CLOUDFLARE_WORKER_URL"):
            D1Client(worker_url="", internal_secret="secret")

    def test_init_missing_secret_raises_storage_error(self):
        """D1Client raises StorageError if internal_secret is missing."""
        with pytest.raises(StorageError, match="CLOUDFLARE_INTERNAL_SECRET"):
            D1Client(worker_url="https://worker.example.com", internal_secret="")


class TestD1ClientUpdateBatchStatus:
    """Tests for D1Client.update_batch_status()."""

    @pytest.fixture
    def client(self):
        return D1Client(
            worker_url="https://worker.example.com",
            internal_secret="test-secret",
        )

    async def test_update_status_sends_correct_request(self, client, httpx_mock):
        """update_batch_status sends POST with correct payload."""
        httpx_mock.add_response(
            url="https://worker.example.com/internal/batch-status",
            method="POST",
            status_code=200,
        )

        await client.update_batch_status(
            batch_id="batch-123", status="processing"
        )

        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["X-Internal-Secret"] == "test-secret"
        import json
        body = json.loads(request.content)
        assert body["batch_id"] == "batch-123"
        assert body["status"] == "processing"

    async def test_update_status_with_error_fields(self, client, httpx_mock):
        """update_batch_status includes error fields when provided."""
        httpx_mock.add_response(
            url="https://worker.example.com/internal/batch-status",
            method="POST",
            status_code=200,
        )

        await client.update_batch_status(
            batch_id="batch-123",
            status="failed",
            error_stage="asr",
            error_message="Speechmatics timeout",
            retry_count=3,
        )

        request = httpx_mock.get_request()
        import json
        body = json.loads(request.content)
        assert body["error_stage"] == "asr"
        assert body["error_message"] == "Speechmatics timeout"
        assert body["retry_count"] == 3

    async def test_update_status_raises_on_http_error(self, client, httpx_mock):
        """update_batch_status raises StorageError on HTTP error."""
        httpx_mock.add_response(
            url="https://worker.example.com/internal/batch-status",
            method="POST",
            status_code=500,
        )

        with pytest.raises(StorageError, match="HTTP 500"):
            await client.update_batch_status(
                batch_id="batch-123", status="processing"
            )


class TestD1ClientPublishCompletionEvent:
    """Tests for D1Client.publish_completion_event()."""

    @pytest.fixture
    def client(self):
        return D1Client(
            worker_url="https://worker.example.com",
            internal_secret="test-secret",
        )

    async def test_publish_event_sends_correct_request(self, client, httpx_mock):
        """publish_completion_event sends POST to correct endpoint."""
        httpx_mock.add_response(
            url="https://worker.example.com/internal/publish-event",
            method="POST",
            status_code=200,
        )

        event = {
            "batch_id": "batch-123",
            "user_id": "user-1",
            "status": "completed",
            "artifact_paths": {"transcript_formatted": "user-1/batch-123/transcript/formatted.txt"},
            "published_at": "2026-02-24T10:00:00Z",
        }

        await client.publish_completion_event(event)

        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["X-Internal-Secret"] == "test-secret"

    async def test_publish_event_raises_on_http_error(self, client, httpx_mock):
        """publish_completion_event raises StorageError on HTTP error."""
        httpx_mock.add_response(
            url="https://worker.example.com/internal/publish-event",
            method="POST",
            status_code=502,
        )

        with pytest.raises(StorageError, match="HTTP 502"):
            await client.publish_completion_event(
                {"batch_id": "batch-123", "status": "completed"}
            )


class TestD1ClientUpdateBatchMetrics:
    """Tests for D1Client.update_batch_metrics() (#37)."""

    @pytest.fixture
    def client(self):
        return D1Client(
            worker_url="https://worker.example.com",
            internal_secret="test-secret",
        )

    async def test_success_sends_all_metrics_columns(self, client, httpx_mock):
        """update_batch_metrics sends all metrics fields on success."""
        httpx_mock.add_response(
            url="https://worker.example.com/internal/batch-status",
            method="POST",
            status_code=200,
        )

        await client.update_batch_metrics(
            batch_id="batch-123",
            status="completed",
            processing_wall_time_seconds=32.5,
            raw_audio_duration_seconds=600.0,
            speech_duration_seconds=450.0,
            speech_ratio=0.75,
            raw_audio_size_bytes=5_000_000,
            cleaned_audio_size_bytes=14_400_000,
            speechmatics_job_id="sm-job-abc",
            speechmatics_cost_estimate=0.04,
        )

        request = httpx_mock.get_request()
        body = json.loads(request.content)
        assert body["batch_id"] == "batch-123"
        assert body["status"] == "completed"
        assert body["processing_wall_time_seconds"] == 32.5
        assert body["raw_audio_duration_seconds"] == 600.0
        assert body["speech_duration_seconds"] == 450.0
        assert body["speech_ratio"] == 0.75
        assert body["raw_audio_size_bytes"] == 5_000_000
        assert body["cleaned_audio_size_bytes"] == 14_400_000
        assert body["speechmatics_job_id"] == "sm-job-abc"
        assert body["speechmatics_cost_estimate"] == 0.04
        assert "processing_completed_at" in body

    async def test_failure_sends_error_fields_and_partial_metrics(
        self, client, httpx_mock
    ):
        """update_batch_metrics includes error fields on failure."""
        httpx_mock.add_response(
            url="https://worker.example.com/internal/batch-status",
            method="POST",
            status_code=200,
        )

        await client.update_batch_metrics(
            batch_id="batch-456",
            status="failed",
            processing_wall_time_seconds=5.0,
            error_stage="asr",
            error_message="Speechmatics timeout",
            retry_count=3,
        )

        request = httpx_mock.get_request()
        body = json.loads(request.content)
        assert body["status"] == "failed"
        assert body["error_stage"] == "asr"
        assert body["error_message"] == "Speechmatics timeout"
        assert body["retry_count"] == 3
        # Partial metrics default to 0
        assert body["raw_audio_duration_seconds"] == 0.0

    async def test_null_handling_for_optional_metrics(self, client, httpx_mock):
        """Optional error fields are omitted when None."""
        httpx_mock.add_response(
            url="https://worker.example.com/internal/batch-status",
            method="POST",
            status_code=200,
        )

        await client.update_batch_metrics(
            batch_id="batch-789",
            status="completed",
            processing_wall_time_seconds=10.0,
        )

        request = httpx_mock.get_request()
        body = json.loads(request.content)
        assert "error_stage" not in body
        assert "error_message" not in body

    async def test_raises_on_http_error(self, client, httpx_mock):
        """update_batch_metrics raises StorageError on HTTP error."""
        httpx_mock.add_response(
            url="https://worker.example.com/internal/batch-status",
            method="POST",
            status_code=500,
        )

        with pytest.raises(StorageError, match="D1 metrics update failed"):
            await client.update_batch_metrics(
                batch_id="batch-123",
                status="completed",
                processing_wall_time_seconds=10.0,
            )


class TestD1ClientInsertProcessingStages:
    """Tests for D1Client.insert_processing_stages() (#37)."""

    @pytest.fixture
    def client(self):
        return D1Client(
            worker_url="https://worker.example.com",
            internal_secret="test-secret",
        )

    async def test_sends_correct_stage_rows(self, client, httpx_mock):
        """insert_processing_stages sends stage rows to Worker."""
        httpx_mock.add_response(
            url="https://worker.example.com/internal/processing-stages",
            method="POST",
            status_code=200,
        )

        stages = [
            {
                "stage": "transcode",
                "duration_seconds": 2.1,
                "success": True,
                "error_message": None,
            },
            {
                "stage": "vad",
                "duration_seconds": 0.8,
                "success": True,
                "error_message": None,
            },
        ]

        await client.insert_processing_stages(
            batch_id="batch-123", stages=stages
        )

        request = httpx_mock.get_request()
        body = json.loads(request.content)
        assert body["batch_id"] == "batch-123"
        assert len(body["stages"]) == 2
        assert body["stages"][0]["stage"] == "transcode"
        assert body["stages"][0]["duration_seconds"] == 2.1
        assert body["stages"][1]["stage"] == "vad"

    async def test_empty_stages_skips_request(self, client, httpx_mock):
        """insert_processing_stages does nothing for empty stages list."""
        await client.insert_processing_stages(
            batch_id="batch-123", stages=[]
        )
        # No request should have been made
        assert len(httpx_mock.get_requests()) == 0

    async def test_stage_rows_have_positive_duration(self, client, httpx_mock):
        """Stage rows include positive duration_seconds."""
        httpx_mock.add_response(
            url="https://worker.example.com/internal/processing-stages",
            method="POST",
            status_code=200,
        )

        stages = [
            {
                "stage": "asr_submit",
                "duration_seconds": 25.3,
                "success": True,
                "error_message": None,
            },
        ]

        await client.insert_processing_stages(
            batch_id="batch-123", stages=stages
        )

        request = httpx_mock.get_request()
        body = json.loads(request.content)
        assert body["stages"][0]["duration_seconds"] > 0.0

    async def test_raises_on_http_error(self, client, httpx_mock):
        """insert_processing_stages raises StorageError on HTTP error."""
        httpx_mock.add_response(
            url="https://worker.example.com/internal/processing-stages",
            method="POST",
            status_code=500,
        )

        with pytest.raises(StorageError, match="D1 stage insert failed"):
            await client.insert_processing_stages(
                batch_id="batch-123",
                stages=[{"stage": "vad", "duration_seconds": 1.0, "success": True, "error_message": None}],
            )
