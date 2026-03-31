from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from namera.providers.base import (
    Availability,
    CheckType,
    Provider,
    ProviderResult,
    registry,
)
from namera.runner import run_checks, run_checks_multi

# ---------------------------------------------------------------------------
# Helpers: mock providers that register/unregister cleanly
# ---------------------------------------------------------------------------

class _SlowProvider(Provider):
    """Provider that sleeps for a configurable duration."""

    name = "test-slow"
    check_type = CheckType.DOMAIN

    sleep_time: float = 0.05

    async def check(self, query: str, **kwargs) -> ProviderResult:
        await asyncio.sleep(self.sleep_time)
        return ProviderResult(
            check_type=self.check_type,
            provider_name=self.name,
            query=query,
            available=Availability.AVAILABLE,
        )


class _ErrorProvider(Provider):
    """Provider that always raises."""

    name = "test-error"
    check_type = CheckType.WHOIS

    async def check(self, query: str, **kwargs) -> ProviderResult:
        raise RuntimeError("boom")


class _HangProvider(Provider):
    """Provider that hangs forever (for timeout tests)."""

    name = "test-hang"
    check_type = CheckType.TRADEMARK

    async def check(self, query: str, **kwargs) -> ProviderResult:
        await asyncio.sleep(9999)
        return ProviderResult(
            check_type=self.check_type,
            provider_name=self.name,
            query=query,
            available=Availability.AVAILABLE,
        )


# Track concurrency for the concurrency-limit test
_concurrent = 0
_max_concurrent = 0


class _ConcurrencyTracker(Provider):
    """Provider that tracks how many instances run at the same time."""

    name = "test-concurrency"
    check_type = CheckType.DOMAIN

    async def check(self, query: str, **kwargs) -> ProviderResult:
        global _concurrent, _max_concurrent
        _concurrent += 1
        if _concurrent > _max_concurrent:
            _max_concurrent = _concurrent
        await asyncio.sleep(0.05)
        _concurrent -= 1
        return ProviderResult(
            check_type=self.check_type,
            provider_name=self.name,
            query=query,
            available=Availability.AVAILABLE,
        )


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Save and restore the registry around each test so mock providers don't leak."""
    saved = dict(registry._providers)
    yield
    registry._providers = saved


@pytest.fixture(autouse=True)
def _mock_cache():
    """Use a no-op cache for runner tests so real cache doesn't interfere."""
    mock_cache = MagicMock()
    mock_cache.get.return_value = None  # always miss
    mock_cache.set.return_value = None
    with patch("namera.runner.get_cache", return_value=mock_cache):
        yield


@pytest.fixture()
def _reset_concurrency_counters():
    global _concurrent, _max_concurrent
    _concurrent = 0
    _max_concurrent = 0
    yield
    _concurrent = 0
    _max_concurrent = 0


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_produces_unknown():
    """A provider that hangs should be timed out and return UNKNOWN with an error."""
    # Only keep the hang provider for TRADEMARK
    registry._providers = {_HangProvider.name: _HangProvider}

    results = await run_checks(
        "testname",
        [CheckType.TRADEMARK],
        timeout=0.1,
    )

    assert len(results) == 1
    r = results[0]
    assert r.available == Availability.UNKNOWN
    assert r.error is not None
    assert "Timed out" in r.error


@pytest.mark.asyncio
async def test_exception_produces_unknown():
    """A provider that raises should return UNKNOWN with the error message."""
    registry._providers = {_ErrorProvider.name: _ErrorProvider}

    results = await run_checks("testname", [CheckType.WHOIS])

    assert len(results) == 1
    r = results[0]
    assert r.available == Availability.UNKNOWN
    assert r.error == "boom"


@pytest.mark.asyncio
async def test_semaphore_limits_concurrency(_reset_concurrency_counters):
    """The semaphore should cap how many checks run at once."""
    global _max_concurrent
    registry._providers = {_ConcurrencyTracker.name: _ConcurrencyTracker}

    # Run 10 names with concurrency capped at 3
    names = [f"name{i}" for i in range(10)]
    await run_checks_multi(
        names,
        [CheckType.DOMAIN],
        concurrency=3,
        timeout=5.0,
    )

    assert _max_concurrent <= 3, f"max concurrent was {_max_concurrent}, expected <= 3"
    assert _max_concurrent >= 1, "at least one check should have run"


@pytest.mark.asyncio
async def test_run_checks_multi_returns_all_results():
    """run_checks_multi should return one result per (name, provider) pair."""
    registry._providers = {_SlowProvider.name: _SlowProvider}

    names = ["alpha", "bravo", "charlie"]
    results = await run_checks_multi(
        names,
        [CheckType.DOMAIN],
        timeout=5.0,
    )

    assert len(results) == 3
    queries = {r.query for r in results}
    assert queries == {"alpha", "bravo", "charlie"}
    for r in results:
        assert r.available == Availability.AVAILABLE


@pytest.mark.asyncio
async def test_run_checks_single_name():
    """run_checks should work correctly for a single name."""
    registry._providers = {_SlowProvider.name: _SlowProvider}

    results = await run_checks("myname", [CheckType.DOMAIN])

    assert len(results) == 1
    assert results[0].query == "myname"
    assert results[0].available == Availability.AVAILABLE


@pytest.mark.asyncio
async def test_run_checks_no_providers():
    """When no providers match the check type, return an empty list."""
    registry._providers = {}

    results = await run_checks("noone", [CheckType.DOMAIN])

    assert results == []


@pytest.mark.asyncio
async def test_run_checks_multi_shared_semaphore(_reset_concurrency_counters):
    """The semaphore in run_checks_multi is shared across all names."""
    global _max_concurrent
    registry._providers = {_ConcurrencyTracker.name: _ConcurrencyTracker}

    names = [f"n{i}" for i in range(20)]
    await run_checks_multi(
        names,
        [CheckType.DOMAIN],
        concurrency=5,
        timeout=5.0,
    )

    assert _max_concurrent <= 5, f"max concurrent was {_max_concurrent}, expected <= 5"
