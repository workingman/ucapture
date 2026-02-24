"""Tests for SpeechmaticsEngine Batch API client."""

import io
import json
from unittest.mock import patch

import httpx
import pytest

from audio_processor.asr.interface import ASREngine, Transcript
from audio_processor.asr.speechmatics import SpeechmaticsEngine
from audio_processor.utils.errors import ASRError


def _make_response(
    status_code: int = 200,
    json_data: dict | None = None,
    text: str = "",
) -> httpx.Response:
    """Build a mock httpx.Response with proper content encoding."""
    if json_data is not None:
        content = json.dumps(json_data).encode("utf-8")
        headers = {"content-type": "application/json"}
    else:
        content = text.encode("utf-8")
        headers = {"content-type": "text/plain"}
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers=headers,
        request=httpx.Request("GET", "https://mock"),
    )


# -- Speechmatics response fixtures --

SUBMIT_RESPONSE = {"id": "job-abc-123"}

STATUS_RUNNING = {"job": {"status": "running"}}
STATUS_DONE = {"job": {"status": "done"}}
STATUS_REJECTED = {"job": {"status": "rejected"}}
STATUS_DELETED = {"job": {"status": "deleted"}}

SINGLE_SPEAKER_TRANSCRIPT = {
    "results": [
        {
            "type": "word",
            "start_time": 0.5,
            "end_time": 0.9,
            "alternatives": [{"content": "hello", "confidence": 0.95, "speaker": "S1"}],
        },
        {
            "type": "word",
            "start_time": 1.0,
            "end_time": 1.4,
            "alternatives": [{"content": "world", "confidence": 0.88, "speaker": "S1"}],
        },
    ]
}

MULTI_SPEAKER_TRANSCRIPT = {
    "results": [
        {
            "type": "word",
            "start_time": 0.5,
            "end_time": 0.9,
            "alternatives": [{"content": "hello", "confidence": 0.95, "speaker": "S1"}],
        },
        {
            "type": "word",
            "start_time": 1.0,
            "end_time": 1.4,
            "alternatives": [{"content": "hi", "confidence": 0.90, "speaker": "S2"}],
        },
        {
            "type": "word",
            "start_time": 1.5,
            "end_time": 2.0,
            "alternatives": [{"content": "there", "confidence": 0.85, "speaker": "S2"}],
        },
        {
            "type": "word",
            "start_time": 2.1,
            "end_time": 2.5,
            "alternatives": [{"content": "great", "confidence": 0.92, "speaker": "S1"}],
        },
    ]
}

EMPTY_TRANSCRIPT = {"results": []}


def _build_mock_client(handler) -> httpx.AsyncClient:
    """Create an AsyncClient backed by a MockTransport handler."""
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


class TestSpeechmaticsEngineConstruction:
    """Tests for SpeechmaticsEngine initialization."""

    def test_requires_api_key(self) -> None:
        with pytest.raises(ValueError, match="api_key is required"):
            SpeechmaticsEngine(api_key="")

    def test_default_timeout(self) -> None:
        engine = SpeechmaticsEngine(api_key="test-key")
        assert engine._timeout == 600

    def test_custom_timeout(self) -> None:
        engine = SpeechmaticsEngine(api_key="test-key", timeout=120)
        assert engine._timeout == 120

    def test_isinstance_asr_engine(self) -> None:
        engine = SpeechmaticsEngine(api_key="test-key")
        assert isinstance(engine, ASREngine)


