"""Shared WHOIS server mapping — single source of truth for all providers."""

from __future__ import annotations

WHOIS_SERVERS: dict[str, str] = {
    "com": "whois.verisign-grs.com",
    "net": "whois.verisign-grs.com",
    "org": "whois.pir.org",
    "io": "whois.nic.io",
    "dev": "whois.nic.google",
    "ai": "whois.nic.ai",
    "co": "whois.nic.co",
    "app": "whois.nic.google",
    "xyz": "whois.nic.xyz",
    "tech": "whois.nic.tech",
    "me": "whois.nic.me",
    "cc": "ccwhois.verisign-grs.com",
    "tv": "tvwhois.verisign-grs.com",
}
