"""Name permutation generation for taken base names."""

from __future__ import annotations

from namera.providers.base import CheckType, ProviderResult
from namera.results import is_available_domain_status, result_candidate_key

PERM_PREFIXES = ["get", "try", "use", "go", "my"]
PERM_SUFFIXES = ["app", "hq"]
MAX_PERM_BASE_NAMES = 5


def names_all_domains_taken(
    results: list[ProviderResult], preferred_tlds: list[str]
) -> list[str]:
    """Return base names where no preferred-TLD domain is available."""
    has_available: set[str] = set()
    checked: set[str] = set()
    for r in results:
        if r.check_type != CheckType.DOMAIN:
            continue
        base = result_candidate_key(r)
        checked.add(base)
        for d in r.details.get("domains", []):
            domain_str = d.get("domain", "")
            tld = domain_str.rsplit(".", 1)[-1] if "." in domain_str else ""
            if tld in preferred_tlds and is_available_domain_status(d.get("available")):
                has_available.add(base)
    return [n for n in checked if n not in has_available]


def generate_permutation_names(base_names: list[str]) -> list[str]:
    """Generate prefix/suffix permutations for taken base names."""
    perms = []
    for name in base_names[:MAX_PERM_BASE_NAMES]:
        for p in PERM_PREFIXES:
            perms.append(f"{p}{name}")
        for s in PERM_SUFFIXES:
            perms.append(f"{name}{s}")
    return perms
