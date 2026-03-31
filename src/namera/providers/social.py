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

    async def check(self, query: str, **kwargs) -> ProviderResult:
        platforms_to_check = kwargs.get("social_platforms", list(PLATFORMS.keys()))
        results: dict[str, str] = {}

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
                    results[platform] = "unknown"
                else:
                    results[platform] = result

        available_count = sum(1 for v in results.values() if v == "available")
        total = len(results)

        if total == 0:
            overall = Availability.UNKNOWN
        elif available_count == total:
            overall = Availability.AVAILABLE
        elif available_count == 0:
            overall = Availability.TAKEN
        else:
            overall = Availability.UNKNOWN

        return ProviderResult(
            check_type=CheckType.SOCIAL,
            provider_name=self.name,
            query=query,
            available=overall,
            details={"platforms": results},
        )

    async def _check_platform(
        self, client: httpx.AsyncClient, platform: str, handle: str
    ) -> str:
        """Check a single platform. Returns 'available', 'taken', or 'unknown'."""
        url = PLATFORMS[platform].format(name=handle)
        try:
            resp = await client.head(url)
            if resp.status_code in _NOT_FOUND:
                return "available"
            if 200 <= resp.status_code < 400:
                return "taken"
            return "unknown"
        except httpx.HTTPError:
            return "unknown"
