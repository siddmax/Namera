from __future__ import annotations

import asyncio
import socket

from namera.providers.base import Availability, CheckType, Provider, ProviderResult


class DnsLookupProvider(Provider):
    """Check domain availability via DNS resolution (no API key needed)."""

    name = "dns"
    check_type = CheckType.DOMAIN

    async def check(self, query: str, **kwargs) -> ProviderResult:
        tlds = kwargs.get("tlds", ["com", "net", "org", "io", "dev"])
        results = []
        for tld in tlds:
            domain = f"{query}.{tld}" if "." not in query else query
            available = await self._resolve(domain)
            results.append({"domain": domain, "available": available.value})

        all_available = all(r["available"] == Availability.AVAILABLE.value for r in results)
        return ProviderResult(
            check_type=CheckType.DOMAIN,
            provider_name=self.name,
            query=query,
            available=Availability.AVAILABLE if all_available else Availability.TAKEN,
            details={"domains": results},
        )

    async def _resolve(self, domain: str) -> Availability:
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, socket.gethostbyname, domain)
            return Availability.TAKEN
        except socket.gaierror:
            return Availability.AVAILABLE
