"""Queue consumer for processing audio batches.

Polls Cloudflare Queues via HTTP pull API with priority-first ordering.
Priority queue is polled before normal queue. Messages are validated,
dispatched to the pipeline, then acked or nacked.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ProcessingJob:
    """Validated processing job deserialized from a queue message.

    Per TDD Section 4.2.
    """

    batch_id: str
    user_id: str
    priority: str
    enqueued_at: str

    @classmethod
    def from_message_body(cls, body: dict[str, Any]) -> ProcessingJob:
        """Deserialize and validate a queue message body.

        Args:
            body: Raw message body dict from queue.

        Returns:
            Validated ProcessingJob.

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        batch_id = body.get("batch_id")
        if not batch_id or not isinstance(batch_id, str):
            raise ValueError("Missing or invalid 'batch_id' in message")

        user_id = body.get("user_id")
        if not user_id or not isinstance(user_id, str):
            raise ValueError("Missing or invalid 'user_id' in message")

        priority = body.get("priority", "normal")
        if priority not in ("immediate", "normal"):
            raise ValueError(
                f"Invalid 'priority': '{priority}'. "
                f"Must be 'immediate' or 'normal'"
            )

        enqueued_at = body.get("enqueued_at", "")
        if enqueued_at:
            try:
                datetime.fromisoformat(enqueued_at)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid 'enqueued_at' ISO 8601 format: '{enqueued_at}'"
                ) from exc

        return cls(
            batch_id=batch_id,
            user_id=user_id,
            priority=priority,
            enqueued_at=enqueued_at,
        )


@dataclass
class QueueMessage:
    """A message received from a Cloudflare Queue."""

    message_id: str
    lease_id: str
    body: dict[str, Any]


