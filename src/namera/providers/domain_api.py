from __future__ import annotations

import os

import httpx

from namera.providers.base import Availability, CheckType, Provider, ProviderResult


class GoDaddyDomainProvider(Provider):
    """Domain availability + pricing via GoDaddy API (OTE or Production).

    Env vars:
      GODADDY_API_KEY    – API key
      GODADDY_API_SECRET – API secret
      GODADDY_ENV        – "production" or "ote" (default: "ote" for testing)
    """

    name = "domain-api"
    check_type = CheckType.DOMAIN

    OTE_BASE = "https://api.ote-godaddy.com"
    PROD_BASE = "https://api.godaddy.com"

    def _base_url(self) -> str:
        env = os.getenv("GODADDY_ENV", "ote").lower()
        return self.PROD_BASE if env == "production" else self.OTE_BASE

    def _headers(self) -> dict[str, str]:
        key = os.getenv("GODADDY_API_KEY", "")
        secret = os.getenv("GODADDY_API_SECRET", "")
        return {
            "Authorization": f"sso-key {key}:{secret}",
            "Accept": "application/json",
        }

    async def check(self, query: str, **kwargs) -> ProviderResult:
        tlds = kwargs.get("tlds", ["com", "ai", "app", "io", "dev"])
        price_max = kwargs.get("price_max")

        key = os.getenv("GODADDY_API_KEY")
        if not key:
            return await self._fallback_dns(query, tlds)

        domains_info = []
        async with httpx.AsyncClient(timeout=15) as client:
            for tld in tlds:
                domain = f"{query}.{tld}" if "." not in query else query
                info = await self._check_single(client, domain, price_max)
                domains_info.append(info)

        any_available = any(d["available"] for d in domains_info)
        return ProviderResult(
            check_type=CheckType.DOMAIN,
            provider_name=self.name,
            query=query,
            available=Availability.AVAILABLE if any_available else Availability.TAKEN,
            details={"domains": domains_info},
        )

    async def _check_single(
        self, client: httpx.AsyncClient, domain: str, price_max: float | None
    ) -> dict:
        url = f"{self._base_url()}/v1/domains/available"
        try:
            resp = await client.get(url, params={"domain": domain}, headers=self._headers())
            if resp.status_code == 200:
                data = resp.json()
                available = data.get("available", False)
                price_micros = data.get("price", 0)
                price_usd = price_micros / 1_000_000 if price_micros else None
                currency = data.get("currency", "USD")

                within_budget = True
                if price_max and price_usd:
                    within_budget = price_usd <= price_max

                return {
                    "domain": domain,
                    "available": available,
                    "price": price_usd,
                    "currency": currency,
                    "within_budget": within_budget,
                    "definitive": data.get("definitive", False),
                }
            else:
                return {
                    "domain": domain,
                    "available": False,
                    "price": None,
                    "currency": None,
                    "within_budget": None,
                    "definitive": False,
                    "error": f"API {resp.status_code}: {resp.text[:200]}",
                }
        except httpx.HTTPError as e:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": None,
                "within_budget": None,
                "definitive": False,
                "error": str(e),
            }

    async def _fallback_dns(self, query: str, tlds: list[str]) -> ProviderResult:
        """Fall back to DNS resolution when no API key is configured."""
        import asyncio
        import socket

        domains_info = []
        loop = asyncio.get_event_loop()
        for tld in tlds:
            domain = f"{query}.{tld}"
            try:
                await loop.run_in_executor(None, socket.gethostbyname, domain)
                available = False
            except socket.gaierror:
                available = True

            domains_info.append({
                "domain": domain,
                "available": available,
                "price": None,
                "currency": None,
                "within_budget": None,
                "definitive": False,
                "note": "DNS fallback — no GODADDY_API_KEY set",
            })

        any_available = any(d["available"] for d in domains_info)
        return ProviderResult(
            check_type=CheckType.DOMAIN,
            provider_name=self.name,
            query=query,
            available=Availability.AVAILABLE if any_available else Availability.TAKEN,
            details={"domains": domains_info},
        )
