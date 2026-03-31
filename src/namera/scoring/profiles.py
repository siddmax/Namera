"""Built-in scoring profiles for common use cases."""

from __future__ import annotations

from namera.scoring.models import ScoringProfile

PROFILES: dict[str, ScoringProfile] = {
    "default": ScoringProfile(
        name="default",
        weights={
            "domain_com": 0.20,
            "domain_availability": 0.10,
            "whois": 0.05,
            "trademark": 0.20,
            "trademark_clearance": 0.05,
            "social_availability": 0.10,
            "length": 0.10,
            "pronounceability": 0.10,
            "string_features": 0.10,
        },
        description="Balanced scoring across all signals",
    ),
    "startup-saas": ScoringProfile(
        name="startup-saas",
        weights={
            "domain_com": 0.25,
            "domain_availability": 0.10,
            "whois": 0.05,
            "trademark": 0.15,
            "trademark_clearance": 0.05,
            "social_availability": 0.10,
            "length": 0.10,
            "pronounceability": 0.10,
            "string_features": 0.10,
        },
        filters={"domain_com": 0.5},
        description="Prioritizes .com availability for SaaS startups",
    ),
    "fintech": ScoringProfile(
        name="fintech",
        weights={
            "domain_com": 0.20,
            "domain_availability": 0.05,
            "whois": 0.05,
            "trademark": 0.25,
            "trademark_clearance": 0.10,
            "social_availability": 0.05,
            "length": 0.10,
            "pronounceability": 0.10,
            "string_features": 0.10,
        },
        filters={"trademark": 0.5},
        description="Heavy trademark weighting for regulated fintech",
    ),
    "consumer": ScoringProfile(
        name="consumer",
        weights={
            "domain_com": 0.15,
            "domain_availability": 0.10,
            "whois": 0.05,
            "trademark": 0.15,
            "trademark_clearance": 0.05,
            "social_availability": 0.15,
            "length": 0.10,
            "pronounceability": 0.15,
            "string_features": 0.10,
        },
        description="Prioritizes memorability and social handles for consumer brands",
    ),
    "developer-tools": ScoringProfile(
        name="developer-tools",
        weights={
            "domain_com": 0.10,
            "domain_dev": 0.10,
            "domain_io": 0.10,
            "domain_availability": 0.05,
            "whois": 0.05,
            "trademark": 0.15,
            "trademark_clearance": 0.05,
            "social_github": 0.10,
            "social_availability": 0.05,
            "length": 0.10,
            "pronounceability": 0.05,
            "string_features": 0.10,
        },
        description="Values .dev/.io TLDs and GitHub handle for dev tools",
    ),
}


def get_profile(name: str) -> ScoringProfile:
    """Get a scoring profile by name, defaults to 'default'."""
    return PROFILES.get(name, PROFILES["default"])


def list_profiles() -> list[str]:
    """Return all available profile names."""
    return sorted(PROFILES.keys())
