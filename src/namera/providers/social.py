"""Social handle availability provider — per-platform HTTP checks."""

from __future__ import annotations

import asyncio
import logging
import re

import httpx

from namera.providers.base import Availability, CheckType, Provider, ProviderResult

logger = logging.getLogger(__name__)

PLATFORMS: dict[str, str] = {
    "github": "https://github.com/{name}",
    "twitter": "https://publish.twitter.com/oembed?url=https://twitter.com/{name}",
    "instagram": "https://www.instagram.com/{name}/",
    "tiktok": "https://www.tiktok.com/oembed?url=https://www.tiktok.com/@{name}",
}

_DESKTOP_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 "
    "Mobile/15E148 Safari/604.1"
)

_INSTAGRAM_GENERIC_TITLE = re.compile(r"<title>\s*Instagram\s*</title>", re.IGNORECASE)


def _shared_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        follow_redirects=True,
        timeout=10.0,
        headers={"User-Agent": _DESKTOP_USER_AGENT},
    )


# --- Per-platform checkers ---


async def _check_github(client: httpx.AsyncClient, handle: str) -> Availability:
    url = PLATFORMS["github"].format(name=handle)
    resp = await client.head(url)
    if resp.status_code == 404:
        return Availability.AVAILABLE
    if 200 <= resp.status_code < 400:
        return Availability.TAKEN
    return Availability.UNKNOWN


async def _check_twitter(client: httpx.AsyncClient, handle: str) -> Availability:
    url = PLATFORMS["twitter"].format(name=handle)
    resp = await client.get(url)
    if resp.status_code == 200:
        return Availability.TAKEN
    if resp.status_code == 404:
        return Availability.AVAILABLE
    return Availability.UNKNOWN


async def _check_instagram(client: httpx.AsyncClient, handle: str) -> Availability:
    url = PLATFORMS["instagram"].format(name=handle)
    resp = await client.get(url, headers={"User-Agent": _MOBILE_USER_AGENT})
    if resp.status_code != 200:
        return Availability.UNKNOWN
    if _INSTAGRAM_GENERIC_TITLE.search(resp.text):
        return Availability.AVAILABLE
    if "<title>" in resp.text.lower():
        return Availability.TAKEN
    return Availability.UNKNOWN


async def _check_tiktok(client: httpx.AsyncClient, handle: str) -> Availability:
    url = PLATFORMS["tiktok"].format(name=handle)
    resp = await client.get(url)
    if resp.status_code == 200:
        return Availability.TAKEN
    if resp.status_code == 404:
        return Availability.AVAILABLE
    return Availability.UNKNOWN


_CHECKERS: dict[str, callable] = {
    "github": _check_github,
    "twitter": _check_twitter,
    "instagram": _check_instagram,
    "tiktok": _check_tiktok,
}


async def _check_platform(
    client: httpx.AsyncClient, platform: str, handle: str
) -> Availability:
    checker = _CHECKERS.get(platform)
    if checker is None:
        return Availability.UNKNOWN
    try:
        return await checker(client, handle)
    except httpx.HTTPError:
        return Availability.UNKNOWN


class SocialHandleProvider(Provider):
    """Check social media handle availability via HTTP."""

    name = "social"
    check_type = CheckType.SOCIAL

    @classmethod
    def cache_kwargs(cls, kwargs: dict) -> dict:
        return {"social_platforms": kwargs.get("social_platforms")}

    async def check(self, query: str, **kwargs) -> ProviderResult:
        client = kwargs.get("_http_client")
        if client:
            return await self._check_all(client, query, **kwargs)
        async with _shared_client() as client:
            return await self._check_all(client, query, **kwargs)

    async def _check_all(
        self, client: httpx.AsyncClient, query: str, **kwargs
    ) -> ProviderResult:
        platforms_to_check = kwargs.get("social_platforms") or list(PLATFORMS.keys())
        results: dict[str, Availability] = {}

        tasks = {
            platform: _check_platform(client, platform, query)
            for platform in platforms_to_check
            if platform in PLATFORMS
        }
        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for platform, result in zip(tasks.keys(), gathered):
            if isinstance(result, Exception):
                results[platform] = Availability.UNKNOWN
            else:
                results[platform] = result

        available_count = sum(1 for v in results.values() if v == Availability.AVAILABLE)
        total = len(results)

        if total == 0:
            overall = Availability.UNKNOWN
        elif available_count == total:
            overall = Availability.AVAILABLE
        elif available_count == 0:
            overall = Availability.TAKEN
        else:
            overall = Availability.PARTIAL

        return ProviderResult(
            check_type=CheckType.SOCIAL,
            provider_name=self.name,
            query=query,
            available=overall,
            details={
                "platforms": {p: av.value for p, av in results.items()},
            },
        )


async def batch_social_check(
    names: list[str],
    platforms: list[str] | None = None,
) -> list[ProviderResult]:
    """Check social handles for multiple names with a shared HTTP client."""
    provider = SocialHandleProvider()
    async with _shared_client() as client:
        coros = [
            provider.check(name, _http_client=client, social_platforms=platforms)
            for name in names
        ]
        gathered = await asyncio.gather(*coros, return_exceptions=True)
        results = []
        for name, result in zip(names, gathered):
            if isinstance(result, Exception):
                logger.warning("Social check failed for %s: %s", name, result)
                results.append(ProviderResult(
                    check_type=CheckType.SOCIAL,
                    provider_name="social",
                    query=name,
                    available=Availability.UNKNOWN,
                    candidate_name=name,
                    error=str(result),
                ))
            else:
                results.append(result)
        return results
