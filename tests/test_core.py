"""Tests for the core programmatic API."""

from __future__ import annotations

from namera.core import rank_candidates, resolve_profile
from namera.providers.base import Availability
from tests.conftest import make_domain_result, make_trademark_result


def test_resolve_profile_default():
    profile = resolve_profile()
    assert profile.name == "default"
    assert "domain_com" in profile.weights


def test_resolve_profile_with_overrides():
    profile = resolve_profile("fintech", {"trademark": 0.99})
    assert profile.name == "fintech+overrides"
    assert profile.weights["trademark"] == 0.99
    # Original fintech weights preserved for other signals
    assert profile.weights["domain_com"] == 0.20


def test_resolve_profile_no_overrides():
    profile = resolve_profile("startup-saas", None)
    assert profile.name == "startup-saas"


def test_rank_candidates_basic():
    results = [
        make_domain_result(
            "good",
            domains=[{"domain": "good.com", "available": "available"}],
            candidate_name="good",
        ),
        make_trademark_result("good", Availability.AVAILABLE, candidate_name="good"),
        make_domain_result(
            "bad",
            domains=[{"domain": "bad.com", "available": "taken"}],
            candidate_name="bad",
        ),
        make_trademark_result("bad", Availability.TAKEN, candidate_name="bad"),
    ]

    profile = resolve_profile()
    ranked = rank_candidates(["good", "bad"], results, profile)

    assert len(ranked) == 2
    assert ranked[0].name == "good"
    assert ranked[0].composite_score > ranked[1].composite_score


def test_rank_candidates_empty():
    profile = resolve_profile()
    ranked = rank_candidates(["orphan"], [], profile)
    assert len(ranked) == 1
    assert ranked[0].name == "orphan"


def test_rank_candidates_with_filters():
    results = [
        make_domain_result(
            "nocom",
            domains=[{"domain": "nocom.com", "available": "taken"}],
            candidate_name="nocom",
        ),
    ]
    # startup-saas has hard filter: domain_com >= 0.5
    profile = resolve_profile("startup-saas")
    ranked = rank_candidates(["nocom"], results, profile)
    assert ranked[0].filtered_out is True
