"""Trademark provider backed by a Supabase Edge Function.

Calls the public /functions/v1/trademark-check endpoint backed by USPTO data.
No credentials are required in the CLI, and batched checks reuse the durable
SQLite cache already used elsewhere in the project.
"""

from __future__ import annotations

import os

import httpx

from namera.cache import get_cache
from namera.providers.base import Availability, CheckType, Provider, ProviderResult
from namera.retry import with_retry

# Public endpoint — no API key needed (verify_jwt=false on the Edge Function).
# Edge Function uses service_role internally to query namera schema.
_DEFAULT_ENDPOINT = (
    "https://wmnzjmrysnzjthldgffh.supabase.co/functions/v1/trademark-check"
)
TRADEMARK_API_URL = os.environ.get("NAMERA_TRADEMARK_API_URL", _DEFAULT_ENDPOINT)
_BATCH_SIZE = 50


def _build_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=10,
        limits=httpx.Limits(
            max_connections=20,
            max_keepalive_connections=10,
        ),
    )


class SupabaseTrademarkProvider(Provider):
    """Exact trademark match against USPTO data."""

    name = "uspto"
    check_type = CheckType.TRADEMARK

    @classmethod
    def cache_kwargs(cls, kwargs: dict) -> dict:
        return {"nice_classes": kwargs.get("nice_classes")}

    async def check(self, query: str, **kwargs) -> ProviderResult:
        nice_classes = kwargs.get("nice_classes")
        try:
            async with _build_client() as client:
                data = await _call_api(
                    client,
                    query,
                    mode="exact",
                    nice_classes=nice_classes,
                )
        except Exception as exc:
            return ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name=self.name,
                query=query,
                available=Availability.UNKNOWN,
                error=f"Trademark lookup failed: {exc}",
            )

        return _parse_single_result(query, data, "exact")


class SupabaseSimilarityProvider(Provider):
    """Fuzzy trademark similarity via PostgreSQL trigram matching."""

    name = "trademark-similarity"
    check_type = CheckType.TRADEMARK

    @classmethod
    def cache_kwargs(cls, kwargs: dict) -> dict:
        return {
            "trademark_similarity_threshold": kwargs.get(
                "trademark_similarity_threshold",
                0.3,
            ),
            "nice_classes": kwargs.get("nice_classes"),
        }

    async def check(self, query: str, **kwargs) -> ProviderResult:
        threshold = kwargs.get("trademark_similarity_threshold", 0.3)
        nice_classes = kwargs.get("nice_classes")
        try:
            async with _build_client() as client:
                data = await _call_api(
                    client,
                    query,
                    mode="similarity",
                    threshold=threshold,
                    nice_classes=nice_classes,
                )
        except Exception as exc:
            return ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name=self.name,
                query=query,
                available=Availability.UNKNOWN,
                error=f"Similarity search failed: {exc}",
            )

        return _parse_single_result(query, data, "similarity")


async def _call_api(
    client: httpx.AsyncClient,
    query: str,
    mode: str = "both",
    threshold: float = 0.3,
    nice_classes: list[int] | None = None,
) -> dict:
    """Call the trademark-check Edge Function for a single query."""
    payload: dict = {"query": query, "mode": mode}
    if threshold != 0.3:
        payload["similarity_threshold"] = threshold
    if nice_classes:
        payload["nice_classes"] = nice_classes

    return await _post_json(client, payload)


async def _call_api_batch(
    client: httpx.AsyncClient,
    queries: list[str],
    mode: str = "both",
    threshold: float = 0.3,
    nice_classes: list[int] | None = None,
) -> dict:
    """Call the trademark-check Edge Function in batch mode."""
    payload: dict = {"queries": queries, "mode": mode}
    if threshold != 0.3:
        payload["similarity_threshold"] = threshold
    if nice_classes:
        payload["nice_classes"] = nice_classes

    return await _post_json(client, payload)


