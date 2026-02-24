"""Queue consumer entry point for the audio processing pipeline.

Starts the QueueConsumer polling loop alongside a lightweight HTTP
health check server (Cloud Run requires a listening port). Handles
SIGTERM for graceful shutdown.
"""

import asyncio
import logging
import os
import signal
import sys
from asyncio import StreamReader, StreamWriter

from audio_processor.observability.logger import StructuredJsonFormatter
from audio_processor.pipeline import process_batch
from audio_processor.queue.consumer import QueueConsumer
from audio_processor.storage.d1_client import D1Client

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    """Configure root logger with structured JSON output for GCP."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJsonFormatter())
    root.addHandler(handler)


async def _health_handler(reader: StreamReader, writer: StreamWriter) -> None:
    """Minimal HTTP handler that returns 200 OK for Cloud Run probes."""
    await reader.read(4096)
    response = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/plain\r\n"
        "Content-Length: 2\r\n"
        "\r\n"
        "ok"
    )
    writer.write(response.encode())
    await writer.drain()
    writer.close()


async def _run(consumer: QueueConsumer, d1_client: D1Client) -> None:
    """Run the health server and queue consumer concurrently."""
    port = int(os.environ.get("PORT", "8080"))
    server = await asyncio.start_server(_health_handler, "0.0.0.0", port)
    logger.info("Health server listening on port %d", port)

    async def _dispatch(batch_id: str, user_id: str) -> None:
        await process_batch(batch_id, user_id)

    consumer_task = asyncio.create_task(consumer.run(_dispatch, d1_client))

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown() -> None:
        logger.info("Received shutdown signal")
        consumer.stop()
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown)

    await stop_event.wait()
    consumer_task.cancel()
    server.close()
    await server.wait_closed()


def main() -> None:
    """Start the queue consumer and process incoming batches."""
    _setup_logging()
    logger.info("Audio processor starting")

    consumer = QueueConsumer()
    d1_client = D1Client()

    asyncio.run(_run(consumer, d1_client))


if __name__ == "__main__":
    main()
