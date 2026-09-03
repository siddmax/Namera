from __future__ import annotations

import asyncio
import socket

from namera.providers.base import Availability, CheckType, Provider, ProviderResult
from namera.providers.whois_servers import WHOIS_SERVERS
from namera.retry import with_retry

WHOIS_PORT = 43

# Explicit "this domain is not registered" markers used by the registries we
# query. A registry that is rate-limiting us, truncating, or erroring emits
# none of these — and must never be read as "available".
_NOT_FOUND_MARKERS = (
    "no match for",
    "no match\n",
    "not found",
    "no data found",
    "no entries found",
    "no object found",
    "status: free",
    "status: available",
    "domain status: no object found",
)


def classify_whois_response(raw: str) -> Availability:
    """Classify a raw WHOIS response into TAKEN / AVAILABLE / UNKNOWN.

    TAKEN needs a record, AVAILABLE needs an explicit not-found marker.
    Anything else is UNKNOWN: absence of a record is not evidence of
    availability, and treating it as such is how parked domains get
    reported as free.
    """
    text = raw.lower()
    if "domain name:" in text or "\ndomain:" in text:
        return Availability.TAKEN
    if any(marker in text for marker in _NOT_FOUND_MARKERS):
        return Availability.AVAILABLE
    return Availability.UNKNOWN


class WhoisProvider(Provider):
    """WHOIS lookup via raw socket connection (no API key needed)."""

    name = "whois"
    check_type = CheckType.WHOIS

    @classmethod
    def cache_kwargs(cls, kwargs: dict) -> dict:
        return {}

    async def check(self, query: str, **kwargs) -> ProviderResult:
        domain = query if "." in query else f"{query}.com"
        tld = domain.rsplit(".", 1)[-1]
        server = WHOIS_SERVERS.get(tld)

        if not server:
            return ProviderResult(
                check_type=CheckType.WHOIS,
                provider_name=self.name,
                query=domain,
                available=Availability.UNKNOWN,
                error=f"No WHOIS server known for .{tld}",
            )

        try:
            raw = await self._query_whois(server, domain)
            return ProviderResult(
                check_type=CheckType.WHOIS,
                provider_name=self.name,
                query=domain,
                available=classify_whois_response(raw),
                details={"raw": raw[:2000]},
            )
        except Exception as e:
            return ProviderResult(
                check_type=CheckType.WHOIS,
                provider_name=self.name,
                query=domain,
                available=Availability.UNKNOWN,
                error=str(e),
            )

    @with_retry(max_retries=2, initial_backoff=1.0)
    async def _query_whois(self, server: str, domain: str) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_whois, server, domain)

    @staticmethod
    def _sync_whois(server: str, domain: str) -> str:
        with socket.create_connection((server, WHOIS_PORT), timeout=10) as sock:
            sock.sendall(f"{domain}\r\n".encode())
            response = b""
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                response += data
            return response.decode("utf-8", errors="replace")