class QueueConsumer:
    """Cloudflare Queues HTTP pull consumer with priority-first polling.

    Polls priority queue first, then normal queue. Messages are
    validated, dispatched to the pipeline callback, and acked/nacked.

    Configuration from environment variables:
        CF_QUEUE_API_URL, CF_QUEUE_ID_PRIORITY, CF_QUEUE_ID_NORMAL,
        CF_API_TOKEN
    """

    def __init__(
        self,
        queue_api_url: str | None = None,
        queue_id_priority: str | None = None,
        queue_id_normal: str | None = None,
        cf_api_token: str | None = None,
        poll_interval: float = 5.0,
        batch_size: int = 10,
    ) -> None:
        self.queue_api_url = (
            queue_api_url or os.environ.get("CF_QUEUE_API_URL", "")
        ).rstrip("/")
        self.queue_id_priority = queue_id_priority or os.environ.get(
            "CF_QUEUE_ID_PRIORITY", ""
        )
        self.queue_id_normal = queue_id_normal or os.environ.get(
            "CF_QUEUE_ID_NORMAL", ""
        )
        self.cf_api_token = cf_api_token or os.environ.get("CF_API_TOKEN", "")
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self._running = False

    def _headers(self) -> dict[str, str]:
        """Build authentication headers for Cloudflare API."""
        return {
            "Authorization": f"Bearer {self.cf_api_token}",
            "Content-Type": "application/json",
        }

    async def _pull_messages(
        self, queue_id: str, client: httpx.AsyncClient
    ) -> list[QueueMessage]:
        """Pull messages from a single Cloudflare Queue.

        Args:
            queue_id: The Cloudflare Queue ID.
            client: Shared httpx client.

        Returns:
            List of QueueMessage objects. Empty list on error or no messages.
        """
        url = f"{self.queue_api_url}/queues/{queue_id}/messages/pull"
        try:
            response = await client.post(
                url,
                headers=self._headers(),
                json={"batch_size": self.batch_size},
                timeout=30.0,
            )
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.error("Queue pull failed for %s: %s", queue_id, exc)
            return []

        data = response.json()
        messages_data = data.get("result", {}).get("messages", [])

        messages: list[QueueMessage] = []
        for msg in messages_data:
            try:
                messages.append(
                    QueueMessage(
                        message_id=msg["id"],
                        lease_id=msg["lease_id"],
                        body=msg["body"],
                    )
                )
            except (KeyError, TypeError) as exc:
                logger.warning("Malformed queue message structure: %s", exc)

        return messages

    async def _ack_message(
        self, queue_id: str, lease_id: str, client: httpx.AsyncClient
    ) -> None:
        """Acknowledge a successfully processed message.

        Args:
            queue_id: The Cloudflare Queue ID.
            lease_id: The lease ID of the message to ack.
            client: Shared httpx client.
        """
        url = f"{self.queue_api_url}/queues/{queue_id}/messages/ack"
        try:
            response = await client.post(
                url,
                headers=self._headers(),
                json={"acks": [{"lease_id": lease_id}]},
                timeout=30.0,
            )
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.error("Ack failed for lease %s: %s", lease_id, exc)

    async def _nack_message(
        self, queue_id: str, lease_id: str, client: httpx.AsyncClient
    ) -> None:
        """Negative-acknowledge a message (return to queue for retry).

        Args:
            queue_id: The Cloudflare Queue ID.
            lease_id: The lease ID of the message to nack.
            client: Shared httpx client.
        """
        url = f"{self.queue_api_url}/queues/{queue_id}/messages/nack"
        try:
            response = await client.post(
                url,
                headers=self._headers(),
                json={"nacks": [{"lease_id": lease_id}]},
                timeout=30.0,
            )
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.error("Nack failed for lease %s: %s", lease_id, exc)

    async def _process_message(
        self,
        queue_id: str,
        message: QueueMessage,
        dispatch_fn: Any,
        d1_client: Any,
        client: httpx.AsyncClient,
    ) -> None:
        """Validate, dispatch, and ack/nack a single message.

        Args:
            queue_id: Source queue ID (for ack/nack).
            message: The queue message to process.
            dispatch_fn: Async callable(batch_id, user_id) -> ProcessingResult.
            d1_client: D1Client for status updates.
            client: Shared httpx client.
        """
        try:
            job = ProcessingJob.from_message_body(message.body)
        except ValueError as exc:
            logger.warning(
                "Invalid message %s: %s", message.message_id, exc
            )
            await self._nack_message(queue_id, message.lease_id, client)
            return

        logger.info(
            "Processing job: batch_id=%s user_id=%s priority=%s",
            job.batch_id,
            job.user_id,
            job.priority,
        )

        # Update D1 status to "processing"
        try:
            await d1_client.update_batch_status(
                batch_id=job.batch_id, status="processing"
            )
        except Exception:
            logger.error(
                "Failed to update status to 'processing' for batch %s",
                job.batch_id,
                exc_info=True,
            )

        # Dispatch to pipeline
        try:
            await dispatch_fn(job.batch_id, job.user_id)
            await self._ack_message(queue_id, message.lease_id, client)
        except Exception:
            logger.error(
                "Pipeline dispatch failed for batch %s",
                job.batch_id,
                exc_info=True,
            )
            await self._ack_message(queue_id, message.lease_id, client)

    async def poll_once(
        self,
        dispatch_fn: Any,
        d1_client: Any,
    ) -> int:
        """Execute a single poll cycle: priority queue first, then normal.

        Args:
            dispatch_fn: Async callable(batch_id, user_id) -> ProcessingResult.
            d1_client: D1Client for status updates.

        Returns:
            Total number of messages processed.
        """
        processed = 0
        async with httpx.AsyncClient() as client:
            # Priority queue first
            if self.queue_id_priority:
                messages = await self._pull_messages(
                    self.queue_id_priority, client
                )
                for msg in messages:
                    await self._process_message(
                        self.queue_id_priority,
                        msg,
                        dispatch_fn,
                        d1_client,
                        client,
                    )
                    processed += 1

            # Then normal queue
            if self.queue_id_normal:
                messages = await self._pull_messages(
                    self.queue_id_normal, client
                )
                for msg in messages:
                    await self._process_message(
                        self.queue_id_normal,
                        msg,
                        dispatch_fn,
                        d1_client,
                        client,
                    )
                    processed += 1

        return processed

    async def run(self, dispatch_fn: Any, d1_client: Any) -> None:
        """Start the polling loop. Runs until stopped.

        Args:
            dispatch_fn: Async callable(batch_id, user_id) -> ProcessingResult.
            d1_client: D1Client for status updates.
        """
        self._running = True
        logger.info("Queue consumer starting poll loop")

        while self._running:
            try:
                count = await self.poll_once(dispatch_fn, d1_client)
                if count > 0:
                    logger.info("Processed %d messages this cycle", count)
            except Exception:
                logger.error(
                    "Unexpected error in poll cycle", exc_info=True
                )

            await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        """Signal the polling loop to stop."""
        self._running = False
        logger.info("Queue consumer stopping")
