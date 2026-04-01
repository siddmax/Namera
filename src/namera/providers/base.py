from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class CheckType(Enum):
    DOMAIN = "domain"
    WHOIS = "whois"
    TRADEMARK = "trademark"
    SOCIAL = "social"


class Availability(Enum):
    AVAILABLE = "available"
    TAKEN = "taken"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass
class ProviderResult:
    check_type: CheckType
    provider_name: str
    query: str
    available: Availability
    candidate_name: str | None = None
    details: dict = field(default_factory=dict)
    error: str | None = None


class Provider(ABC):
    """Base class for all lookup providers."""

    name: str
    check_type: CheckType

    @abstractmethod
    async def check(self, query: str, **kwargs) -> ProviderResult:
        ...

    @classmethod
    def cache_kwargs(cls, kwargs: dict) -> dict:
        """Return only the kwargs that materially affect this provider's output."""
        return kwargs

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "name") and hasattr(cls, "check_type"):
            registry.register(cls)


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, type[Provider]] = {}

    def register(self, provider_cls: type[Provider]):
        self._providers[provider_cls.name] = provider_cls

    def get(self, name: str) -> type[Provider] | None:
        return self._providers.get(name)

    def list_by_type(self, check_type: CheckType) -> list[type[Provider]]:
        return [p for p in self._providers.values() if p.check_type == check_type]

    def all(self) -> list[type[Provider]]:
        return list(self._providers.values())


registry = ProviderRegistry()
