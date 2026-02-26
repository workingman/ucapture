"""Tests for audio_processor.queue.consumer module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from audio_processor.queue.consumer import (
    ProcessingJob,
    QueueConsumer,
    QueueMessage,
)


class TestProcessingJobValidation:
    """Tests for ProcessingJob.from_message_body() validation."""

    def test_valid_message_parses_correctly(self):
        """Valid message body produces correct ProcessingJob."""
        body = {
            "batch_id": "batch-123",
            "user_id": "user-1",
            "priority": "immediate",
            "enqueued_at": "2026-02-24T10:00:00Z",
        }
        job = ProcessingJob.from_message_body(body)
        assert job.batch_id == "batch-123"
        assert job.user_id == "user-1"
        assert job.priority == "immediate"
        assert job.enqueued_at == "2026-02-24T10:00:00Z"

    def test_missing_batch_id_raises_value_error(self):
        """Missing batch_id raises ValueError."""
        with pytest.raises(ValueError, match="batch_id"):
            ProcessingJob.from_message_body(
                {"user_id": "u1", "priority": "normal"}
            )

    def test_missing_user_id_raises_value_error(self):
        """Missing user_id raises ValueError."""
        with pytest.raises(ValueError, match="user_id"):
            ProcessingJob.from_message_body(
                {"batch_id": "b1", "priority": "normal"}
            )

    def test_invalid_priority_raises_value_error(self):
        """Invalid priority value raises ValueError."""
        with pytest.raises(ValueError, match="priority"):
            ProcessingJob.from_message_body(
                {"batch_id": "b1", "user_id": "u1", "priority": "urgent"}
            )

    def test_defaults_priority_to_normal(self):
        """Missing priority defaults to 'normal'."""
        job = ProcessingJob.from_message_body(
            {"batch_id": "b1", "user_id": "u1"}
        )
        assert job.priority == "normal"

    def test_invalid_enqueued_at_raises_value_error(self):
        """Invalid enqueued_at ISO format raises ValueError."""
        with pytest.raises(ValueError, match="enqueued_at"):
            ProcessingJob.from_message_body(
                {
                    "batch_id": "b1",
                    "user_id": "u1",
                    "enqueued_at": "not-a-date",
                }
            )


class TestQueueConsumerPollOnce:
    """Tests for QueueConsumer.poll_once() priority-first polling."""

    def _make_consumer(self):
        """Create a QueueConsumer with test configuration."""
        return QueueConsumer(
            queue_api_url="https://api.cloudflare.com/client/v4/accounts/123",
            queue_id_priority="priority-queue-id",
            queue_id_normal="normal-queue-id",
            cf_api_token="test-token",
            poll_interval=0.1,
        )

    async def test_priority_queue_polled_before_normal(self):
        """Priority queue is polled before normal queue."""
        consumer = self._make_consumer()
        poll_order = []

        original_pull = consumer._pull_messages

        async def tracking_pull(queue_id, client):
            poll_order.append(queue_id)
            return []

        consumer._pull_messages = tracking_pull

        mock_d1 = AsyncMock()
        mock_dispatch = AsyncMock()

        await consumer.poll_once(mock_dispatch, mock_d1)

        assert poll_order == ["priority-queue-id", "normal-queue-id"]

    async def test_valid_message_dispatched_and_acked(self):
        """Valid message is validated, dispatched, and acked."""
        consumer = self._make_consumer()

        msg = QueueMessage(
            message_id="msg-1",
            lease_id="lease-1",
            body={
                "batch_id": "batch-abc",
                "user_id": "user-1",
                "priority": "normal",
                "enqueued_at": "2026-02-24T10:00:00Z",
            },
        )

        async def fake_pull(queue_id, client):
            if queue_id == "priority-queue-id":
                return [msg]
            return []

        consumer._pull_messages = fake_pull
        consumer._ack_message = AsyncMock()
        consumer._nack_message = AsyncMock()

        mock_d1 = AsyncMock()
        mock_dispatch = AsyncMock()

        count = await consumer.poll_once(mock_dispatch, mock_d1)

        assert count == 1
        mock_d1.update_batch_status.assert_called_once_with(
            batch_id="batch-abc", status="processing"
        )
        mock_dispatch.assert_called_once_with("batch-abc", "user-1")
        consumer._ack_message.assert_called_once()
        consumer._nack_message.assert_not_called()

    async def test_invalid_message_nacked(self):
        """Invalid message (missing batch_id) is nacked."""
        consumer = self._make_consumer()

        msg = QueueMessage(
            message_id="msg-bad",
            lease_id="lease-bad",
            body={"user_id": "u1"},  # Missing batch_id
        )

        async def fake_pull(queue_id, client):
            if queue_id == "normal-queue-id":
                return [msg]
            return []

        consumer._pull_messages = fake_pull
        consumer._ack_message = AsyncMock()
        consumer._nack_message = AsyncMock()

        mock_d1 = AsyncMock()
        mock_dispatch = AsyncMock()

        count = await consumer.poll_once(mock_dispatch, mock_d1)

        assert count == 1
        mock_dispatch.assert_not_called()
        consumer._nack_message.assert_called_once()
        consumer._ack_message.assert_not_called()

    async def test_d1_status_updated_to_processing(self):
        """D1 status is updated to 'processing' on job pickup."""
        consumer = self._make_consumer()

        msg = QueueMessage(
            message_id="msg-1",
            lease_id="lease-1",
            body={"batch_id": "b1", "user_id": "u1", "priority": "normal"},
        )

        async def fake_pull(queue_id, client):
            if queue_id == "priority-queue-id":
                return [msg]
            return []

        consumer._pull_messages = fake_pull
        consumer._ack_message = AsyncMock()
        consumer._nack_message = AsyncMock()

        mock_d1 = AsyncMock()
        mock_dispatch = AsyncMock()

        await consumer.poll_once(mock_dispatch, mock_d1)

        mock_d1.update_batch_status.assert_called_once_with(
            batch_id="b1", status="processing"
        )

    async def test_dispatch_exception_acks_message(self):
        """When dispatch_fn raises, message is still acked (not nacked)."""
        consumer = self._make_consumer()

        msg = QueueMessage(
            message_id="msg-err",
            lease_id="lease-err",
            body={"batch_id": "b-err", "user_id": "u1", "priority": "normal"},
        )

        async def fake_pull(queue_id, client):
            if queue_id == "priority-queue-id":
                return [msg]
            return []

        consumer._pull_messages = fake_pull
        consumer._ack_message = AsyncMock()
        consumer._nack_message = AsyncMock()

        mock_d1 = AsyncMock()
        mock_dispatch = AsyncMock(side_effect=RuntimeError("pipeline boom"))

        count = await consumer.poll_once(mock_dispatch, mock_d1)

        assert count == 1
        mock_dispatch.assert_called_once_with("b-err", "u1")
        consumer._ack_message.assert_called_once()
        consumer._nack_message.assert_not_called()