class TestSubmitJob:
    """Tests for job submission to Speechmatics Batch API."""

    async def test_submit_sends_correct_config(self) -> None:
        """Verify submission includes language='en' and diarization='speaker'."""
        engine = SpeechmaticsEngine(api_key="test-key", base_url="https://mock-api")

        call_log: list[httpx.Request] = []

        def mock_handler(request: httpx.Request) -> httpx.Response:
            call_log.append(request)
            url = str(request.url)
            if request.method == "POST" and "/jobs/" in url:
                return _make_response(201, SUBMIT_RESPONSE)
            if request.method == "GET" and "/transcript" in url:
                return _make_response(200, SINGLE_SPEAKER_TRANSCRIPT)
            if request.method == "GET" and "/jobs/" in url:
                return _make_response(200, STATUS_DONE)
            return _make_response(404)

        client = _build_mock_client(mock_handler)

        with patch("builtins.open", return_value=io.BytesIO(b"fake audio")):
            job_id = await engine._submit_job(client, "/fake/audio.wav")
            await engine._poll_until_complete(client, job_id)
            raw = await engine._fetch_transcript(client, job_id)
            result = engine._convert_response(raw)

        # Verify the POST request was made
        post_requests = [r for r in call_log if r.method == "POST"]
        assert len(post_requests) == 1

        # Check authorization header
        assert post_requests[0].headers["authorization"] == "Bearer test-key"

        # Check the config in the multipart form data body
        content = post_requests[0].content.decode("utf-8", errors="replace")
        assert "transcription" in content
        assert "en" in content
        assert "speaker" in content
        assert isinstance(result, Transcript)


class TestPollStatus:
    """Tests for job status polling."""

    async def test_poll_running_then_done(self) -> None:
        """Verify polling continues when status is 'running' and stops at 'done'."""
        engine = SpeechmaticsEngine(api_key="test-key", base_url="https://mock-api")

        poll_count = 0

        def mock_handler(request: httpx.Request) -> httpx.Response:
            nonlocal poll_count
            url = str(request.url)
            if request.method == "POST" and "/jobs/" in url:
                return _make_response(201, SUBMIT_RESPONSE)
            if request.method == "GET" and "/transcript" in url:
                return _make_response(200, SINGLE_SPEAKER_TRANSCRIPT)
            if request.method == "GET" and "/jobs/" in url:
                poll_count += 1
                if poll_count < 3:
                    return _make_response(200, STATUS_RUNNING)
                return _make_response(200, STATUS_DONE)
            return _make_response(404)

        client = _build_mock_client(mock_handler)

        with patch("audio_processor.asr.speechmatics.POLL_INTERVAL_SECONDS", 0.01):
            await engine._poll_until_complete(client, "job-abc-123")

        assert poll_count == 3

    async def test_poll_done_returns_immediately(self) -> None:
        """Verify immediate 'done' status returns without extra polls."""
        engine = SpeechmaticsEngine(api_key="test-key", base_url="https://mock-api")

        poll_count = 0

        def mock_handler(request: httpx.Request) -> httpx.Response:
            nonlocal poll_count
            url = str(request.url)
            if request.method == "GET" and "/jobs/" in url:
                poll_count += 1
                return _make_response(200, STATUS_DONE)
            return _make_response(404)

        client = _build_mock_client(mock_handler)
        await engine._poll_until_complete(client, "job-abc-123")
        assert poll_count == 1

    async def test_poll_rejected_raises_asr_error(self) -> None:
        """Verify 'rejected' status raises ASRError."""
        engine = SpeechmaticsEngine(api_key="test-key", base_url="https://mock-api")

        def mock_handler(request: httpx.Request) -> httpx.Response:
            return _make_response(200, STATUS_REJECTED)

        client = _build_mock_client(mock_handler)

        with pytest.raises(ASRError, match="rejected"):
            await engine._poll_until_complete(client, "job-abc-123")

    async def test_poll_deleted_raises_asr_error(self) -> None:
        """Verify 'deleted' status raises ASRError."""
        engine = SpeechmaticsEngine(api_key="test-key", base_url="https://mock-api")

        def mock_handler(request: httpx.Request) -> httpx.Response:
            return _make_response(200, STATUS_DELETED)

        client = _build_mock_client(mock_handler)

        with pytest.raises(ASRError, match="deleted"):
            await engine._poll_until_complete(client, "job-abc-123")

    async def test_poll_timeout_raises_asr_error(self) -> None:
        """Verify exceeding timeout raises ASRError."""
        engine = SpeechmaticsEngine(
            api_key="test-key", base_url="https://mock-api", timeout=0
        )

        def mock_handler(request: httpx.Request) -> httpx.Response:
            return _make_response(200, STATUS_RUNNING)

        client = _build_mock_client(mock_handler)

        with patch("audio_processor.asr.speechmatics.POLL_INTERVAL_SECONDS", 0.01):
            with pytest.raises(ASRError, match="timed out"):
                await engine._poll_until_complete(client, "job-abc-123")


