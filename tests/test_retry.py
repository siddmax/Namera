from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from namera.retry import is_retryable, with_retry

# ---------- is_retryable ----------


@pytest.mark.parametrize(
    "msg",
    [
        "Connection timed out",
        "timed out waiting for response",
        "Connection refused by host",
        "Connection reset by peer",
        "Temporary failure in name resolution",
        "I/O timeout",
        "Too many requests",
        "rate limit exceeded",
        "rate-limit hit",
        "Please try again later",
        "Service unavailable",
        "HTTP 503",
        "HTTP 429",
    ],
)
def test_is_retryable_matches_transient_errors(msg: str):
    assert is_retryable(Exception(msg)) is True


@pytest.mark.parametrize(
    "msg",
    [
        "invalid value",
        "key not found",
        "division by zero",
        "No such file or directory",
        "permission denied",
    ],
)
def test_is_retryable_rejects_non_transient_errors(msg: str):
    assert is_retryable(Exception(msg)) is False


def test_is_retryable_with_standard_exceptions():
    assert is_retryable(ValueError("bad input")) is False
    assert is_retryable(KeyError("missing")) is False


# ---------- with_retry ----------


@pytest.mark.asyncio
async def test_retry_succeeds_on_first_attempt():
    """No retry needed when the function succeeds immediately."""
    call_count = 0

    @with_retry(max_retries=3, initial_backoff=0.01)
    async def succeed():
        nonlocal call_count
        call_count += 1
        return "ok"

    result = await succeed()
    assert result == "ok"
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_retries_then_succeeds():
    """Function fails twice with a retryable error, then succeeds."""
    call_count = 0

    @with_retry(max_retries=3, initial_backoff=0.01, jitter=False)
    async def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise OSError("Connection timed out")
        return "recovered"

    result = await flaky()
    assert result == "recovered"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_gives_up_after_max_retries():
    """Raises the last error after exhausting all retries."""
    call_count = 0

    @with_retry(max_retries=2, initial_backoff=0.01, jitter=False)
    async def always_fail():
        nonlocal call_count
        call_count += 1
        raise OSError("Connection timed out")

    with pytest.raises(OSError, match="timed out"):
        await always_fail()

    # initial attempt + 2 retries = 3
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_does_not_retry_non_retryable():
    """Non-retryable errors are raised immediately without retrying."""
    call_count = 0

    @with_retry(max_retries=3, initial_backoff=0.01)
    async def bad_input():
        nonlocal call_count
        call_count += 1
        raise ValueError("invalid argument")

    with pytest.raises(ValueError, match="invalid argument"):
        await bad_input()

    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_backoff_increases():
    """Verify that backoff increases between retries (no jitter)."""
    sleep_times: list[float] = []

    @with_retry(
        max_retries=3,
        initial_backoff=1.0,
        backoff_factor=2.0,
        max_backoff=10.0,
        jitter=False,
    )
    async def always_fail():
        raise OSError("Connection refused")

    with patch("namera.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_sleep.side_effect = lambda t: sleep_times.append(t)
        with pytest.raises(OSError):
            await always_fail()

    assert len(sleep_times) == 3
    assert sleep_times[0] == pytest.approx(1.0)
    assert sleep_times[1] == pytest.approx(2.0)
    assert sleep_times[2] == pytest.approx(4.0)


@pytest.mark.asyncio
async def test_retry_jitter_produces_varied_sleep_times():
    """With jitter enabled, sleep times should be randomized (between 0 and backoff)."""
    sleep_times: list[float] = []

    @with_retry(
        max_retries=3,
        initial_backoff=1.0,
        backoff_factor=2.0,
        max_backoff=10.0,
        jitter=True,
    )
    async def always_fail():
        raise OSError("Connection timed out")

    with patch("namera.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_sleep.side_effect = lambda t: sleep_times.append(t)
        with pytest.raises(OSError):
            await always_fail()

    assert len(sleep_times) == 3
    # With jitter, sleep times should be in [0, backoff) for each attempt
    assert 0 <= sleep_times[0] <= 1.0
    assert 0 <= sleep_times[1] <= 2.0
    assert 0 <= sleep_times[2] <= 4.0


@pytest.mark.asyncio
async def test_retry_respects_max_backoff():
    """Backoff should be capped at max_backoff."""
    sleep_times: list[float] = []

    @with_retry(
        max_retries=4,
        initial_backoff=5.0,
        backoff_factor=3.0,
        max_backoff=10.0,
        jitter=False,
    )
    async def always_fail():
        raise OSError("Connection refused")

    with patch("namera.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_sleep.side_effect = lambda t: sleep_times.append(t)
        with pytest.raises(OSError):
            await always_fail()

    # 5.0, 10.0 (capped from 15.0), 10.0 (capped from 30.0), 10.0 (capped)
    assert sleep_times[0] == pytest.approx(5.0)
    assert sleep_times[1] == pytest.approx(10.0)
    assert sleep_times[2] == pytest.approx(10.0)
    assert sleep_times[3] == pytest.approx(10.0)
