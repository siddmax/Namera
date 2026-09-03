from __future__ import annotations

import asyncio
import socket

import httpx

from namera.providers.base import Availability, CheckType, Provider, ProviderResult
from namera.providers.domain import DnsLookupUtil
from namera.providers.whois import classify_whois_response
from namera.providers.whois_servers import WHOIS_SERVERS
from namera.results import summarize_domain_statuses

# IANA RDAP bootstrap URL for DNS registries
_IANA_RDAP_DNS_URL = "https://data.iana.org/rdap/dns.json"

# Class-level cache for RDAP server mapping (TLD -> RDAP base URL)
_rdap_server_cache: dict[str, str] = {}
_cache_attempted = False


async def _load_rdap_servers(client: httpx.AsyncClient) -> None:
    """Fetch the IANA RDAP bootstrap file and populate the TLD -> URL cache."""
    global _cache_attempted
    if _cache_attempted:
        return
    _cache_attempted = True
    try:
        resp = await client.get(_IANA_RDAP_DNS_URL, timeout=5.0)
        resp.raise_for_status()
        data = resp.json()
        for entry in data.get("services", []):
            tlds, urls = entry[0], entry[1]
            if urls:
                base_url = urls[0].rstrip("/")
                for tld in tlds:
                    _rdap_server_cache[tld.lower()] = base_url
    except Exception:
        pass


async def _whois_fallback(domain: str) -> Availability:
    """Raw-socket WHOIS check as last-resort fallback."""
    tld = domain.rsplit(".", 1)[-1].lower()
    server = WHOIS_SERVERS.get(tld)
    if not server:
        return Availability.UNKNOWN

    def _sync_whois() -> str:
        with socket.create_connection((server, 43), timeout=5) as sock:
            sock.sendall(f"{domain}\r\n".encode())
            response = b""
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                response += data
            return response.decode("utf-8", errors="replace")

    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, _sync_whois)
        return classify_whois_response(raw)
    except Exception:
        return Availability.UNKNOWN


class RdapProvider(Provider):
    """Check domain availability via RDAP with DNS and WHOIS fallbacks."""

    name = "rdap"
    check_type = CheckType.DOMAIN

    @classmethod
    def cache_kwargs(cls, kwargs: dict) -> dict:
        return {"tlds": kwargs.get("tlds")}

    async def check(self, query: str, **kwargs) -> ProviderResult:
        tlds = kwargs.get("tlds", ["com", "net", "org", "io", "dev"])
        client = kwargs.get("_http_client")

        if client:
            return await self._check_all_tlds(client, query, tlds)
        async with httpx.AsyncClient() as client:
            return await self._check_all_tlds(client, query, tlds)

    async def _check_all_tlds(
        self, client: httpx.AsyncClient, query: str, tlds: list[str]
    ) -> ProviderResult:
        await _load_rdap_servers(client)

        domains = [
            f"{query}.{tld}" if "." not in query else query for tld in tlds
        ]
        checks = await asyncio.gather(
            *(self._check_domain(client, domain) for domain in domains)
        )
        results = [
            {"domain": domain, "available": avail.value, "method": method}
            for domain, (avail, method) in zip(domains, checks)
        ]

        overall = summarize_domain_statuses(r["available"] for r in results)
        return ProviderResult(
            check_type=CheckType.DOMAIN,
            provider_name=self.name,
            query=query,
            available=overall,
            details={"domains": results},
        )

    @staticmethod
    async def _confirm_available(domain: str) -> tuple[Availability, str]:
        """Second-source an RDAP "not found" before calling a domain free.

        Some registries answer 404 for domains that are registered — the IANA
        bootstrap points at a stale or incomplete RDAP endpoint. Confirm
        against WHOIS when we have a server for the TLD; a WHOIS record wins
        over RDAP's absence of one. Costs a round-trip only on domains that
        already look available.
        """
        tld = domain.rsplit(".", 1)[-1].lower()
        if tld not in WHOIS_SERVERS:
            return Availability.AVAILABLE, "rdap"
        if await _whois_fallback(domain) == Availability.TAKEN:
            return Availability.TAKEN, "whois"
        return Availability.AVAILABLE, "rdap"

    async def _check_domain(
        self, client: httpx.AsyncClient, domain: str
    ) -> tuple[Availability, str]:
        """Try RDAP first, then DNS, then WHOIS. Returns (availability, method)."""
        tld = domain.rsplit(".", 1)[-1].lower()
        rdap_url = _rdap_server_cache.get(tld)

        # --- RDAP attempt ---
        if rdap_url:
            try:
                resp = await client.get(
                    f"{rdap_url}/domain/{domain}", timeout=5.0
                )
                if resp.status_code == 404:
                    return await self._confirm_available(domain)
                if resp.status_code == 200:
                    body = resp.text
                    if "object does not exist" in body.lower():
                        return await self._confirm_available(domain)
                    return Availability.TAKEN, "rdap"
                # Non-200/404 — fall through to DNS
            except Exception:
                pass  # RDAP failed — fall through to DNS

        # --- DNS fallback ---
        # DNS can confirm TAKEN (domain resolves) but cannot confirm AVAILABLE
        # (a registered domain may have no A records). Only trust TAKEN here.
        try:
            dns_result = await DnsLookupUtil.resolve(domain)
            if dns_result == Availability.TAKEN:
                return dns_result, "dns"
        except Exception:
            pass  # DNS failed — fall through to WHOIS

        # --- WHOIS fallback ---
        try:
            whois_result = await _whois_fallback(domain)
            return whois_result, "whois"
        except Exception:
            return Availability.UNKNOWN, "whois"
