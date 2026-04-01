"""Social handle availability provider — HTTP checks, zero cost."""

from __future__ import annotations

import asyncio

import httpx

from namera.providers.base import Availability, CheckType, Provider, ProviderResult

# Platform URLs — {name} is replaced with the handle
PLATFORMS: dict[str, str] = {
    "github": "https://github.com/{name}",
    "twitter": "https://x.com/{name}",
    "instagram": "https://www.instagram.com/{name}/",
}

# HTTP status codes that indicate the handle is available (not found)
_NOT_FOUND = {404}

# User-agent to avoid bot blocks
_USER_AGENT = "Mozilla/5.0 (compatible; Namera/0.1; +https://github.com/namera)"


class SocialHandleProvider(Provider):
    """Check social media handle availability via HTTP."""

    name = "social"
    check_type = CheckType.SOCIAL

    @classmethod
    def cache_kwargs(cls, kwargs: dict) -> dict:
        return {"social_platforms": kwargs.get("social_platforms")}

    async def check(self, query: str, **kwargs) -> ProviderResult:
        platforms_to_check = kwargs.get("social_platforms", list(PLATFORMS.keys()))
        results: dict[str, Availability] = {}

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10.0,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            tasks = {
                platform: self._check_platform(client, platform, query)
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
                "platform_availability": {p: av for p, av in results.items()},
            },
        )

    async def _check_platform(
        self, client: httpx.AsyncClient, platform: str, handle: str
    ) -> Availability:
        """Check a single platform. Returns an Availability enum value."""
        url = PLATFORMS[platform].format(name=handle)
        try:
            resp = await client.head(url)
            if resp.status_code in _NOT_FOUND:
                return Availability.AVAILABLE
            if 200 <= resp.status_code < 400:
                return Availability.TAKEN
            return Availability.UNKNOWN
        except httpx.HTTPError:
            return Availability.UNKNOWN
