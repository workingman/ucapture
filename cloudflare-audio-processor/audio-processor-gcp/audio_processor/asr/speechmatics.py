"""Speechmatics ASR client implementation.

Implements the SpeechmaticsEngine using the Speechmatics Batch API v2.
Supports diarization and converts results to the internal Transcript model.
"""

import asyncio
import json
import logging
import time

import httpx

from audio_processor.asr.interface import (
    ASREngine,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
)
from audio_processor.utils.errors import ASRError

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://asr.api.speechmatics.com/v2"
POLL_INTERVAL_SECONDS = 5.0
TRANSIENT_STATUS_CODES = {429, 503}


class SpeechmaticsEngine(ASREngine):
    """Speechmatics Batch API ASR engine with speaker diarization.

    Submits audio files for transcription, polls for completion, and converts
    Speechmatics JSON responses into the internal Transcript data model.

    Args:
        api_key: Speechmatics API key for authentication.
        timeout: Maximum seconds to wait for job completion (default 600).
        base_url: Speechmatics API base URL (default production endpoint).
    """

    def __init__(
        self,
        api_key: str,
        timeout: int = 600,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")

    async def transcribe(self, audio_path: str, metadata: dict) -> Transcript:
        """Transcribe an audio file via Speechmatics Batch API.

        Submits the audio, polls until completion, fetches the transcript,
        and converts the response to internal data models.

        Args:
            audio_path: Path to the audio file (16kHz mono 16-bit PCM WAV).
            metadata: Batch metadata for context (e.g., language hints).

        Returns:
            Transcript with speaker-labeled segments and raw API response.

        Raises:
            ASRError: On submission failure, job rejection, or timeout.
        """
        async with httpx.AsyncClient() as client:
            job_id = await self._submit_job(client, audio_path)
            await self._poll_until_complete(client, job_id)
            raw_response = await self._fetch_transcript(client, job_id)
            return self._convert_response(raw_response)

    async def _submit_job(self, client: httpx.AsyncClient, audio_path: str) -> str:
        """Submit an audio file for transcription.

        Returns:
            The Speechmatics job ID.

        Raises:
            ASRError: If submission fails.
        """
        config = {
            "type": "transcription",
            "transcription_config": {
                "language": "en",
                "diarization": "speaker",
            },
        }

        url = f"{self._base_url}/jobs/"
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            with open(audio_path, "rb") as audio_file:
                files = {
                    "data_file": ("audio.wav", audio_file, "audio/wav"),
                }
                data = {"config": json.dumps(config)}
                response = await client.post(
                    url, headers=headers, files=files, data=data
                )
        except (OSError, httpx.HTTPError) as exc:
            raise ASRError(
                f"Failed to submit job: {exc}", provider="speechmatics"
            ) from exc

        if response.status_code == 429:
            raise ASRError(
                "Rate limited during job submission",
                provider="speechmatics",
            )
        if response.status_code == 503:
            raise ASRError(
                "Service unavailable during job submission",
                provider="speechmatics",
            )
        if response.status_code != 201:
            raise ASRError(
                f"Job submission failed with status {response.status_code}: "
                f"{response.text}",
                provider="speechmatics",
            )

        body = response.json()
        job_id = body.get("id")
        if not job_id:
            raise ASRError("No job ID in submission response", provider="speechmatics")

        logger.info("Submitted Speechmatics job %s", job_id)
        return job_id

    async def _poll_until_complete(
        self, client: httpx.AsyncClient, job_id: str
    ) -> None:
        """Poll job status until done, rejected, or timeout.

        Raises:
            ASRError: If the job is rejected, deleted, or times out.
        """
        url = f"{self._base_url}/jobs/{job_id}"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        deadline = time.monotonic() + self._timeout

        while time.monotonic() < deadline:
            try:
                response = await client.get(url, headers=headers)
            except httpx.HTTPError as exc:
                raise ASRError(
                    f"Failed to poll job status: {exc}",
                    provider="speechmatics",
                ) from exc

            if response.status_code in TRANSIENT_STATUS_CODES:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                continue

            if response.status_code != 200:
                raise ASRError(
                    f"Poll failed with status {response.status_code}: "
                    f"{response.text}",
                    provider="speechmatics",
                )

            body = response.json()
            status = body.get("job", {}).get("status", "")

            if status == "done":
                logger.info("Speechmatics job %s completed", job_id)
                return

            if status in ("rejected", "deleted"):
                raise ASRError(
                    f"Job {job_id} was {status}",
                    provider="speechmatics",
                )

            # Still running/queued, wait and poll again
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

        raise ASRError(
            f"Job {job_id} timed out after {self._timeout}s",
            provider="speechmatics",
        )

    async def _fetch_transcript(self, client: httpx.AsyncClient, job_id: str) -> dict:
        """Fetch the completed transcript.

        Returns:
            Raw Speechmatics JSON response.

        Raises:
            ASRError: If fetching the transcript fails.
        """
        url = f"{self._base_url}/jobs/{job_id}/transcript"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        params = {"format": "json-v2"}

        try:
            response = await client.get(url, headers=headers, params=params)
        except httpx.HTTPError as exc:
            raise ASRError(
                f"Failed to fetch transcript: {exc}",
                provider="speechmatics",
            ) from exc

        if response.status_code != 200:
            raise ASRError(
                f"Transcript fetch failed with status "
                f"{response.status_code}: {response.text}",
                provider="speechmatics",
            )

        return response.json()

    def _convert_response(self, raw_response: dict) -> Transcript:
        """Convert Speechmatics JSON response to internal Transcript model.

        Groups consecutive words by speaker into TranscriptSegments.
        Speaker labels are formatted as 'Speaker 1', 'Speaker 2', etc.

        Args:
            raw_response: Raw Speechmatics API JSON response.

        Returns:
            Transcript with speaker-labeled segments.
        """
        results = raw_response.get("results", [])

        if not results:
            return Transcript(segments=[], raw_response=raw_response)

        # Map Speechmatics speaker IDs (S1, S2, ...) to friendly labels
        speaker_map: dict[str, str] = {}
        segments: list[TranscriptSegment] = []
        current_speaker: str | None = None
        current_words: list[TranscriptWord] = []

        for result in results:
            # Skip punctuation and non-word types
            if result.get("type") != "word":
                continue

            alternatives = result.get("alternatives", [])
            if not alternatives:
                continue

            alt = alternatives[0]
            raw_speaker = alt.get("speaker", "UU")

            # Map raw speaker ID to friendly label
            if raw_speaker not in speaker_map:
                speaker_num = len(speaker_map) + 1
                speaker_map[raw_speaker] = f"Speaker {speaker_num}"

            friendly_speaker = speaker_map[raw_speaker]

            word = TranscriptWord(
                text=alt.get("content", ""),
                start_time=result.get("start_time", 0.0),
                end_time=result.get("end_time", 0.0),
                confidence=alt.get("confidence", 0.0),
            )

            # Start new segment on speaker change
            if friendly_speaker != current_speaker:
                if current_words and current_speaker is not None:
                    segments.append(
                        TranscriptSegment(
                            speaker_label=current_speaker,
                            words=current_words,
                        )
                    )
                current_speaker = friendly_speaker
                current_words = [word]
            else:
                current_words.append(word)

        # Flush final segment
        if current_words and current_speaker is not None:
            segments.append(
                TranscriptSegment(
                    speaker_label=current_speaker,
                    words=current_words,
                )
            )

        return Transcript(segments=segments, raw_response=raw_response)
