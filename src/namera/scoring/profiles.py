"""Built-in scoring profiles for common use cases."""

from __future__ import annotations

from namera.scoring.models import ScoringProfile

PROFILES: dict[str, ScoringProfile] = {
    "default": ScoringProfile(
        name="default",
        weights={
            "domain_com": 0.18,
            "domain_availability": 0.08,
            "whois": 0.03,
            "trademark": 0.20,
            "trademark_clearance": 0.05,
            "social_availability": 0.08,
            "length": 0.08,
            "pronounceability": 0.08,
            "string_features": 0.04,
            "distinctiveness": 0.05,
            "semantic_fit": 0.06,
            "style_fit": 0.04,
            "audience_fit": 0.03,
        },
        description="Balanced scoring across all signals",
    ),
    "startup-saas": ScoringProfile(
        name="startup-saas",
        weights={
            "domain_com": 0.22,
            "domain_availability": 0.08,
            "whois": 0.03,
            "trademark": 0.15,
            "trademark_clearance": 0.05,
            "social_availability": 0.08,
            "length": 0.08,
            "pronounceability": 0.08,
            "string_features": 0.04,
            "distinctiveness": 0.05,
            "semantic_fit": 0.06,
            "style_fit": 0.04,
            "audience_fit": 0.04,
        },
        filters={"domain_com": 0.5},
        description="Prioritizes .com availability for SaaS startups",
    ),
    "fintech": ScoringProfile(
        name="fintech",
        weights={
            "domain_com": 0.18,
            "domain_availability": 0.04,
            "whois": 0.03,
            "trademark": 0.22,
            "trademark_clearance": 0.08,
            "social_availability": 0.04,
            "length": 0.08,
            "pronounceability": 0.08,
            "string_features": 0.03,
            "distinctiveness": 0.08,
            "semantic_fit": 0.06,
            "style_fit": 0.04,
            "audience_fit": 0.04,
        },
        filters={"trademark": 0.5},
        description="Heavy trademark weighting for regulated fintech",
    ),
    "consumer": ScoringProfile(
        name="consumer",
        weights={
            "domain_com": 0.12,
            "domain_availability": 0.08,
            "whois": 0.03,
            "trademark": 0.14,
            "trademark_clearance": 0.04,
            "social_availability": 0.12,
            "length": 0.08,
            "pronounceability": 0.10,
            "string_features": 0.04,
            "distinctiveness": 0.06,
            "semantic_fit": 0.07,
            "style_fit": 0.05,
            "audience_fit": 0.07,
        },
        description="Prioritizes memorability and social handles for consumer brands",
    ),
    "developer-tools": ScoringProfile(
        name="developer-tools",
        weights={
            "domain_com": 0.08,
            "domain_dev": 0.08,
            "domain_io": 0.08,
            "domain_availability": 0.04,
            "whois": 0.03,
            "trademark": 0.14,
            "trademark_clearance": 0.04,
            "social_github": 0.08,
            "social_availability": 0.04,
            "length": 0.08,
            "pronounceability": 0.05,
            "string_features": 0.04,
            "distinctiveness": 0.05,
            "semantic_fit": 0.06,
            "style_fit": 0.04,
            "audience_fit": 0.07,
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
