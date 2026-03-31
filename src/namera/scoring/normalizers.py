"""Convert ProviderResult objects into normalized Signal objects."""

from __future__ import annotations

from namera.providers.base import Availability, CheckType, ProviderResult
from namera.scoring.models import Signal

_AVAILABILITY_SCORES = {
    Availability.AVAILABLE: 1.0,
    Availability.TAKEN: 0.0,
    Availability.UNKNOWN: 0.3,
}


def normalize_domain(result: ProviderResult) -> list[Signal]:
    """Normalize domain check results into per-TLD signals."""
    signals = []
    domains = result.details.get("domains", [])

    for d in domains:
        domain = d.get("domain", "")
        tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
        av_str = d.get("available", "unknown")

        # Map string availability to score
        if av_str == "available":
            score = 1.0
        elif av_str == "taken":
            score = 0.0
        else:
            score = 0.3

        signal_name = f"domain_{tld}" if tld else "domain"
        signals.append(Signal(
            name=signal_name,
            value=score,
            raw=av_str,
            source=result.provider_name,
        ))

    # Aggregate: fraction of TLDs available
    if domains:
        available_count = sum(1 for d in domains if d.get("available") == "available")
        aggregate = available_count / len(domains)
        signals.append(Signal(
            name="domain_availability",
            value=aggregate,
            raw=f"{available_count}/{len(domains)}",
            source=result.provider_name,
        ))

    return signals


def normalize_whois(result: ProviderResult) -> list[Signal]:
    """Normalize WHOIS result into a single signal."""
    return [Signal(
        name="whois",
        value=_AVAILABILITY_SCORES.get(result.available, 0.3),
        raw=result.available.value,
        source=result.provider_name,
    )]


def normalize_trademark(result: ProviderResult) -> list[Signal]:
    """Normalize trademark check results."""
    signals = []

    # Base availability signal
    signals.append(Signal(
        name="trademark",
        value=_AVAILABILITY_SCORES.get(result.available, 0.3),
        raw=result.available.value,
        source=result.provider_name,
    ))

    # Similarity score (inverted: high similarity = low score = bad)
    max_sim = result.details.get("max_similarity")
    if max_sim is not None:
        signals.append(Signal(
            name="trademark_clearance",
            value=max(0.0, 1.0 - float(max_sim)),
            raw=max_sim,
            source=result.provider_name,
        ))

    return signals


def normalize_social(result: ProviderResult) -> list[Signal]:
    """Normalize social handle check results."""
    signals = []
    platforms = result.details.get("platforms", {})

    for platform, status in platforms.items():
        if status == "available":
            score = 1.0
        elif status == "taken":
            score = 0.0
        else:
            score = 0.3
        signals.append(Signal(
            name=f"social_{platform}",
            value=score,
            raw=status,
            source=result.provider_name,
        ))

    # Aggregate
    if platforms:
        available = sum(1 for s in platforms.values() if s == "available")
        signals.append(Signal(
            name="social_availability",
            value=available / len(platforms),
            raw=f"{available}/{len(platforms)}",
            source=result.provider_name,
        ))

    return signals


# Registry mapping check types to normalizer functions
NORMALIZERS: dict[CheckType, callable] = {
    CheckType.DOMAIN: normalize_domain,
    CheckType.WHOIS: normalize_whois,
    CheckType.TRADEMARK: normalize_trademark,
    CheckType.SOCIAL: normalize_social,
}


def normalize_result(result: ProviderResult) -> list[Signal]:
    """Normalize any ProviderResult into Signals using the appropriate normalizer."""
    normalizer = NORMALIZERS.get(result.check_type)
    if normalizer:
        return normalizer(result)
    return []


def register_normalizer(check_type: CheckType, fn: callable) -> None:
    """Register a normalizer for a new check type."""
    NORMALIZERS[check_type] = fn
