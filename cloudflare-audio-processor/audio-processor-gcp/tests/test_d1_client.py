"""Tests for audio_processor.storage.d1_client module."""

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
