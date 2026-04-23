"""Tests for social handle availability provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from namera.providers.base import Availability, CheckType
from namera.providers.social import (
    SocialHandleProvider,
    _check_github,
    _check_instagram,
    _check_platform,
    _check_tiktok,
    _check_twitter,
    batch_social_check,
)


def _make_response(status_code: int, text: str = "") -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    return resp


# --- GitHub ---


@pytest.mark.asyncio
async def test_github_head_404_means_available():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.head = AsyncMock(return_value=_make_response(404))
    assert await _check_github(client, "xyznotreal") == Availability.AVAILABLE


@pytest.mark.asyncio
async def test_github_head_200_means_taken():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.head = AsyncMock(return_value=_make_response(200))
    assert await _check_github(client, "torvalds") == Availability.TAKEN


@pytest.mark.asyncio
async def test_github_head_301_means_taken():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.head = AsyncMock(return_value=_make_response(301))
    assert await _check_github(client, "renamed") == Availability.TAKEN


@pytest.mark.asyncio
async def test_github_head_429_means_unknown():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.head = AsyncMock(return_value=_make_response(429))
    assert await _check_github(client, "ratelimited") == Availability.UNKNOWN


# --- Instagram ---


@pytest.mark.asyncio
async def test_instagram_profile_exists():
    body = '<html><head><title>@realuser • Instagram photos and videos</title></head></html>'
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_make_response(200, text=body))
    assert await _check_instagram(client, "realuser") == Availability.TAKEN


@pytest.mark.asyncio
async def test_instagram_profile_not_found():
    body = "<html><head><title>Instagram</title></head></html>"
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_make_response(200, text=body))
    assert await _check_instagram(client, "xqz9v8w7m3k2j") == Availability.AVAILABLE


@pytest.mark.asyncio
async def test_instagram_generic_title_with_whitespace():
    body = "<html><head><title> Instagram </title></head></html>"
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_make_response(200, text=body))
    assert await _check_instagram(client, "xyztest") == Availability.AVAILABLE


@pytest.mark.asyncio
async def test_instagram_rate_limited():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_make_response(429))
    assert await _check_instagram(client, "anyone") == Availability.UNKNOWN


@pytest.mark.asyncio
async def test_instagram_non_200():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_make_response(302))
    assert await _check_instagram(client, "anyone") == Availability.UNKNOWN


@pytest.mark.asyncio
async def test_instagram_no_title_tag():
    body = "<html><head></head><body>login wall</body></html>"
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_make_response(200, text=body))
    assert await _check_instagram(client, "ambiguous") == Availability.UNKNOWN


@pytest.mark.asyncio
async def test_instagram_uses_mobile_user_agent():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_make_response(200, text="<title>Instagram</title>"))
    await _check_instagram(client, "testhandle")
    _, kwargs = client.get.call_args
    assert "iPhone" in kwargs["headers"]["User-Agent"]


# --- Twitter ---


@pytest.mark.asyncio
async def test_twitter_oembed_200_means_taken():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_make_response(200))
    assert await _check_twitter(client, "elonmusk") == Availability.TAKEN


@pytest.mark.asyncio
async def test_twitter_oembed_404_means_available():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_make_response(404))
    assert await _check_twitter(client, "xyznotreal") == Availability.AVAILABLE


@pytest.mark.asyncio
async def test_twitter_oembed_400_means_unknown():
    """400 can be rate limit or suspended account — must NOT report as available."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_make_response(400))
    assert await _check_twitter(client, "suspended") == Availability.UNKNOWN


# --- TikTok ---


@pytest.mark.asyncio
async def test_tiktok_oembed_200_means_taken():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_make_response(200))
    assert await _check_tiktok(client, "tiktok") == Availability.TAKEN


@pytest.mark.asyncio
async def test_tiktok_oembed_404_means_available():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_make_response(404))
    assert await _check_tiktok(client, "xyznotreal") == Availability.AVAILABLE


@pytest.mark.asyncio
async def test_tiktok_oembed_400_means_unknown():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_make_response(400))
    assert await _check_tiktok(client, "ratelimited") == Availability.UNKNOWN


# --- _check_platform dispatch ---


