"""Shared test fixtures for Namera."""

from __future__ import annotations

import pytest

from namera.providers.base import Availability, CheckType, ProviderResult, registry


@pytest.fixture(autouse=True)
def isolate_registry():
    """Save and restore the provider registry to prevent test pollution."""
    saved = dict(registry._providers)
    yield
    registry._providers = saved


def make_result(
    check_type: CheckType = CheckType.DOMAIN,
    provider_name: str = "test",
    query: str = "example",
    available: Availability = Availability.AVAILABLE,
    candidate_name: str | None = None,
    details: dict | None = None,
    error: str | None = None,
) -> ProviderResult:
    """Factory for creating ProviderResult instances in tests."""
    return ProviderResult(
        check_type=check_type,
        provider_name=provider_name,
        query=query,
        available=available,
        candidate_name=candidate_name,
        details=details or {},
        error=error,
    )


def make_domain_result(
    query: str = "example",
    domains: list[dict] | None = None,
    provider_name: str = "dns",
    candidate_name: str | None = None,
) -> ProviderResult:
    """Factory for domain results with nested domain details."""
    if domains is None:
        domains = [{"domain": f"{query}.com", "available": "available"}]
    return make_result(
        check_type=CheckType.DOMAIN,
        provider_name=provider_name,
        query=query,
        available=Availability.AVAILABLE,
        candidate_name=candidate_name,
        details={"domains": domains},
    )


def make_trademark_result(
    query: str = "example",
    available: Availability = Availability.AVAILABLE,
    provider_name: str = "uspto",
    candidate_name: str | None = None,
    max_similarity: float | None = None,
) -> ProviderResult:
    """Factory for trademark results."""
    details: dict = {}
    if max_similarity is not None:
        details["max_similarity"] = max_similarity
    return make_result(
        check_type=CheckType.TRADEMARK,
        provider_name=provider_name,
        query=query,
        available=available,
        candidate_name=candidate_name,
        details=details,
    )
