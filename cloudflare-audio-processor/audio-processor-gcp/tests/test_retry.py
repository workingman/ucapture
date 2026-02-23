"""Tests for retry_with_backoff decorator."""

from unittest.mock import AsyncMock, patch

import pytest

from audio_processor.utils.retry import retry_with_backoff


class TestRetryWithBackoff:
    """Tests for the retry decorator with exponential backoff."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_call(self) -> None:
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def succeed_immediately() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await succeed_immediately()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure_then_succeeds(self) -> None:
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def fail_twice_then_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"attempt {call_count}")
            return "ok"

        result = await fail_twice_then_succeed()
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_last_exception_after_exhausting_retries(self) -> None:
        @retry_with_backoff(max_retries=2, base_delay=0.01)
        async def always_fail() -> None:
            raise RuntimeError("persistent failure")

        with pytest.raises(RuntimeError, match="persistent failure"):
            await always_fail()

    @pytest.mark.asyncio
    async def test_correct_number_of_retries(self) -> None:
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def count_calls() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await count_calls()

        # 1 initial + 3 retries = 4 total calls
        assert call_count == 4

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self) -> None:
        """Verify delays follow base_delay * 2^attempt pattern."""
        recorded_delays: list[float] = []

        async def mock_sleep(delay: float) -> None:
            recorded_delays.append(delay)

        @retry_with_backoff(max_retries=3, base_delay=1.0)
        async def always_fail() -> None:
            raise ValueError("fail")

        with patch("audio_processor.utils.retry.asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(ValueError):
                await always_fail()

        # Delays: 1.0 * 2^0 = 1.0, 1.0 * 2^1 = 2.0, 1.0 * 2^2 = 4.0
        assert recorded_delays == [1.0, 2.0, 4.0]

    @pytest.mark.asyncio
    async def test_preserves_function_name(self) -> None:
        @retry_with_backoff()
        async def my_function() -> None:
            pass

        assert my_function.__name__ == "my_function"

    @pytest.mark.asyncio
    async def test_zero_retries_runs_once(self) -> None:
        call_count = 0

        @retry_with_backoff(max_retries=0, base_delay=0.01)
        async def fail_once() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await fail_once()

        assert call_count == 1
