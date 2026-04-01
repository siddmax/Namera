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

_STRING_FIELDS = {
    "niche",
    "industry",
    "description",
    "target_audience",
    "location",
    "name_style",
    "scoring_profile",
}
_LIST_STRING_FIELDS = {"name_candidates", "keywords", "preferred_tlds", "checks"}


@dataclass
class BusinessContext:
    name_candidates: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    # Business identity
    niche: str | None = None
    industry: str | None = None
    description: str | None = None

    # Targeting
    target_audience: str | None = None
    location: str | None = None

    # Domain preferences
    preferred_tlds: list[str] | None = None
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
        if not isinstance(data, dict):
            raise TypeError("BusinessContext must be a JSON object.")

        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        normalized: dict = {}

        for field_name, value in filtered.items():
            if field_name in _STRING_FIELDS:
                normalized[field_name] = _normalize_optional_string(field_name, value)
            elif field_name in _LIST_STRING_FIELDS:
                normalized[field_name] = _normalize_string_list(field_name, value)
            elif field_name == "weight_overrides":
                normalized[field_name] = _normalize_weight_overrides(value)
            else:
                normalized[field_name] = value

        return cls(**normalized)

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

        search_text = " ".join(
            value.lower()
            for value in (self.niche, self.industry, self.location, self.description)
            if value
        )
        if search_text:
            for keyword, tlds in TLD_HINTS.items():
                if keyword in search_text:
                    return tlds

        return DEFAULT_TLDS

    def resolve_check_types(self) -> list[CheckType]:
        if not self.checks:
            return [CheckType.DOMAIN, CheckType.WHOIS, CheckType.TRADEMARK]

        result = []
        invalid_checks = []
        for check in self.checks:
            ct = CHECK_TYPE_MAP.get(check.lower())
            if ct:
                result.append(ct)
            else:
                invalid_checks.append(check)

        if invalid_checks:
            raise ValueError(
                "Invalid checks: "
                + ", ".join(sorted(invalid_checks))
                + ". Expected one or more of: domain, whois, trademark, social."
            )

        return result


def _normalize_optional_string(field_name: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")

    normalized = value.strip()
    return normalized or None


def _normalize_string_list(field_name: str, value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a list of strings.")

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise TypeError(f"{field_name} must be a list of strings.")

        item_value = item.strip()
        if item_value:
            if field_name == "preferred_tlds":
                normalized.append(item_value.lstrip("."))
            else:
                normalized.append(item_value)

    return list(dict.fromkeys(normalized))


def _normalize_weight_overrides(value: object) -> dict[str, float] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError("weight_overrides must be an object mapping signal names to numbers.")

    normalized: dict[str, float] = {}
    for key, weight in value.items():
        if not isinstance(key, str) or not key.strip():
            raise TypeError("weight_overrides keys must be non-empty strings.")
        if not isinstance(weight, (int, float)):
            raise TypeError("weight_overrides values must be numeric.")
        normalized[key.strip()] = float(weight)

    return normalized or None
