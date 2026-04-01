from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from namera.providers.base import Availability, CheckType, registry
from namera.providers.rdap import RdapProvider


@pytest.fixture(autouse=True)
def _reset_cache():
    """Reset the module-level RDAP cache before each test."""
    import namera.providers.rdap as rdap_mod

    rdap_mod._cache_loaded = False
    rdap_mod._rdap_server_cache.clear()
    yield
    rdap_mod._cache_loaded = False
    rdap_mod._rdap_server_cache.clear()


def test_rdap_provider_registered():
    """RdapProvider should be auto-registered in the provider registry."""
    provider_cls = registry.get("rdap")
    assert provider_cls is not None
    assert provider_cls is RdapProvider


def test_rdap_provider_attributes():
    assert RdapProvider.name == "rdap"
    assert RdapProvider.check_type == CheckType.DOMAIN


def _make_response(status_code: int, json_data=None, text: str = ""):
    """Build a fake httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
        resp.raise_for_status = MagicMock()
    return resp


@pytest.mark.asyncio
async def test_rdap_404_means_available():
    """RDAP 404 response should mark the domain as available."""
    bootstrap = _make_response(200, json_data={
        "services": [[["com"], ["https://rdap.example.com"]]]
    })
    domain_resp = _make_response(404, text="")

    async def fake_get(url, **kwargs):
        if "dns.json" in url:
            return bootstrap
        return domain_resp

    with patch("namera.providers.rdap.httpx.AsyncClient") as mock_client_cls:
        client_instance = AsyncMock()
        client_instance.get = AsyncMock(side_effect=fake_get)
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = client_instance

        provider = RdapProvider()
        result = await provider.check("testname", tlds=["com"])

    assert result.available == Availability.AVAILABLE
    assert result.details["domains"][0]["available"] == "available"
    assert result.details["domains"][0]["method"] == "rdap"


@pytest.mark.asyncio
async def test_rdap_200_means_taken():
    """RDAP 200 with valid data should mark the domain as taken."""
    bootstrap = _make_response(200, json_data={
        "services": [[["com"], ["https://rdap.example.com"]]]
    })
    domain_resp = _make_response(200, text='{"objectClassName": "domain"}')

    async def fake_get(url, **kwargs):
        if "dns.json" in url:
            return bootstrap
        return domain_resp

    with patch("namera.providers.rdap.httpx.AsyncClient") as mock_client_cls:
        client_instance = AsyncMock()
        client_instance.get = AsyncMock(side_effect=fake_get)
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = client_instance

        provider = RdapProvider()
        result = await provider.check("google", tlds=["com"])

    assert result.available == Availability.TAKEN
    assert result.details["domains"][0]["available"] == "taken"
    assert result.details["domains"][0]["method"] == "rdap"


@pytest.mark.asyncio
async def test_rdap_object_does_not_exist_means_available():
    """RDAP 200 with 'object does not exist' body should mark as available."""
    bootstrap = _make_response(200, json_data={
        "services": [[["com"], ["https://rdap.example.com"]]]
    })
    domain_resp = _make_response(
        200, text='{"errorCode": 404, "title": "Object does not exist"}'
    )

    async def fake_get(url, **kwargs):
        if "dns.json" in url:
            return bootstrap
        return domain_resp

    with patch("namera.providers.rdap.httpx.AsyncClient") as mock_client_cls:
        client_instance = AsyncMock()
        client_instance.get = AsyncMock(side_effect=fake_get)
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = client_instance

        provider = RdapProvider()
        result = await provider.check("xyznotreal123", tlds=["com"])

    assert result.available == Availability.AVAILABLE
    assert result.details["domains"][0]["method"] == "rdap"


@pytest.mark.asyncio
async def test_fallback_to_dns_when_no_rdap_server():
    """When RDAP bootstrap has no server for TLD, should fall back to DNS."""
    bootstrap = _make_response(200, json_data={"services": []})

    async def fake_get(url, **kwargs):
        if "dns.json" in url:
            return bootstrap
        raise httpx.ConnectError("should not be called")

    with (
        patch("namera.providers.rdap.httpx.AsyncClient") as mock_client_cls,
        patch(
            "namera.providers.rdap.DnsLookupUtil.resolve",
            new_callable=AsyncMock,
            return_value=Availability.AVAILABLE,
        ) as mock_dns,
    ):
        client_instance = AsyncMock()
        client_instance.get = AsyncMock(side_effect=fake_get)
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = client_instance

        provider = RdapProvider()
        result = await provider.check("fallbacktest", tlds=["com"])

    mock_dns.assert_called_once_with("fallbacktest.com")
    assert result.details["domains"][0]["method"] == "dns"
    assert result.details["domains"][0]["available"] == "available"


@pytest.mark.asyncio
async def test_fallback_to_whois_when_rdap_and_dns_fail():
    """When RDAP and DNS both fail, should fall back to WHOIS."""
    bootstrap = _make_response(200, json_data={"services": []})

    async def fake_get(url, **kwargs):
        if "dns.json" in url:
            return bootstrap
        raise httpx.ConnectError("no rdap")

    with (
        patch("namera.providers.rdap.httpx.AsyncClient") as mock_client_cls,
        patch(
            "namera.providers.rdap.DnsLookupUtil.resolve",
            new_callable=AsyncMock,
            side_effect=Exception("dns broken"),
        ),
        patch(
            "namera.providers.rdap._whois_fallback",
            new_callable=AsyncMock,
            return_value=Availability.TAKEN,
        ) as mock_whois,
    ):
        client_instance = AsyncMock()
        client_instance.get = AsyncMock(side_effect=fake_get)
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = client_instance

        provider = RdapProvider()
        result = await provider.check("whoistest", tlds=["com"])

    mock_whois.assert_called_once_with("whoistest.com")
    assert result.details["domains"][0]["method"] == "whois"
    assert result.details["domains"][0]["available"] == "taken"


@pytest.mark.asyncio
async def test_rdap_timeout_falls_back_to_dns():
    """RDAP timeout should fall back to DNS resolution."""
    import namera.providers.rdap as rdap_mod

    # Pre-populate cache to skip bootstrap fetch
    rdap_mod._cache_loaded = True
    rdap_mod._rdap_server_cache["com"] = "https://rdap.example.com"

    async def fake_get(url, **kwargs):
        raise httpx.TimeoutException("timed out")

    with (
        patch("namera.providers.rdap.httpx.AsyncClient") as mock_client_cls,
        patch(
            "namera.providers.rdap.DnsLookupUtil.resolve",
            new_callable=AsyncMock,
            return_value=Availability.TAKEN,
        ) as mock_dns,
    ):
        client_instance = AsyncMock()
        client_instance.get = AsyncMock(side_effect=fake_get)
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = client_instance

        provider = RdapProvider()
        result = await provider.check("timeouttest", tlds=["com"])

    mock_dns.assert_called_once_with("timeouttest.com")
    assert result.details["domains"][0]["method"] == "dns"


@pytest.mark.asyncio
async def test_multiple_tlds():
    """Provider should check all requested TLDs."""
    bootstrap = _make_response(200, json_data={
        "services": [
            [["com"], ["https://rdap.verisign.com"]],
            [["net"], ["https://rdap.verisign.com"]],
        ]
    })
    domain_taken = _make_response(200, text='{"objectClassName": "domain"}')
    domain_avail = _make_response(404, text="")

    async def fake_get(url, **kwargs):
        if "dns.json" in url:
            return bootstrap
        if "example.com" in url:
            return domain_taken
        return domain_avail

    with patch("namera.providers.rdap.httpx.AsyncClient") as mock_client_cls:
        client_instance = AsyncMock()
        client_instance.get = AsyncMock(side_effect=fake_get)
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = client_instance

        provider = RdapProvider()
        result = await provider.check("example", tlds=["com", "net"])

    assert len(result.details["domains"]) == 2
    domains = {d["domain"]: d for d in result.details["domains"]}
    assert domains["example.com"]["available"] == "taken"
    assert domains["example.net"]["available"] == "available"
    assert result.available == Availability.AVAILABLE
