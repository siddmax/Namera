"""Data models for the scoring engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Signal:
    """A single normalized scoring signal."""

    name: str  # e.g., "domain_com", "length", "pronounceability"
    value: float  # normalized 0.0 - 1.0
    raw: Any = None  # original value for display
    source: str = ""  # provider name or "local"

    def __post_init__(self):
        self.value = max(0.0, min(1.0, self.value))


@dataclass
class ScoringProfile:
    """Weights and filters for ranking names."""

    name: str
    weights: dict[str, float]
    filters: dict[str, float] = field(default_factory=dict)
    description: str = ""

    def effective_weight(self, signal_name: str) -> float:
        """Return weight for a signal, 0.0 if not in profile."""
        return self.weights.get(signal_name, 0.0)


@dataclass
class RankedName:
    """A name with its composite score and individual signals."""

    name: str
    composite_score: float
    signals: dict[str, Signal] = field(default_factory=dict)
    filtered_out: bool = False
    filter_reason: str | None = None

    def to_dict(self) -> dict:
        """Serialize for JSON output."""
        return {
            "name": self.name,
            "score": round(self.composite_score, 4),
            "signals": {
                k: {"value": round(v.value, 4), "raw": v.raw, "source": v.source}
                for k, v in self.signals.items()
            },
            "filtered_out": self.filtered_out,
            "filter_reason": self.filter_reason,
        }
