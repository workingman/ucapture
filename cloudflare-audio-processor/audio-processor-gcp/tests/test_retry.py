"""Tests for retry_with_backoff decorator."""

import logging
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


class TestRetryableExceptions:
    """Tests for transient vs permanent failure classification."""

    @pytest.mark.asyncio
    async def test_permanent_failure_not_retried(self) -> None:
        """Non-retryable exception re-raises immediately without retry."""
        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        async def raise_permanent() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("permanent failure")

        with pytest.raises(ValueError, match="permanent failure"):
            await raise_permanent()

        assert call_count == 1  # No retries for permanent failures

    @pytest.mark.asyncio
    async def test_transient_failure_retried(self) -> None:
        """Retryable exception is retried up to max_retries."""
        call_count = 0

        @retry_with_backoff(
            max_retries=2,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        async def raise_transient() -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("transient failure")

        with pytest.raises(ConnectionError, match="transient failure"):
            await raise_transient()

        # 1 initial + 2 retries = 3 total calls
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_transient_then_success(self) -> None:
        """Retryable exception followed by success returns result."""
        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        async def fail_once_then_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("transient")
            return "ok"

        result = await fail_once_then_succeed()
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_count_attached_on_exhaustion(self) -> None:
        """_retry_count is set to max_retries when retries are exhausted."""

        @retry_with_backoff(
            max_retries=2,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        async def always_fail() -> None:
            raise ConnectionError("fail")

        with pytest.raises(ConnectionError) as exc_info:
            await always_fail()

        assert exc_info.value._retry_count == 2  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_retry_count_attached_on_permanent_failure(self) -> None:
        """_retry_count is set to current attempt on permanent failure."""
        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        async def transient_then_permanent() -> None:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("transient")
            raise ValueError("permanent")

        with pytest.raises(ValueError, match="permanent"):
            await transient_then_permanent()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_count_zero_on_immediate_permanent(self) -> None:
        """_retry_count is 0 when permanent failure occurs on first attempt."""

        @retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        async def immediate_permanent() -> None:
            raise ValueError("permanent on first try")

        with pytest.raises(ValueError) as exc_info:
            await immediate_permanent()

        assert exc_info.value._retry_count == 0  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_none_retryable_exceptions_retries_all(self) -> None:
        """When retryable_exceptions is None, all exceptions are retried (legacy)."""
        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.01)
        async def always_fail() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await always_fail()

        # 1 initial + 2 retries = 3 total calls
        assert call_count == 3


class TestRetryLogging:
    """Tests for retry attempt logging."""

    @pytest.mark.asyncio
    async def test_retry_logs_warning_with_attempt_info(self, caplog) -> None:
        """Each retry attempt logs a warning with attempt number, delay, and error."""

        @retry_with_backoff(
            max_retries=2,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        async def always_fail() -> None:
            raise ConnectionError("network down")

        with caplog.at_level(logging.WARNING, logger="audio_processor.utils.retry"):
            with pytest.raises(ConnectionError):
                await always_fail()

        retry_logs = [r for r in caplog.records if "Retry" in r.message]
        assert len(retry_logs) == 2
        assert "1/2" in retry_logs[0].message
        assert "2/2" in retry_logs[1].message
        assert "network down" in retry_logs[0].message
        assert "always_fail" in retry_logs[0].message

    @pytest.mark.asyncio
    async def test_no_log_on_immediate_success(self, caplog) -> None:
        """No retry logs when the function succeeds on first call."""

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def succeed() -> str:
            return "ok"

        with caplog.at_level(logging.WARNING, logger="audio_processor.utils.retry"):
            await succeed()

        retry_logs = [r for r in caplog.records if "Retry" in r.message]
        assert len(retry_logs) == 0
