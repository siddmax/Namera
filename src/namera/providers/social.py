"""Social handle availability provider — HTTP checks, zero cost."""

from __future__ import annotations

import asyncio

import httpx

from namera.providers.base import Availability, CheckType, Provider, ProviderResult

# Platform URLs — {name} is replaced with the handle
PLATFORMS: dict[str, str] = {
    "github": "https://github.com/{name}",
    "twitter": "https://publish.twitter.com/oembed?url=https://twitter.com/{name}",
    "instagram": "https://www.instagram.com/{name}/",
    "tiktok": "https://www.tiktok.com/oembed?url=https://www.tiktok.com/@{name}",
}

# HTTP status codes that indicate the handle is available (not found)
_NOT_FOUND = {404}

# User-agent to avoid bot blocks
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Platforms that use oembed (GET, not HEAD; 400/404 = available, 200 = taken)
_OEMBED_PLATFORMS = {"twitter", "tiktok"}


def _shared_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        follow_redirects=True,
        timeout=10.0,
        headers={"User-Agent": _USER_AGENT},
    )


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
                "platform_availability": {p: av.value for p, av in results.items()},
            },
        )


async def _check_platform(
    client: httpx.AsyncClient, platform: str, handle: str
) -> Availability:
    """Check a single platform. Returns an Availability enum value."""
    url = PLATFORMS[platform].format(name=handle)
    try:
        if platform in _OEMBED_PLATFORMS:
            resp = await client.get(url)
            if resp.status_code == 200:
                return Availability.TAKEN
            if resp.status_code in {400, 404}:
                return Availability.AVAILABLE
            return Availability.UNKNOWN

        resp = await client.head(url)
        if resp.status_code in _NOT_FOUND:
            return Availability.AVAILABLE
        if 200 <= resp.status_code < 400:
            return Availability.TAKEN
        return Availability.UNKNOWN
    except httpx.HTTPError:
        return Availability.UNKNOWN


async def batch_social_check(
    names: list[str],
    platforms: list[str] | None = None,
) -> list[ProviderResult]:
    """Check social handles for multiple names with a shared HTTP client.

    All platform checks across all names run concurrently under one connection pool.
    """
    provider = SocialHandleProvider()
    async with _shared_client() as client:
        coros = [
            provider.check(name, _http_client=client, social_platforms=platforms)
            for name in names
        ]
        return list(await asyncio.gather(*coros))
