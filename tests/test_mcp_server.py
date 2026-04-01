"""Tests for the Namera MCP server tools."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys

import pytest

from namera.providers.base import Availability, CheckType, ProviderResult
from namera.scoring.models import RankedName, Signal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_results(name: str, error: str | None = None) -> list[ProviderResult]:
    """Build a minimal set of provider results for a single name."""
    avail = Availability.UNKNOWN if error else Availability.AVAILABLE
    return [
        ProviderResult(
            check_type=CheckType.DOMAIN,
            provider_name="rdap",
            query=name,
            candidate_name=name,
            available=avail,
            details={"domains": [{"domain": f"{name}.com", "available": "available"}]},
            error=error,
        ),
        ProviderResult(
            check_type=CheckType.TRADEMARK,
            provider_name="uspto",
            query=name,
            candidate_name=name,
            available=avail,
            details={"matches": [], "match_count": 0},
            error=error,
        ),
    ]


def _make_ranked(name: str, score: float = 0.75) -> RankedName:
    """Build a minimal RankedName for testing."""
    return RankedName(
        name=name,
        composite_score=score,
        signals={
            "domain_com": Signal(name="domain_com", value=1.0, raw=None, source="dns"),
            "trademark": Signal(name="trademark", value=1.0, raw=None, source="trademark"),
        },
    )


# ---------------------------------------------------------------------------
# check_name tool tests
# ---------------------------------------------------------------------------


class TestCheckName:
    @pytest.mark.asyncio
    async def test_happy_path(self, monkeypatch):
        """check_name returns results for a valid name."""
        from namera.mcp_server import check_name

        results = _make_results("voxly")

        async def mock_check_single(name, check_types, **kwargs):
            return results

        monkeypatch.setattr("namera.mcp_server.check_single", mock_check_single)
        monkeypatch.setattr("namera.providers.register_all", lambda: None)

        response = await check_name("voxly")
        parsed = json.loads(response)

        assert parsed["name"] == "voxly"
        assert len(parsed["results"]) == 2
        assert "warnings" not in parsed

    @pytest.mark.asyncio
    async def test_partial_failure(self, monkeypatch):
        """When some providers error, results include warnings."""
        from namera.mcp_server import check_name

        results = [
            ProviderResult(
                check_type=CheckType.DOMAIN,
                provider_name="rdap",
                query="voxly",
                candidate_name="voxly",
                available=Availability.AVAILABLE,
                details={},
            ),
            ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="uspto",
                query="voxly",
                candidate_name="voxly",
                available=Availability.UNKNOWN,
                error="Timed out after 15s",
            ),
        ]

        async def mock_check_single(name, check_types, **kwargs):
            return results

        monkeypatch.setattr("namera.mcp_server.check_single", mock_check_single)
        monkeypatch.setattr("namera.providers.register_all", lambda: None)

        response = await check_name("voxly")
        parsed = json.loads(response)

        assert len(parsed["results"]) == 2
        assert len(parsed["warnings"]) == 1
        assert parsed["warnings"][0]["provider"] == "uspto"
        assert parsed["warnings"][0]["recoverable"] is True

    @pytest.mark.asyncio
    async def test_all_providers_fail(self, monkeypatch):
        """When all providers error, all results have warnings."""
        from namera.mcp_server import check_name

        results = _make_results("voxly", error="Connection refused")

        async def mock_check_single(name, check_types, **kwargs):
            return results

        monkeypatch.setattr("namera.mcp_server.check_single", mock_check_single)
        monkeypatch.setattr("namera.providers.register_all", lambda: None)

        response = await check_name("voxly")
        parsed = json.loads(response)

        assert len(parsed["warnings"]) == 2

    @pytest.mark.asyncio
    async def test_invalid_input_empty_name(self, monkeypatch):
        """Empty name returns an error."""
        from namera.mcp_server import check_name

        monkeypatch.setattr("namera.providers.register_all", lambda: None)

        response = await check_name("")
        parsed = json.loads(response)

        assert "error" in parsed
        assert parsed["results"] == []

    @pytest.mark.asyncio
    async def test_timeout_in_provider(self, monkeypatch):
        """Provider timeout produces warning with recoverable=True."""
        from namera.mcp_server import check_name

        results = [
            ProviderResult(
                check_type=CheckType.DOMAIN,
                provider_name="rdap",
                query="voxly",
                candidate_name="voxly",
                available=Availability.UNKNOWN,
                error="Timed out after 15s",
            ),
        ]

        async def mock_check_single(name, check_types, **kwargs):
            return results

        monkeypatch.setattr("namera.mcp_server.check_single", mock_check_single)
        monkeypatch.setattr("namera.providers.register_all", lambda: None)

        response = await check_name("voxly")
        parsed = json.loads(response)

        assert parsed["warnings"][0]["recoverable"] is True


# ---------------------------------------------------------------------------
# find_names tool tests
# ---------------------------------------------------------------------------


class TestFindNames:
    @pytest.mark.asyncio
    async def test_happy_path(self, monkeypatch):
        """find_names returns ranked results for valid context."""
        from namera.mcp_server import find_names

        results = _make_results("voxly")
        ranked = [_make_ranked("voxly")]

        async def mock_check_and_rank(ctx, **kwargs):
            return results, ranked

        monkeypatch.setattr("namera.mcp_server.check_and_rank", mock_check_and_rank)

        context = json.dumps({
            "name_candidates": ["voxly"],
            "niche": "tech",
            "preferred_tlds": ["com"],
        })
        response = await find_names(context)
        parsed = json.loads(response)

        assert "ranked" in parsed
        assert "summary" in parsed
        assert len(parsed["ranked"]) == 1
        assert parsed["ranked"][0]["name"] == "voxly"

    @pytest.mark.asyncio
    async def test_partial_failure(self, monkeypatch):
        """Partial provider failure still returns ranked results."""
        from namera.mcp_server import find_names

        results = _make_results("voxly") + [
            ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="uspto",
                query="voxly",
                candidate_name="voxly",
                available=Availability.UNKNOWN,
                error="upstream_error",
            ),
        ]
        ranked = [_make_ranked("voxly", score=0.5)]

        async def mock_check_and_rank(ctx, **kwargs):
            return results, ranked

        monkeypatch.setattr("namera.mcp_server.check_and_rank", mock_check_and_rank)

        context = json.dumps({
            "name_candidates": ["voxly"],
            "preferred_tlds": ["com"],
        })
        response = await find_names(context)
        parsed = json.loads(response)

        assert "ranked" in parsed
        assert len(parsed["ranked"]) >= 1

    @pytest.mark.asyncio
    async def test_empty_candidates_error(self):
        """No candidates or keywords returns error."""
        from namera.mcp_server import find_names

        context = json.dumps({"niche": "tech"})
        response = await find_names(context)
        parsed = json.loads(response)

        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        """Invalid JSON context returns error."""
        from namera.mcp_server import find_names

        response = await find_names("{bad json")
        parsed = json.loads(response)

        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_scoring_profile(self, monkeypatch):
        """Custom scoring profile is applied."""
        from namera.mcp_server import find_names

        captured_ctx = {}
        results = _make_results("voxly")
        ranked = [_make_ranked("voxly")]

        async def mock_check_and_rank(ctx, **kwargs):
            captured_ctx["profile"] = ctx.scoring_profile
            return results, ranked

        monkeypatch.setattr("namera.mcp_server.check_and_rank", mock_check_and_rank)

        context = json.dumps({
            "name_candidates": ["voxly"],
            "scoring_profile": "fintech",
            "preferred_tlds": ["com"],
        })
        response = await find_names(context)
        parsed = json.loads(response)

        assert "ranked" in parsed
        assert captured_ctx["profile"] == "fintech"


# ---------------------------------------------------------------------------
# Runner _check() consolidation regression
# ---------------------------------------------------------------------------


class TestRunnerConsolidation:
    """Verify the consolidated _run_single_check produces same behavior."""

    @pytest.mark.asyncio
    async def test_cache_hit_skips_provider(self, monkeypatch):
        """When cache has a result, provider.check() is not called."""
        from namera.providers.base import Provider
        from namera.runner import _run_single_check

        call_count = 0

        class _CachedProvider(Provider):
            name = "test-cached"
            check_type = CheckType.DOMAIN

            async def check(self, query, **kwargs):
                nonlocal call_count
                call_count += 1
                return ProviderResult(
                    check_type=self.check_type,
                    provider_name=self.name,
                    query=query,
                    available=Availability.AVAILABLE,
                )

        cached_result = ProviderResult(
            check_type=CheckType.DOMAIN,
            provider_name="test-cached",
            query="voxly",
            available=Availability.AVAILABLE,
        )

        monkeypatch.setattr(
            "namera.runner.get_cache",
            lambda: type("FakeCache", (), {
                "get": lambda self, p, q, k: cached_result,
                "set": lambda self, r, k: None,
            })(),
        )

        sem = asyncio.Semaphore(5)
        result = await _run_single_check(_CachedProvider, "voxly", {}, sem)

        assert result.available == Availability.AVAILABLE
        assert call_count == 0  # provider never called

    @pytest.mark.asyncio
    async def test_timeout_returns_unknown(self, monkeypatch):
        """Timeout produces UNKNOWN result, not an exception."""
        from namera.providers.base import Provider
        from namera.runner import _run_single_check

        class _SlowProvider(Provider):
            name = "test-slow-consolidated"
            check_type = CheckType.DOMAIN

            async def check(self, query, **kwargs):
                await asyncio.sleep(10)
                return ProviderResult(
                    check_type=self.check_type,
                    provider_name=self.name,
                    query=query,
                    available=Availability.AVAILABLE,
                )

        monkeypatch.setattr(
            "namera.runner.get_cache",
            lambda: type("FakeCache", (), {
                "get": lambda self, p, q, k: None,
                "set": lambda self, r, k: None,
            })(),
        )

        sem = asyncio.Semaphore(5)
        result = await _run_single_check(_SlowProvider, "voxly", {}, sem, timeout=0.01)

        assert result.available == Availability.UNKNOWN
        assert "timed out" in result.error.lower()


# ---------------------------------------------------------------------------
# stdout contamination guard
# ---------------------------------------------------------------------------


class TestStdoutContamination:
    def test_mcp_server_import_no_stdout(self):
        """Importing the MCP server module must not write to stdout."""
        result = subprocess.run(
            [sys.executable, "-c", "import namera.mcp_server"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.stdout == "", (
            f"MCP server import wrote to stdout: {result.stdout!r}"
        )
