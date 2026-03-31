from __future__ import annotations

from dataclasses import replace

from namera.providers.base import Availability, CheckType, ProviderResult


def flag_trademark_risks(results: list[ProviderResult]) -> list[ProviderResult]:
    """Flag results for names that have trademark conflicts.

    Sets details["trademark_risk"] = True on ALL results for names
    where any trademark provider returned TAKEN.
    """
    risky_names: set[str] = set()
    for r in results:
        if r.check_type == CheckType.TRADEMARK and r.available == Availability.TAKEN:
            risky_names.add(r.query.lower())

    for r in results:
        if r.query.lower() in risky_names:
            r.details["trademark_risk"] = True

    return results


def get_trademark_risk_names(results: list[ProviderResult]) -> list[str]:
    """Return list of names that have trademark conflicts."""
    return sorted({
        r.query
        for r in results
        if r.check_type == CheckType.TRADEMARK and r.available == Availability.TAKEN
    })


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
                if d["available"] == Availability.AVAILABLE.value
            ]
            if available_domains:
                new_result = replace(
                    r, details={**r.details, "domains": available_domains}
                )
                new_result.available = Availability.AVAILABLE
                filtered.append(new_result)
        else:
            if r.available == Availability.AVAILABLE:
                filtered.append(r)
    return filtered
