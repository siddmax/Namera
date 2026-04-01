"""Tests for GoDaddy domain API provider."""

import socket

import pytest

from namera.providers.base import CheckType
from namera.providers.domain_api import GoDaddyDomainProvider


@pytest.mark.asyncio
async def test_fallback_dns_when_no_api_key(monkeypatch):
    """Without GODADDY_API_KEY, should fall back to DNS resolution."""
    monkeypatch.delenv("GODADDY_API_KEY", raising=False)
    monkeypatch.setattr(
        socket,
        "gethostbyname",
        lambda domain: (_ for _ in ()).throw(socket.gaierror(socket.EAI_NONAME, "missing")),
    )

    provider = GoDaddyDomainProvider()
    result = await provider.check("thisisaverylongnamethatdoesnotexist12345", tlds=["com"])

    assert result.check_type == CheckType.DOMAIN
    assert result.provider_name == "domain-api"
    assert len(result.details["domains"]) == 1
    assert result.details["domains"][0]["available"] == "available"
    assert "DNS fallback" in result.details["domains"][0].get("note", "")


@pytest.mark.asyncio
async def test_api_result_structure_uses_string_status(monkeypatch, httpx_mock):
    monkeypatch.setenv("GODADDY_API_KEY", "key")
    monkeypatch.setenv("GODADDY_API_SECRET", "secret")
    httpx_mock.add_response(
        url="https://api.ote-godaddy.com/v1/domains/available?domain=google.com",
        json={"available": True, "price": 12000000, "currency": "USD", "definitive": True},
    )

    provider = GoDaddyDomainProvider()
    result = await provider.check("google", tlds=["com"])

    assert result.check_type == CheckType.DOMAIN
    domain_info = result.details["domains"][0]
    assert domain_info["domain"] == "google.com"
    assert domain_info["available"] == "available"
    assert domain_info["price"] == 12.0
