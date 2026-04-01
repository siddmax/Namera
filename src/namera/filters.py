from __future__ import annotations

from dataclasses import replace

from namera.providers.base import Availability, CheckType, ProviderResult
from namera.results import (
    is_available_domain_status,
    result_candidate_key,
    result_candidate_label,
)


def filter_trademarked_results(results: list[ProviderResult]) -> list[ProviderResult]:
    """Drop every result associated with a trademark-conflicted candidate."""
    risky_names = {
        result_candidate_key(result)
        for result in results
        if result.check_type == CheckType.TRADEMARK
        and result.available == Availability.TAKEN
    }
    if not risky_names:
        return list(results)

    return [
        replace(result, details=dict(result.details))
        for result in results
        if result_candidate_key(result) not in risky_names
    ]


def get_trademark_risk_names(results: list[ProviderResult]) -> list[str]:
    """Return list of names that have trademark conflicts."""
    risky_names: dict[str, str] = {}
    for result in results:
        if result.check_type == CheckType.TRADEMARK and result.available == Availability.TAKEN:
            risky_names.setdefault(
                result_candidate_key(result),
                result_candidate_label(result),
            )

    return sorted(risky_names.values(), key=str.lower)


def filter_available_only(results: list[ProviderResult]) -> list[ProviderResult]:
    """Filter results to only include available entries.

    For domain results with nested sub-results, filters the domains list
    and drops the result entirely if no domains remain available.
    """
    filtered = []
    for r in results:
        if r.check_type == CheckType.DOMAIN and r.details.get("domains"):
            available_domains = [
                d
                for d in r.details["domains"]
                if is_available_domain_status(d.get("available"))
            ]
            if available_domains:
                new_result = replace(
                    r,
                    details={**r.details, "domains": available_domains},
                )
                new_result.available = Availability.AVAILABLE
                filtered.append(new_result)
        else:
            if r.available == Availability.AVAILABLE:
                filtered.append(replace(r, details=dict(r.details)))
    return filtered
