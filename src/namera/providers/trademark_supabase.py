"""Trademark provider backed by Supabase Edge Function.

Calls the /functions/v1/trademark-check endpoint — a public, keyless API
backed by USPTO data in the namera schema. No credentials exposed to users.

Performance: shared connection pool + in-memory TTL cache.
"""

from __future__ import annotations

import os
import time

import httpx

from namera.providers.base import Availability, CheckType, Provider, ProviderResult

# Public endpoint — no API key needed (verify_jwt=false on the Edge Function).
# Edge Function uses service_role internally to query namera schema.
_DEFAULT_ENDPOINT = (
    "https://wmnzjmrysnzjthldgffh.supabase.co/functions/v1/trademark-check"
)
TRADEMARK_API_URL = os.environ.get("NAMERA_TRADEMARK_API_URL", _DEFAULT_ENDPOINT)

# ---------- shared connection pool ----------

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Reuse a single AsyncClient across all queries (connection pooling)."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
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
    return _client


# ---------- in-memory TTL cache ----------

_cache: dict[str, tuple[float, object]] = {}
_CACHE_TTL = 3600  # 1 hour — trademark data changes slowly
_CACHE_MAX = 2000  # entries


def _cache_get(key: str) -> object | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, val = entry
    if time.monotonic() - ts > _CACHE_TTL:
        del _cache[key]
        return None
    return val


def _cache_set(key: str, val: object) -> None:
    if len(_cache) >= _CACHE_MAX:
        by_age = sorted(_cache, key=lambda k: _cache[k][0])
        for k in by_age[: _CACHE_MAX // 4]:
            del _cache[k]
    _cache[key] = (time.monotonic(), val)


# ---------- providers ----------


class SupabaseTrademarkProvider(Provider):
    """Exact trademark match against USPTO data."""

    name = "uspto"
    check_type = CheckType.TRADEMARK

    async def check(self, query: str, **kwargs) -> ProviderResult:
        nice_classes = kwargs.get("nice_classes")
        cache_key = f"exact:{query.upper().strip()}:{nice_classes}"
        cached = _cache_get(cache_key)

        if cached is not None:
            data = cached
        else:
            try:
                data = await _call_api(query, mode="exact", nice_classes=nice_classes)
                _cache_set(cache_key, data)
            except Exception as e:
                return ProviderResult(
                    check_type=CheckType.TRADEMARK,
                    provider_name=self.name,
                    query=query,
                    available=Availability.UNKNOWN,
                    error=f"Trademark lookup failed: {e}",
                )

        exact = data.get("exact", {})
        matches = exact.get("matches", [])

        if exact.get("trademarked"):
            return ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name=self.name,
                query=query,
                available=Availability.TAKEN,
                details={
                    "matches": matches,
                    "match_count": exact.get("count", len(matches)),
                    "source": "uspto",
                },
            )

        return ProviderResult(
            check_type=CheckType.TRADEMARK,
            provider_name=self.name,
            query=query,
            available=Availability.AVAILABLE,
            details={
                "matches": [],
                "match_count": 0,
                "source": "uspto",
            },
        )


class SupabaseSimilarityProvider(Provider):
    """Fuzzy trademark similarity via PostgreSQL trigram matching."""

    name = "trademark-similarity"
    check_type = CheckType.TRADEMARK

    async def check(self, query: str, **kwargs) -> ProviderResult:
        threshold = kwargs.get("trademark_similarity_threshold", 0.3)
        nice_classes = kwargs.get("nice_classes")
        cache_key = f"sim:{query.upper().strip()}:{threshold}:{nice_classes}"
        cached = _cache_get(cache_key)

        if cached is not None:
            data = cached
        else:
            try:
                data = await _call_api(
                    query, mode="similarity",
                    threshold=threshold, nice_classes=nice_classes,
                )
                _cache_set(cache_key, data)
            except Exception as e:
                return ProviderResult(
                    check_type=CheckType.TRADEMARK,
                    provider_name=self.name,
                    query=query,
                    available=Availability.UNKNOWN,
                    error=f"Similarity search failed: {e}",
                )

        sim = data.get("similarity", {})
        similar = sim.get("matches", [])
        max_score = sim.get("max_score", 0.0)

        if not similar:
            return ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name=self.name,
                query=query,
                available=Availability.AVAILABLE,
                details={
                    "similar_marks": [],
                    "max_similarity": 0.0,
                    "source": "uspto",
                },
            )

        if max_score >= 0.95:
            availability = Availability.TAKEN
        elif max_score >= 0.6:
            availability = Availability.UNKNOWN
        else:
            availability = Availability.AVAILABLE

        return ProviderResult(
            check_type=CheckType.TRADEMARK,
            provider_name=self.name,
            query=query,
            available=availability,
            details={
                "similar_marks": similar[:10],
                "max_similarity": round(max_score, 3),
                "source": "uspto",
                "note": (
                    f"Found {len(similar)} similar mark(s), "
                    f"top similarity: {max_score:.0%}"
                ),
            },
        )


# ---------- shared API call ----------


async def _call_api(
    query: str,
    mode: str = "both",
    threshold: float = 0.3,
    nice_classes: list[int] | None = None,
) -> dict:
    """Call the trademark-check Edge Function."""
    payload: dict = {"query": query, "mode": mode}
    if threshold != 0.3:
        payload["similarity_threshold"] = threshold
    if nice_classes:
        payload["nice_classes"] = nice_classes

    client = _get_client()
    resp = await client.post(TRADEMARK_API_URL, json=payload)
    resp.raise_for_status()
    return resp.json()
