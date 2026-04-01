from __future__ import annotations

import asyncio

from namera.cache import get_cache
from namera.providers.base import Availability, CheckType, ProviderResult, registry

DEFAULT_CONCURRENCY = 15
DEFAULT_TIMEOUT = 15.0  # seconds per check
_TRADEMARK_CHECK_TYPES = {CheckType.TRADEMARK}


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
            provider_kwargs = provider_cls.cache_kwargs(check_kwargs)
            # Check cache first
            cached = cache.get(provider_cls.name, check_name, provider_kwargs)
            if cached is not None:
                return _attach_candidate_name(cached, check_name)

            provider = provider_cls()
            try:
                result = await asyncio.wait_for(
                    provider.check(check_name, **check_kwargs),
                    timeout=timeout,
                )
                result = _attach_candidate_name(result, check_name)
                cache.set(result, provider_kwargs)
                return result
            except asyncio.TimeoutError:
                return ProviderResult(
                    check_type=provider_cls.check_type,
                    provider_name=provider_cls.name,
                    query=check_name,
                    available=Availability.UNKNOWN,
                    candidate_name=check_name,
                    error=f"Timed out after {timeout}s",
                )
            except Exception as e:
                return ProviderResult(
                    check_type=provider_cls.check_type,
                    provider_name=provider_cls.name,
                    query=check_name,
                    available=Availability.UNKNOWN,
                    candidate_name=check_name,
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
            provider_kwargs = provider_cls.cache_kwargs(kwargs)
            cached = cache.get(provider_cls.name, check_name, provider_kwargs)
            if cached is not None:
                return _attach_candidate_name(cached, check_name)

            provider = provider_cls()
            try:
                result = await asyncio.wait_for(
                    provider.check(check_name, **kwargs),
                    timeout=timeout,
                )
                result = _attach_candidate_name(result, check_name)
                cache.set(result, provider_kwargs)
                return result
            except asyncio.TimeoutError:
                return ProviderResult(
                    check_type=provider_cls.check_type,
                    provider_name=provider_cls.name,
                    query=check_name,
                    available=Availability.UNKNOWN,
                    candidate_name=check_name,
                    error=f"Timed out after {timeout}s",
                )
            except Exception as e:
                return ProviderResult(
                    check_type=provider_cls.check_type,
                    provider_name=provider_cls.name,
                    query=check_name,
                    available=Availability.UNKNOWN,
                    candidate_name=check_name,
                    error=str(e),
                )

    coros = [_check(pc, n) for pc, n in all_tasks]
    results = await asyncio.gather(*coros)
    return list(results)


async def run_checks_multi_batched(
    names: list[str],
    check_types: list[CheckType],
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout: float = DEFAULT_TIMEOUT,
    **kwargs,
) -> list[ProviderResult]:
    """Like run_checks_multi but batches trademark calls into single API requests.

    Domain/WHOIS/social checks run concurrently per-name (no batch protocol).
    Trademark checks are batched: 30 names → 2 API calls (exact + similarity)
    instead of 60 individual calls.
    """
    # Split: trademark checks get batched, everything else runs per-name
    non_trademark_types = [ct for ct in check_types if ct not in _TRADEMARK_CHECK_TYPES]
    has_trademark = CheckType.TRADEMARK in check_types

    results: list[ProviderResult] = []

    # Run non-trademark checks concurrently (same as run_checks_multi)
    if non_trademark_types:
        non_tm_results = await run_checks_multi(
            names, non_trademark_types,
            concurrency=concurrency, timeout=timeout, **kwargs,
        )
        results.extend(non_tm_results)

    # Batch trademark checks
    if has_trademark:
        from namera.providers.trademark_supabase import batch_trademark_check

        exact_results, sim_results = await asyncio.gather(
            asyncio.wait_for(
                batch_trademark_check(
                    names,
                    mode="exact",
                    nice_classes=kwargs.get("nice_classes"),
                ),
                timeout=timeout * 2,
            ),
            asyncio.wait_for(
                batch_trademark_check(
                    names,
                    mode="similarity",
                    threshold=kwargs.get("trademark_similarity_threshold", 0.3),
                    nice_classes=kwargs.get("nice_classes"),
                ),
                timeout=timeout * 2,
            ),
        )
        results.extend(exact_results)
        results.extend(sim_results)

    return results


def _attach_candidate_name(result: ProviderResult, candidate_name: str) -> ProviderResult:
    if result.candidate_name is None:
        result.candidate_name = candidate_name
    return result
