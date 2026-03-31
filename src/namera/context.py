from __future__ import annotations

import json
from dataclasses import dataclass, field

from namera.providers.base import CheckType

DEFAULT_TLDS = ["com", "net", "org", "io", "dev"]

TLD_HINTS: dict[str, list[str]] = {
    "fintech": ["com", "io", "finance", "money", "co"],
    "finance": ["com", "io", "finance", "money", "co"],
    "tech": ["com", "io", "dev", "ai", "co"],
    "saas": ["com", "io", "dev", "app", "co"],
    "ai": ["com", "ai", "io", "dev"],
    "health": ["com", "health", "io", "co"],
    "healthcare": ["com", "health", "io", "co"],
    "education": ["com", "edu", "io", "academy"],
    "ecommerce": ["com", "shop", "store", "io", "co"],
    "retail": ["com", "shop", "store", "co"],
    "gaming": ["com", "io", "gg", "dev"],
    "crypto": ["com", "io", "finance", "co"],
    "media": ["com", "io", "media", "co"],
    "food": ["com", "co", "io", "kitchen"],
    "travel": ["com", "travel", "io", "co"],
}

CHECK_TYPE_MAP = {
    "domain": CheckType.DOMAIN,
    "whois": CheckType.WHOIS,
    "trademark": CheckType.TRADEMARK,
    "social": CheckType.SOCIAL,
}


@dataclass
class BusinessContext:
    name_candidates: list[str] = field(default_factory=list)

    # Business identity
    niche: str | None = None
    industry: str | None = None
    description: str | None = None

    # Targeting
    target_audience: str | None = None
    location: str | None = None

    # Domain preferences
    preferred_tlds: list[str] | None = None
    max_domain_price: float | None = None
    name_style: str | None = None

    # Check selection
    checks: list[str] | None = None

    # Scoring
    scoring_profile: str | None = None
    weight_overrides: dict[str, float] | None = None

    def to_dict(self) -> dict:
        result = {}
        for k, v in self.__dict__.items():
            if v is not None and v != [] and v != "":
                result[k] = v
        return result

    @classmethod
    def from_dict(cls, data: dict) -> BusinessContext:
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @classmethod
    def from_json(cls, json_str: str) -> BusinessContext:
        data = json.loads(json_str)
        return cls.from_dict(data)

    def resolve_tlds(self) -> list[str]:
        if self.preferred_tlds:
            # Check if single item is a preset name
            if len(self.preferred_tlds) == 1:
                from namera.presets import get_preset

                preset = get_preset(self.preferred_tlds[0])
                if preset:
                    return preset
            return self.preferred_tlds

        if self.niche:
            niche_lower = self.niche.lower()
            for keyword, tlds in TLD_HINTS.items():
                if keyword in niche_lower:
                    return tlds

        return DEFAULT_TLDS

    def resolve_check_types(self) -> list[CheckType]:
        if not self.checks:
            return [CheckType.DOMAIN, CheckType.WHOIS, CheckType.TRADEMARK]

        result = []
        for check in self.checks:
            ct = CHECK_TYPE_MAP.get(check.lower())
            if ct:
                result.append(ct)
        return result or [CheckType.DOMAIN, CheckType.WHOIS, CheckType.TRADEMARK]
