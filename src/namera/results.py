from __future__ import annotations

from collections.abc import Iterable, Sequence

from namera.providers.base import Availability, ProviderResult


def normalize_candidate_name(value: str) -> str:
    """Return a canonical key for matching candidate names."""
    return value.strip().lower()


def derive_candidate_name(query: str) -> str:
    """Best-effort fallback for older results that only carry a query string."""
    query = query.strip()
    if "." in query:
        return query.rsplit(".", 1)[0].lower()
    return query.lower()


def result_candidate_key(result: ProviderResult) -> str:
    """Return the canonical candidate key for a result."""
    if result.candidate_name:
        return normalize_candidate_name(result.candidate_name)
    return derive_candidate_name(result.query)


def result_candidate_label(result: ProviderResult) -> str:
    """Return a display label for the candidate associated with a result."""
    if result.candidate_name:
        return result.candidate_name
    return derive_candidate_name(result.query)


def group_results_by_candidate(
    candidates: Sequence[str],
    results: Iterable[ProviderResult],
) -> dict[str, list[ProviderResult]]:
    """Group provider results by their originating candidate name."""
    grouped = {candidate: [] for candidate in candidates}
    lookup = {
        normalize_candidate_name(candidate): candidate
        for candidate in candidates
    }

    for result in results:
        candidate = lookup.get(result_candidate_key(result))
        if candidate is not None:
            grouped[candidate].append(result)

    return grouped


def normalize_domain_status(value: object) -> str:
    """Normalize mixed provider payloads to a canonical domain status string."""
    if isinstance(value, Availability):
        return value.value
    if isinstance(value, bool):
        return Availability.AVAILABLE.value if value else Availability.TAKEN.value
    if value is None:
        return Availability.UNKNOWN.value

    normalized = str(value).strip().lower()
    if normalized in {
        Availability.AVAILABLE.value,
        Availability.TAKEN.value,
        Availability.PARTIAL.value,
        Availability.UNKNOWN.value,
    }:
        return normalized
    return Availability.UNKNOWN.value


def domain_status_to_availability(value: object) -> Availability:
    """Convert a raw domain status payload into an Availability enum."""
    return Availability(normalize_domain_status(value))


def is_available_domain_status(value: object) -> bool:
    """Return True when a raw domain status represents availability."""
    return normalize_domain_status(value) == Availability.AVAILABLE.value


def summarize_domain_statuses(values: Iterable[object]) -> Availability:
    """Collapse per-domain statuses into an overall provider result."""
    statuses = [normalize_domain_status(value) for value in values]
    if not statuses:
        return Availability.UNKNOWN
    if any(status == Availability.AVAILABLE.value for status in statuses):
        return Availability.AVAILABLE
    if all(status == Availability.TAKEN.value for status in statuses):
        return Availability.TAKEN
    return Availability.UNKNOWN
