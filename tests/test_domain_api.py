"""Tests for GoDaddy domain API provider."""

import pytest

from namera.providers.base import CheckType
from namera.providers.domain_api import GoDaddyDomainProvider


@pytest.mark.asyncio
async def test_fallback_dns_when_no_api_key(monkeypatch):
    """Without GODADDY_API_KEY, should fall back to DNS resolution."""
    monkeypatch.delenv("GODADDY_API_KEY", raising=False)

    provider = GoDaddyDomainProvider()
    result = await provider.check("thisisaverylongnamethatdoesnotexist12345", tlds=["com"])

    assert result.check_type == CheckType.DOMAIN
    assert result.provider_name == "domain-api"
    assert len(result.details["domains"]) == 1
    assert "DNS fallback" in result.details["domains"][0].get("note", "")


@pytest.mark.asyncio
async def test_result_structure(monkeypatch):
    """Verify result has expected fields."""
    monkeypatch.delenv("GODADDY_API_KEY", raising=False)

    provider = GoDaddyDomainProvider()
    result = await provider.check("google", tlds=["com"])

    assert result.check_type == CheckType.DOMAIN
    domain_info = result.details["domains"][0]
    assert "domain" in domain_info
    assert "available" in domain_info
    assert domain_info["domain"] == "google.com"
