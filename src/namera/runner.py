from __future__ import annotations

import asyncio
import logging

from namera.cache import get_cache
from namera.providers.base import Availability, CheckType, ProviderResult, registry

DEFAULT_CONCURRENCY = 15
DEFAULT_TIMEOUT = 15.0  # seconds per check
_BATCHED_CHECK_TYPES = {CheckType.TRADEMARK, CheckType.SOCIAL}

logger = logging.getLogger(__name__)


async def _run_single_check(
    provider_cls,
    name: str,
    kwargs: dict,
    sem: asyncio.Semaphore,
    timeout: float = DEFAULT_TIMEOUT,
) -> ProviderResult:
    """Execute a single provider check with caching, timeout, and error handling.

    Shared by run_checks() and run_checks_multi() to avoid duplication.
    """
    async with sem:
        cache = get_cache()
        provider_kwargs = provider_cls.cache_kwargs(kwargs)
        cached = cache.get(provider_cls.name, name, provider_kwargs)
        if cached is not None:
            return _attach_candidate_name(cached, name)

        provider = provider_cls()
        try:
            result = await asyncio.wait_for(
                provider.check(name, **kwargs),
                timeout=timeout,
            )
            result = _attach_candidate_name(result, name)
            cache.set(result, provider_kwargs)
            return result
        except asyncio.TimeoutError:
            return ProviderResult(
                check_type=provider_cls.check_type,
                provider_name=provider_cls.name,
                query=name,
                available=Availability.UNKNOWN,
                candidate_name=name,
                error=f"Timed out after {timeout}s",
            )
        except Exception as e:
            return ProviderResult(
                check_type=provider_cls.check_type,
                provider_name=provider_cls.name,
                query=name,
                available=Availability.UNKNOWN,
                candidate_name=name,
                error=str(e),
            )


async def run_checks(
    name: str,
    check_types: list[CheckType],
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout: float = DEFAULT_TIMEOUT,
    **kwargs,
) -> list[ProviderResult]:
    """Run all provider checks for a single name with bounded concurrency."""
    sem = asyncio.Semaphore(concurrency)
    coros = [
        _run_single_check(provider_cls, name, kwargs, sem, timeout)
        for ct in check_types
        for provider_cls in registry.list_by_type(ct)
    ]
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
    coros = [
        _run_single_check(provider_cls, name, kwargs, sem, timeout)
        for name in names
        for ct in check_types
        for provider_cls in registry.list_by_type(ct)
    ]
    results = await asyncio.gather(*coros)
    return list(results)


async def run_checks_multi_batched(
    names: list[str],
    check_types: list[CheckType],
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout: float = DEFAULT_TIMEOUT,
    **kwargs,
) -> list[ProviderResult]:
    """Like run_checks_multi but batches trademark and social calls.

    Domain/WHOIS checks run concurrently per-name.
    Trademark checks are batched: 30 names → 2 API calls (exact + similarity).
    Social checks are batched: shared HTTP client across all names.

    Batch operations are wrapped in try/except to ensure partial failures
    don't kill the entire request — domain results survive trademark timeouts.
    """
    # Split: batched types vs per-name types
    per_name_types = [ct for ct in check_types if ct not in _BATCHED_CHECK_TYPES]
    has_trademark = CheckType.TRADEMARK in check_types
    has_social = CheckType.SOCIAL in check_types

    batch_coros = []

    # Non-batched checks concurrently per-name
    if per_name_types:
        batch_coros.append(run_checks_multi(
            names, per_name_types,
            concurrency=concurrency, timeout=timeout, **kwargs,
        ))

    # Batch trademark checks
    if has_trademark:
        from namera.providers.trademark_supabase import batch_trademark_check

        async def _batch_trademarks():
            try:
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
                return list(exact_results) + list(sim_results)
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning("Trademark batch failed: %s", e)
                return []

        batch_coros.append(_batch_trademarks())

    # Batch social checks (shared HTTP client)
    if has_social:
        from namera.providers.social import batch_social_check

        async def _batch_social():
            try:
                return await asyncio.wait_for(
                    batch_social_check(
                        names,
                        platforms=kwargs.get("social_platforms"),
                    ),
                    timeout=timeout * 2,
                )
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning("Social batch failed: %s", e)
                return []

        batch_coros.append(_batch_social())

    gathered = await asyncio.gather(*batch_coros)
    results: list[ProviderResult] = []
    for group in gathered:
        results.extend(group)

    return results


def _attach_candidate_name(result: ProviderResult, candidate_name: str) -> ProviderResult:
    if result.candidate_name is None:
        result.candidate_name = candidate_name
    return result
