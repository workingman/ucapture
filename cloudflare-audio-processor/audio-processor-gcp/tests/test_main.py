"""Tests for audio_processor.main shutdown behavior."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from audio_processor.main import SHUTDOWN_TIMEOUT_SECONDS, _run


class TestShutdownTimeout:
    """Tests for graceful shutdown with timeout."""

    @pytest.mark.asyncio
    async def test_shutdown_timeout_constant_is_25(self) -> None:
        """Shutdown timeout is 25s (5s buffer before Cloud Run SIGKILL at 30s)."""
        assert SHUTDOWN_TIMEOUT_SECONDS == 25

    @pytest.mark.asyncio
    async def test_clean_shutdown_within_timeout(self) -> None:
        """Consumer that stops quickly completes shutdown without warning."""
        consumer = MagicMock()
        d1_client = AsyncMock()

        async def fake_run(dispatch_fn, d1):
            while consumer._running:
                await asyncio.sleep(0.01)

        consumer._running = True
        consumer.run = fake_run

        def stop_consumer():
            consumer._running = False

        consumer.stop.side_effect = stop_consumer

        with patch("audio_processor.main.asyncio.start_server") as mock_server:
            mock_srv = AsyncMock()
            mock_srv.close = MagicMock()
            mock_server.return_value = mock_srv

            # Patch add_signal_handler to capture the shutdown callback
            shutdown_callback = None

            def capture_handler(sig, callback):
                nonlocal shutdown_callback
                shutdown_callback = callback

            loop = asyncio.get_running_loop()
            original_add = loop.add_signal_handler
            loop.add_signal_handler = capture_handler

            try:
                task = asyncio.create_task(_run(consumer, d1_client))
                await asyncio.sleep(0.05)

                # Trigger shutdown via captured callback
                assert shutdown_callback is not None
                shutdown_callback()

                # Should complete quickly (consumer stops fast)
                await asyncio.wait_for(task, timeout=2.0)
            finally:
                loop.add_signal_handler = original_add

    @pytest.mark.asyncio
    async def test_shutdown_timeout_cancels_hanging_consumer(self) -> None:
        """When consumer hangs beyond timeout, it is cancelled with warning."""
        import audio_processor.main as main_mod

        consumer = MagicMock()
        d1_client = AsyncMock()

        async def hanging_run(dispatch_fn, d1):
            # Never completes on its own
            await asyncio.sleep(9999)

        consumer.run = hanging_run

        original_timeout = main_mod.SHUTDOWN_TIMEOUT_SECONDS
        main_mod.SHUTDOWN_TIMEOUT_SECONDS = 0.1

        try:
            with patch("audio_processor.main.asyncio.start_server") as mock_server:
                mock_srv = AsyncMock()
                mock_srv.close = MagicMock()
                mock_server.return_value = mock_srv

                shutdown_callback = None

                def capture_handler(sig, callback):
                    nonlocal shutdown_callback
                    shutdown_callback = callback

                loop = asyncio.get_running_loop()
                original_add = loop.add_signal_handler
                loop.add_signal_handler = capture_handler

                try:
                    task = asyncio.create_task(_run(consumer, d1_client))
                    await asyncio.sleep(0.05)

                    # Trigger shutdown
                    assert shutdown_callback is not None
                    shutdown_callback()

                    # Should complete within timeout + small buffer
                    await asyncio.wait_for(task, timeout=2.0)
                finally:
                    loop.add_signal_handler = original_add
        finally:
            main_mod.SHUTDOWN_TIMEOUT_SECONDS = original_timeout
