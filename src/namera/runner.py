from __future__ import annotations

import asyncio

from namera.cache import get_cache
from namera.providers.base import Availability, CheckType, ProviderResult, registry

DEFAULT_CONCURRENCY = 15
DEFAULT_TIMEOUT = 15.0  # seconds per check


async def run_checks(
    name: str,
    check_types: list[CheckType],
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout: float = DEFAULT_TIMEOUT,
    **kwargs,
) -> list[ProviderResult]:
    """Run all provider checks for a single name with bounded concurrency."""
    tasks = []
    for ct in check_types:
        for provider_cls in registry.list_by_type(ct):
            tasks.append((provider_cls, name, kwargs))

    sem = asyncio.Semaphore(concurrency)

    cache = get_cache()

    async def _check(provider_cls, check_name, check_kwargs):
        async with sem:
            # Check cache first
            cached = cache.get(provider_cls.name, check_name, check_kwargs)
            if cached is not None:
                return cached

            provider = provider_cls()
            try:
                result = await asyncio.wait_for(
                    provider.check(check_name, **check_kwargs),
                    timeout=timeout,
                )
                cache.set(result, check_kwargs)
                return result
            except asyncio.TimeoutError:
                return ProviderResult(
                    check_type=provider_cls.check_type,
                    provider_name=provider_cls.name,
                    query=check_name,
                    available=Availability.UNKNOWN,
                    error=f"Timed out after {timeout}s",
                )
            except Exception as e:
                return ProviderResult(
                    check_type=provider_cls.check_type,
                    provider_name=provider_cls.name,
                    query=check_name,
                    available=Availability.UNKNOWN,
                    error=str(e),
                )

    coros = [_check(pc, n, kw) for pc, n, kw in tasks]
    results = await asyncio.gather(*coros)
    return list(results)


async def run_checks_multi(
    names: list[str],
    check_types: list[CheckType],
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout: float = DEFAULT_TIMEOUT,
    **kwargs,
) -> list[ProviderResult]:
    """Run checks for multiple names. The semaphore is shared across ALL names."""
    sem = asyncio.Semaphore(concurrency)
    all_tasks = []

    for name in names:
        for ct in check_types:
            for provider_cls in registry.list_by_type(ct):
                all_tasks.append((provider_cls, name))

    cache = get_cache()

    async def _check(provider_cls, check_name):
        async with sem:
            cached = cache.get(provider_cls.name, check_name, kwargs)
            if cached is not None:
                return cached

            provider = provider_cls()
            try:
                result = await asyncio.wait_for(
                    provider.check(check_name, **kwargs),
                    timeout=timeout,
                )
                cache.set(result, kwargs)
                return result
            except asyncio.TimeoutError:
                return ProviderResult(
                    check_type=provider_cls.check_type,
                    provider_name=provider_cls.name,
                    query=check_name,
                    available=Availability.UNKNOWN,
                    error=f"Timed out after {timeout}s",
                )
            except Exception as e:
                return ProviderResult(
                    check_type=provider_cls.check_type,
                    provider_name=provider_cls.name,
                    query=check_name,
                    available=Availability.UNKNOWN,
                    error=str(e),
                )

    coros = [_check(pc, n) for pc, n in all_tasks]
    results = await asyncio.gather(*coros)
    return list(results)
