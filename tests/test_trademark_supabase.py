"""Tests for the Supabase trademark providers (Edge Function API)."""

from __future__ import annotations

import re
from unittest.mock import patch

import httpx
import pytest

from namera.providers.base import Availability, CheckType, ProviderResult
from namera.providers.trademark_supabase import (
    SupabaseSimilarityProvider,
    SupabaseTrademarkProvider,
)

TM_URL = re.compile(r".*/functions/v1/trademark-check")
TEST_ENDPOINT = "https://test.supabase.co/functions/v1/trademark-check"


@pytest.fixture(autouse=True)
def _mock_api_env():
    """Point at test URL and reset shared client between tests."""
    import namera.providers.trademark_supabase as mod

    mod._client = None
    with patch.object(mod, "TRADEMARK_API_URL", TEST_ENDPOINT):
        yield
    if mod._client and not mod._client.is_closed:
        import asyncio

        try:
            asyncio.get_event_loop().run_until_complete(mod._client.aclose())
        except Exception:
            pass
    mod._client = None


@pytest.fixture
def trademark_provider():
    return SupabaseTrademarkProvider()


@pytest.fixture
def similarity_provider():
    return SupabaseSimilarityProvider()


# --- SupabaseTrademarkProvider ---


class TestSupabaseTrademarkProvider:
    """Tests for exact trademark match via Edge Function."""

    @pytest.mark.asyncio
    async def test_taken_when_matches_found(self, trademark_provider, httpx_mock):
        httpx_mock.add_response(
            url=TM_URL,
            json={
                "query": "apple",
                "exact": {
                    "matches": [
                        {
                            "serial_number": "97000001",
                            "mark_text": "APPLE",
                            "status": "live",
                            "owner_name": "Apple Inc.",
                        }
                    ],
                    "count": 1,
                    "trademarked": True,
                },
            },
        )

        result = await trademark_provider.check("apple")
        assert result.available == Availability.TAKEN
        assert result.check_type == CheckType.TRADEMARK
        assert result.provider_name == "uspto"
        assert result.details["match_count"] == 1

    @pytest.mark.asyncio
    async def test_available_when_no_matches(self, trademark_provider, httpx_mock):
        httpx_mock.add_response(
            url=TM_URL,
            json={
                "query": "xyznonexistent",
                "exact": {"matches": [], "count": 0, "trademarked": False},
            },
        )

        result = await trademark_provider.check("xyznonexistent")
        assert result.available == Availability.AVAILABLE
        assert result.details["match_count"] == 0

    @pytest.mark.asyncio
    async def test_unknown_on_network_error(self, trademark_provider, httpx_mock):
        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        result = await trademark_provider.check("test")
        assert result.available == Availability.UNKNOWN
        assert "failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_unknown_on_http_error(self, trademark_provider, httpx_mock):
        httpx_mock.add_response(url=TM_URL, status_code=500)

        result = await trademark_provider.check("test")
        assert result.available == Availability.UNKNOWN
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_source_in_details(self, trademark_provider, httpx_mock):
        httpx_mock.add_response(
            url=TM_URL,
            json={
                "query": "test",
                "exact": {"matches": [], "count": 0, "trademarked": False},
            },
        )

        result = await trademark_provider.check("test")
        assert result.details["source"] == "uspto"

    @pytest.mark.asyncio
    async def test_provider_auto_registered(self):
        from namera.providers.base import registry

        providers = registry.list_by_type(CheckType.TRADEMARK)
        provider_names = [p.name for p in providers]
        assert "uspto" in provider_names


# --- SupabaseSimilarityProvider ---


class TestSupabaseSimilarityProvider:
    """Tests for fuzzy trademark similarity search."""

    @pytest.mark.asyncio
    async def test_taken_when_high_similarity(self, similarity_provider, httpx_mock):
        httpx_mock.add_response(
            url=TM_URL,
            json={
                "query": "appl",
                "similarity": {
                    "matches": [
                        {"mark_text": "APPLE", "similarity_score": 0.98},
                    ],
                    "count": 1,
                    "max_score": 0.98,
                },
            },
        )

        result = await similarity_provider.check("appl")
        assert result.available == Availability.TAKEN
        assert result.details["max_similarity"] == 0.98

    @pytest.mark.asyncio
    async def test_unknown_when_moderate_similarity(
        self, similarity_provider, httpx_mock,
    ):
        httpx_mock.add_response(
            url=TM_URL,
            json={
                "query": "apple",
                "similarity": {
                    "matches": [
                        {"mark_text": "APPLEX", "similarity_score": 0.75},
                    ],
                    "count": 1,
                    "max_score": 0.75,
                },
            },
        )

        result = await similarity_provider.check("apple")
        assert result.available == Availability.UNKNOWN

    @pytest.mark.asyncio
    async def test_available_when_no_similar_marks(
        self, similarity_provider, httpx_mock,
    ):
        httpx_mock.add_response(
            url=TM_URL,
            json={
                "query": "xyzunique",
                "similarity": {"matches": [], "count": 0, "max_score": 0},
            },
        )

        result = await similarity_provider.check("xyzunique")
        assert result.available == Availability.AVAILABLE
        assert result.details["max_similarity"] == 0.0

    @pytest.mark.asyncio
    async def test_unknown_on_error(self, similarity_provider, httpx_mock):
        httpx_mock.add_exception(httpx.ConnectError("timeout"))

        result = await similarity_provider.check("test")
        assert result.available == Availability.UNKNOWN

    @pytest.mark.asyncio
    async def test_similarity_provider_registered(self):
        from namera.providers.base import registry

        providers = registry.list_by_type(CheckType.TRADEMARK)
        provider_names = [p.name for p in providers]
        assert "trademark-similarity" in provider_names


# --- Trademark risk filtering ---


class TestTrademarkRiskFiltering:
    """Tests for the trademark risk flagging in filters.py."""

    def test_flag_trademark_risks_marks_risky_names(self):
        from namera.filters import flag_trademark_risks

        results = [
            ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="uspto",
                query="apple",
                available=Availability.TAKEN,
                details={"match_count": 1},
            ),
            ProviderResult(
                check_type=CheckType.DOMAIN,
                provider_name="dns",
                query="apple",
                available=Availability.AVAILABLE,
                details={
                    "domains": [
                        {"domain": "apple.dev", "available": "available"},
                    ],
                },
            ),
            ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="uspto",
                query="xyzclean",
                available=Availability.AVAILABLE,
                details={"match_count": 0},
            ),
        ]

        flagged = flag_trademark_risks(results)
        assert flagged[0].details.get("trademark_risk") is True
        assert flagged[1].details.get("trademark_risk") is True
        assert flagged[2].details.get("trademark_risk") is None

    def test_get_trademark_risk_names(self):
        from namera.filters import get_trademark_risk_names

        results = [
            ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="uspto",
                query="apple",
                available=Availability.TAKEN,
                details={},
            ),
            ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="uspto",
                query="banana",
                available=Availability.AVAILABLE,
                details={},
            ),
        ]

        risky = get_trademark_risk_names(results)
        assert risky == ["apple"]
