"""Tests for the Supabase trademark providers (Edge Function API)."""

from __future__ import annotations

import re

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
    """Point at a deterministic test URL."""
    import namera.providers.trademark_supabase as mod

    original = mod.TRADEMARK_API_URL
    mod.TRADEMARK_API_URL = TEST_ENDPOINT
    try:
        yield
    finally:
        mod.TRADEMARK_API_URL = original


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
        assert result.candidate_name == "xyznonexistent"

    @pytest.mark.asyncio
    async def test_unknown_on_network_error(self, trademark_provider, monkeypatch):
        async def fail(*args, **kwargs):
            raise httpx.ConnectError("Connection refused")

        monkeypatch.setattr("namera.providers.trademark_supabase._post_json", fail)

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
    async def test_batch_trademark_check_uses_durable_cache(
        self,
        tmp_path,
        monkeypatch,
        httpx_mock,
    ):
        from namera.cache import ResultCache
        from namera.providers.trademark_supabase import batch_trademark_check

        cache = ResultCache(db_path=tmp_path / "cache.db")
        monkeypatch.setattr("namera.providers.trademark_supabase.get_cache", lambda: cache)
        httpx_mock.add_response(
            url=TM_URL,
            json={
                "results": {
                    "acme": {"exact": {"matches": [], "count": 0, "trademarked": False}},
                },
            },
        )

        first = await batch_trademark_check(["acme"], mode="exact")
        assert first[0].available == Availability.AVAILABLE
        assert len(httpx_mock.get_requests()) == 1

        second = await batch_trademark_check(["acme"], mode="exact")
        assert second[0].available == Availability.AVAILABLE
        assert len(httpx_mock.get_requests()) == 1
        cache.close()

    @pytest.mark.asyncio
    async def test_unknown_on_error(self, similarity_provider, monkeypatch):
        async def fail(*args, **kwargs):
            raise httpx.ConnectError("timeout")

        monkeypatch.setattr("namera.providers.trademark_supabase._post_json", fail)

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
    def test_get_trademark_risk_names(self):
        from namera.filters import get_trademark_risk_names

        results = [
            ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="uspto",
                query="apple",
                candidate_name="apple",
                available=Availability.TAKEN,
                details={},
            ),
            ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="uspto",
                query="banana",
                candidate_name="banana",
                available=Availability.AVAILABLE,
                details={},
            ),
        ]

        risky = get_trademark_risk_names(results)
        assert risky == ["apple"]
