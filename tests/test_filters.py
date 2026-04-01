from __future__ import annotations

from namera.filters import (
    filter_available_only,
    filter_trademarked_results,
    get_trademark_risk_names,
)
from namera.providers.base import Availability, CheckType, ProviderResult


def _make_domain_result(
    query: str = "example",
    domains: list[dict] | None = None,
) -> ProviderResult:
    """Helper to build a domain ProviderResult with nested sub-results."""
    if domains is None:
        domains = []
    return ProviderResult(
        check_type=CheckType.DOMAIN,
        provider_name="dns",
        query=query,
        available=Availability.UNKNOWN,
        details={"domains": domains},
    )


def _make_flat_result(
    check_type: CheckType = CheckType.WHOIS,
    available: Availability = Availability.AVAILABLE,
    query: str = "example.com",
) -> ProviderResult:
    """Helper to build a flat (non-domain) ProviderResult."""
    return ProviderResult(
        check_type=check_type,
        provider_name="whois" if check_type == CheckType.WHOIS else "trademark-stub",
        query=query,
        available=available,
        details={},
    )


class TestFilterFlatResults:
    """Tests for filtering flat results (whois/trademark type)."""

    def test_available_passes(self):
        results = [_make_flat_result(available=Availability.AVAILABLE)]
        filtered = filter_available_only(results)
        assert len(filtered) == 1
        assert filtered[0].available == Availability.AVAILABLE

    def test_taken_is_excluded(self):
        results = [_make_flat_result(available=Availability.TAKEN)]
        filtered = filter_available_only(results)
        assert len(filtered) == 0

    def test_unknown_is_excluded(self):
        results = [_make_flat_result(available=Availability.UNKNOWN)]
        filtered = filter_available_only(results)
        assert len(filtered) == 0


class TestFilterDomainResults:
    """Tests for filtering domain results with nested sub-results."""

    def test_only_available_domains_pass(self):
        result = _make_domain_result(
            domains=[
                {"domain": "example.com", "available": "available"},
                {"domain": "example.net", "available": "taken"},
                {"domain": "example.org", "available": "available"},
            ]
        )
        filtered = filter_available_only([result])
        assert len(filtered) == 1
        domains = filtered[0].details["domains"]
        assert len(domains) == 2
        assert domains[0]["domain"] == "example.com"
        assert domains[1]["domain"] == "example.org"

    def test_domain_result_dropped_when_no_available(self):
        result = _make_domain_result(
            domains=[
                {"domain": "example.com", "available": "taken"},
                {"domain": "example.net", "available": "taken"},
            ]
        )
        filtered = filter_available_only([result])
        assert len(filtered) == 0

    def test_domain_result_availability_set_to_available(self):
        result = _make_domain_result(
            domains=[
                {"domain": "example.io", "available": "available"},
            ]
        )
        filtered = filter_available_only([result])
        assert len(filtered) == 1
        assert filtered[0].available == Availability.AVAILABLE

    def test_boolean_available_status_is_supported(self):
        result = _make_domain_result(
            domains=[
                {"domain": "example.com", "available": True},
                {"domain": "example.net", "available": False},
            ]
        )
        filtered = filter_available_only([result])
        assert len(filtered) == 1
        assert filtered[0].details["domains"] == [
            {"domain": "example.com", "available": True},
        ]


class TestFilterEmptyInput:
    """Test empty input returns empty output."""

    def test_empty_list(self):
        assert filter_available_only([]) == []


class TestFilterMixedResults:
    """Test mixed results — some available, some taken — correct filtering."""

    def test_mixed_flat_and_domain(self):
        domain_result = _make_domain_result(
            domains=[
                {"domain": "foo.com", "available": "taken"},
                {"domain": "foo.dev", "available": "available"},
            ]
        )
        whois_available = _make_flat_result(
            check_type=CheckType.WHOIS,
            available=Availability.AVAILABLE,
            query="foo.com",
        )
        whois_taken = _make_flat_result(
            check_type=CheckType.WHOIS,
            available=Availability.TAKEN,
            query="foo.net",
        )
        trademark_taken = _make_flat_result(
            check_type=CheckType.TRADEMARK,
            available=Availability.TAKEN,
            query="foo",
        )

        results = [domain_result, whois_available, whois_taken, trademark_taken]
        filtered = filter_available_only(results)

        # Domain result kept with only foo.dev
        assert len(filtered) == 2
        assert filtered[0].check_type == CheckType.DOMAIN
        assert len(filtered[0].details["domains"]) == 1
        assert filtered[0].details["domains"][0]["domain"] == "foo.dev"
        # Whois available kept
        assert filtered[1].check_type == CheckType.WHOIS
        assert filtered[1].available == Availability.AVAILABLE

    def test_original_result_not_mutated(self):
        """Ensure filtering creates new objects and doesn't mutate originals."""
        original = _make_domain_result(
            domains=[
                {"domain": "a.com", "available": "available"},
                {"domain": "a.net", "available": "taken"},
            ]
        )
        original_domain_count = len(original.details["domains"])
        filter_available_only([original])
        assert len(original.details["domains"]) == original_domain_count


class TestTrademarkFiltering:
    def test_get_trademark_risk_names_uses_candidate_identity(self):
        results = [
            ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="uspto",
                query="acme",
                candidate_name="Acme",
                available=Availability.TAKEN,
                details={},
            ),
            ProviderResult(
                check_type=CheckType.WHOIS,
                provider_name="whois",
                query="acme.com",
                candidate_name="Acme",
                available=Availability.AVAILABLE,
                details={},
            ),
        ]

        assert get_trademark_risk_names(results) == ["Acme"]

    def test_filter_trademarked_results_drops_rewritten_queries(self):
        results = [
            ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="uspto",
                query="acme",
                candidate_name="acme",
                available=Availability.TAKEN,
                details={},
            ),
            ProviderResult(
                check_type=CheckType.WHOIS,
                provider_name="whois",
                query="acme.com",
                candidate_name="acme",
                available=Availability.AVAILABLE,
                details={},
            ),
        ]

        assert filter_trademarked_results(results) == []