@with_retry(max_retries=2, initial_backoff=0.5)
async def _post_json(client: httpx.AsyncClient, payload: dict) -> dict:
    response = await client.post(TRADEMARK_API_URL, json=payload)
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", "60"))
        raise httpx.HTTPStatusError(
            f"Rate limited (429). Retry after {retry_after}s",
            request=response.request,
            response=response,
        )
    response.raise_for_status()
    return response.json()


async def batch_trademark_check(
    names: list[str],
    mode: str = "exact",
    threshold: float = 0.3,
    nice_classes: list[int] | None = None,
) -> list[ProviderResult]:
    """Check trademarks for multiple names using batched API requests."""
    provider_cls = SupabaseTrademarkProvider if mode == "exact" else SupabaseSimilarityProvider
    cache_kwargs = provider_cls.cache_kwargs({
        "trademark_similarity_threshold": threshold,
        "nice_classes": nice_classes,
    })
    cache = get_cache()

    results: dict[str, ProviderResult] = {}
    uncached: list[str] = []

    for name in names:
        cached = cache.get(provider_cls.name, name, cache_kwargs)
        if cached is not None:
            if cached.candidate_name is None:
                cached.candidate_name = name
            results[name] = cached
        else:
            uncached.append(name)

    if not uncached:
        return [results[name] for name in names]

    async with _build_client() as client:
        for index in range(0, len(uncached), _BATCH_SIZE):
            chunk = uncached[index : index + _BATCH_SIZE]
            try:
                payload = await _call_api_batch(
                    client,
                    chunk,
                    mode=mode,
                    threshold=threshold,
                    nice_classes=nice_classes,
                )
                batch_results = payload.get("results", {})
                for name in chunk:
                    name_data = (
                        batch_results.get(name)
                        or batch_results.get(name.upper())
                        or {}
                    )
                    result = _parse_single_result(name, name_data, mode)
                    cache.set(result, cache_kwargs)
                    results[name] = result
            except Exception:
                for name in chunk:
                    try:
                        payload = await _call_api(
                            client,
                            name,
                            mode=mode,
                            threshold=threshold,
                            nice_classes=nice_classes,
                        )
                        result = _parse_single_result(name, payload, mode)
                        cache.set(result, cache_kwargs)
                        results[name] = result
                    except Exception as exc:
                        results[name] = ProviderResult(
                            check_type=CheckType.TRADEMARK,
                            provider_name=provider_cls.name,
                            query=name,
                            candidate_name=name,
                            available=Availability.UNKNOWN,
                            error=f"Trademark lookup failed: {exc}",
                        )

    return [results[name] for name in names]


def _parse_single_result(name: str, data: dict, mode: str) -> ProviderResult:
    """Convert a single name's API response into a ProviderResult."""
    if mode == "exact":
        exact = data.get("exact", {})
        matches = exact.get("matches", [])
        if exact.get("trademarked"):
            return ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="uspto",
                query=name,
                candidate_name=name,
                available=Availability.TAKEN,
                details={
                    "matches": matches,
                    "match_count": exact.get("count", len(matches)),
                    "source": "uspto",
                },
            )

        return ProviderResult(
            check_type=CheckType.TRADEMARK,
            provider_name="uspto",
            query=name,
            candidate_name=name,
            available=Availability.AVAILABLE,
            details={
                "matches": [],
                "match_count": exact.get("count", 0),
                "source": "uspto",
            },
        )

    similarity = data.get("similarity", {})
    similar = similarity.get("matches", [])
    max_score = similarity.get("max_score", 0.0)

    if not similar:
        availability = Availability.AVAILABLE
    elif max_score >= 0.95:
        availability = Availability.TAKEN
    elif max_score >= 0.6:
        availability = Availability.UNKNOWN
    else:
        availability = Availability.AVAILABLE

    details = {
        "similar_marks": similar[:10],
        "max_similarity": round(max_score, 3),
        "source": "uspto",
    }
    if similar:
        details["note"] = (
            f"Found {len(similar)} similar mark(s), top similarity: {max_score:.0%}"
        )

    return ProviderResult(
        check_type=CheckType.TRADEMARK,
        provider_name="trademark-similarity",
        query=name,
        candidate_name=name,
        available=availability,
        details=details,
    )