@pytest.mark.asyncio
async def test_check_platform_dispatches_to_github():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.head = AsyncMock(return_value=_make_response(404))
    result = await _check_platform(client, "github", "testhandle")
    assert result == Availability.AVAILABLE


@pytest.mark.asyncio
async def test_check_platform_unknown_platform():
    client = AsyncMock(spec=httpx.AsyncClient)
    result = await _check_platform(client, "myspace", "testhandle")
    assert result == Availability.UNKNOWN


@pytest.mark.asyncio
async def test_check_platform_http_error_returns_unknown():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.head = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
    result = await _check_platform(client, "github", "testhandle")
    assert result == Availability.UNKNOWN


# --- SocialHandleProvider integration ---


@pytest.mark.asyncio
async def test_all_available_means_overall_available():
    async def route_head(url, **kwargs):
        return _make_response(404)

    async def route_get(url, **kwargs):
        if "instagram" in url:
            return _make_response(200, text="<title>Instagram</title>")
        return _make_response(404)

    client = AsyncMock(spec=httpx.AsyncClient)
    client.head = AsyncMock(side_effect=route_head)
    client.get = AsyncMock(side_effect=route_get)

    provider = SocialHandleProvider()
    result = await provider.check("freshname", _http_client=client)

    assert result.available == Availability.AVAILABLE
    assert result.check_type == CheckType.SOCIAL
    for status in result.details["platforms"].values():
        assert status == "available"


@pytest.mark.asyncio
async def test_all_taken_means_overall_taken():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.head = AsyncMock(return_value=_make_response(200))
    client.get = AsyncMock(return_value=_make_response(200, text="<title>@user</title>"))

    provider = SocialHandleProvider()
    result = await provider.check("takenname", _http_client=client)

    assert result.available == Availability.TAKEN


@pytest.mark.asyncio
async def test_mixed_results_means_partial():
    async def route_head(url, **kwargs):
        if "github" in url:
            return _make_response(404)
        return _make_response(200)

    async def route_get(url, **kwargs):
        if "oembed" in url:
            return _make_response(404)
        return _make_response(200, text="<title>@user</title>")

    client = AsyncMock(spec=httpx.AsyncClient)
    client.head = AsyncMock(side_effect=route_head)
    client.get = AsyncMock(side_effect=route_get)

    provider = SocialHandleProvider()
    result = await provider.check("mixedname", _http_client=client)

    assert result.available == Availability.PARTIAL


@pytest.mark.asyncio
async def test_exception_on_one_platform_others_survive():
    async def route_head(url, **kwargs):
        if "github" in url:
            raise httpx.ConnectError("github down")
        return _make_response(200)

    client = AsyncMock(spec=httpx.AsyncClient)
    client.head = AsyncMock(side_effect=route_head)
    client.get = AsyncMock(return_value=_make_response(200, text="<title>@u</title>"))

    provider = SocialHandleProvider()
    result = await provider.check("testname", _http_client=client)

    platforms = result.details["platforms"]
    assert platforms["github"] == "unknown"
    assert "twitter" in platforms


@pytest.mark.asyncio
async def test_platform_filtering():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.head = AsyncMock(return_value=_make_response(404))

    provider = SocialHandleProvider()
    result = await provider.check(
        "testname", _http_client=client, social_platforms=["github"]
    )

    assert list(result.details["platforms"].keys()) == ["github"]


@pytest.mark.asyncio
async def test_no_duplicate_platform_availability_key():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.head = AsyncMock(return_value=_make_response(404))
    client.get = AsyncMock(return_value=_make_response(404))

    provider = SocialHandleProvider()
    result = await provider.check("freshname", _http_client=client)

    assert "platform_availability" not in result.details
    assert "platforms" in result.details


# --- batch_social_check ---


@pytest.mark.asyncio
async def test_batch_returns_results_for_all_names():
    async def route_head(url, **kwargs):
        return _make_response(404)

    async def route_get(url, **kwargs):
        return _make_response(404)

    with pytest.MonkeyPatch.context() as mp:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.head = AsyncMock(side_effect=route_head)
        mock_client.get = AsyncMock(side_effect=route_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mp.setattr(
            "namera.providers.social._shared_client", lambda: mock_client
        )

        results = await batch_social_check(["alpha", "beta", "gamma"])

    assert len(results) == 3
    assert all(r.check_type == CheckType.SOCIAL for r in results)
