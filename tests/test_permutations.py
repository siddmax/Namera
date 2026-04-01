"""Tests for fallback variation generation (formerly permutations module)."""

from __future__ import annotations

from namera.composer import (
    FALLBACK_VARIATION_PREFIXES,
    FALLBACK_VARIATION_SUFFIXES,
    MAX_FALLBACK_VARIATION_KEYWORDS,
    compose_fallback_variations,
)
from namera.results import candidate_names_without_available_domains
from tests.conftest import make_domain_result


def test_generate_fallback_variations_basic():
    perms = compose_fallback_variations(["voxly"])
    assert "getvoxly" in perms
    assert "tryvoxly" in perms
    assert "voxlyapp" in perms
    assert "voxlyhq" in perms


def test_generate_fallback_variations_count():
    perms = compose_fallback_variations(["test"])
    # base keyword + prefixed variants + suffixed variants
    expected = 1 + len(FALLBACK_VARIATION_PREFIXES) + len(FALLBACK_VARIATION_SUFFIXES)
    assert len(perms) == expected


def test_generate_fallback_variations_max_limit():
    many = [f"name{i}" for i in range(20)]
    perms = compose_fallback_variations(many)
    per_name = 1 + len(FALLBACK_VARIATION_PREFIXES) + len(FALLBACK_VARIATION_SUFFIXES)
    assert len(perms) == MAX_FALLBACK_VARIATION_KEYWORDS * per_name


def test_generate_fallback_variations_empty():
    assert compose_fallback_variations([]) == []


def test_names_all_domains_taken_none_taken():
    results = [
        make_domain_result(
            "voxly",
            domains=[{"domain": "voxly.com", "available": "available"}],
            candidate_name="voxly",
        ),
    ]
    taken = candidate_names_without_available_domains(results, ["com"])
    assert taken == []


def test_names_all_domains_taken_all_taken():
    results = [
        make_domain_result(
            "voxly",
            domains=[{"domain": "voxly.com", "available": "taken"}],
            candidate_name="voxly",
        ),
    ]
    taken = candidate_names_without_available_domains(results, ["com"])
    assert "voxly" in taken


def test_names_all_domains_taken_ignores_non_preferred():
    results = [
        make_domain_result(
            "voxly",
            domains=[
                {"domain": "voxly.com", "available": "taken"},
                {"domain": "voxly.xyz", "available": "available"},
            ],
            candidate_name="voxly",
        ),
    ]
    # xyz is available but not in preferred_tlds
    taken = candidate_names_without_available_domains(results, ["com"])
    assert "voxly" in taken
