from __future__ import annotations

import asyncio
import socket

from namera.providers.base import Availability, CheckType, Provider, ProviderResult
from namera.retry import with_retry

WHOIS_PORT = 43


class WhoisProvider(Provider):
    """WHOIS lookup via raw socket connection (no API key needed)."""

    name = "whois"
    check_type = CheckType.WHOIS

    WHOIS_SERVERS = {
        "com": "whois.verisign-grs.com",
        "net": "whois.verisign-grs.com",
        "org": "whois.pir.org",
        "io": "whois.nic.io",
        "dev": "whois.nic.google",
    }

    async def check(self, query: str, **kwargs) -> ProviderResult:
        domain = query if "." in query else f"{query}.com"
        tld = domain.rsplit(".", 1)[-1]
        server = self.WHOIS_SERVERS.get(tld)

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
            taken = "Domain Name:" in raw or "domain:" in raw.lower()
            return ProviderResult(
                check_type=CheckType.WHOIS,
                provider_name=self.name,
                query=domain,
                available=Availability.TAKEN if taken else Availability.AVAILABLE,
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
        loop = asyncio.get_event_loop()
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
