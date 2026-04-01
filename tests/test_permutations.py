"""Tests for the permutations module."""

from __future__ import annotations

from namera.permutations import (
    MAX_PERM_BASE_NAMES,
    PERM_PREFIXES,
    PERM_SUFFIXES,
    generate_permutation_names,
    names_all_domains_taken,
)
from tests.conftest import make_domain_result


def test_generate_permutation_names_basic():
    perms = generate_permutation_names(["voxly"])
    assert f"get{' voxly'}" not in perms  # no space
    assert "getvoxly" in perms
    assert "tryvoxly" in perms
    assert "voxlyapp" in perms
    assert "voxlyhq" in perms


def test_generate_permutation_names_count():
    perms = generate_permutation_names(["test"])
    expected = len(PERM_PREFIXES) + len(PERM_SUFFIXES)
    assert len(perms) == expected


def test_generate_permutation_names_max_limit():
    many = [f"name{i}" for i in range(20)]
    perms = generate_permutation_names(many)
    per_name = len(PERM_PREFIXES) + len(PERM_SUFFIXES)
    assert len(perms) == MAX_PERM_BASE_NAMES * per_name


def test_generate_permutation_names_empty():
    assert generate_permutation_names([]) == []


def test_names_all_domains_taken_none_taken():
    results = [
        make_domain_result(
            "voxly",
            domains=[{"domain": "voxly.com", "available": "available"}],
            candidate_name="voxly",
        ),
    ]
    taken = names_all_domains_taken(results, ["com"])
    assert taken == []


def test_names_all_domains_taken_all_taken():
    results = [
        make_domain_result(
            "voxly",
            domains=[{"domain": "voxly.com", "available": "taken"}],
            candidate_name="voxly",
        ),
    ]
    taken = names_all_domains_taken(results, ["com"])
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
    taken = names_all_domains_taken(results, ["com"])
    assert "voxly" in taken