class TestConvertResponse:
    """Tests for Speechmatics response conversion to Transcript model."""

    def test_single_speaker_all_words_in_one_segment(self) -> None:
        """Verify single-speaker transcript has one segment with 'Speaker 1'."""
        engine = SpeechmaticsEngine(api_key="test-key")
        transcript = engine._convert_response(SINGLE_SPEAKER_TRANSCRIPT)

        assert len(transcript.segments) == 1
        assert transcript.segments[0].speaker_label == "Speaker 1"
        assert len(transcript.segments[0].words) == 2
        assert transcript.segments[0].words[0].text == "hello"
        assert transcript.segments[0].words[1].text == "world"

    def test_multi_speaker_groups_by_speaker(self) -> None:
        """Verify multi-speaker transcript groups words by speaker changes."""
        engine = SpeechmaticsEngine(api_key="test-key")
        transcript = engine._convert_response(MULTI_SPEAKER_TRANSCRIPT)

        assert len(transcript.segments) == 3
        assert transcript.segments[0].speaker_label == "Speaker 1"
        assert transcript.segments[0].words[0].text == "hello"
        assert transcript.segments[1].speaker_label == "Speaker 2"
        assert len(transcript.segments[1].words) == 2
        assert transcript.segments[2].speaker_label == "Speaker 1"
        assert transcript.segments[2].words[0].text == "great"

    def test_empty_response_returns_empty_segments(self) -> None:
        """Verify empty results produce empty segments list."""
        engine = SpeechmaticsEngine(api_key="test-key")
        transcript = engine._convert_response(EMPTY_TRANSCRIPT)

        assert len(transcript.segments) == 0

    def test_raw_response_preserved(self) -> None:
        """Verify raw Speechmatics response is preserved in Transcript."""
        engine = SpeechmaticsEngine(api_key="test-key")
        transcript = engine._convert_response(SINGLE_SPEAKER_TRANSCRIPT)

        assert transcript.raw_response == SINGLE_SPEAKER_TRANSCRIPT

    def test_word_fields_populated(self) -> None:
        """Verify TranscriptWord fields are populated from Speechmatics data."""
        engine = SpeechmaticsEngine(api_key="test-key")
        transcript = engine._convert_response(SINGLE_SPEAKER_TRANSCRIPT)

        word = transcript.segments[0].words[0]
        assert word.text == "hello"
        assert word.start_time == 0.5
        assert word.end_time == 0.9
        assert word.confidence == 0.95


class TestRetryBehavior:
    """Tests for transient error retry behavior."""

    async def test_retry_on_429_during_submit(self) -> None:
        """Verify 429 on submit raises ASRError (retry handled by decorator)."""
        engine = SpeechmaticsEngine(api_key="test-key", base_url="https://mock-api")

        def mock_handler(request: httpx.Request) -> httpx.Response:
            return _make_response(429, text="Rate limited")

        client = _build_mock_client(mock_handler)

        with patch("builtins.open", return_value=io.BytesIO(b"fake audio")):
            with pytest.raises(ASRError, match="Rate limited"):
                await engine._submit_job(client, "/fake/audio.wav")

    async def test_retry_on_503_during_submit(self) -> None:
        """Verify 503 on submit raises ASRError (retry handled by decorator)."""
        engine = SpeechmaticsEngine(api_key="test-key", base_url="https://mock-api")

        def mock_handler(request: httpx.Request) -> httpx.Response:
            return _make_response(503, text="Service unavailable")

        client = _build_mock_client(mock_handler)

        with patch("builtins.open", return_value=io.BytesIO(b"fake audio")):
            with pytest.raises(ASRError, match="Service unavailable"):
                await engine._submit_job(client, "/fake/audio.wav")
