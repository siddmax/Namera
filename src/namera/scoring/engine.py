"""Ranking engine — normalizes signals, applies weights, sorts candidates."""

from __future__ import annotations

from namera.providers.base import ProviderResult
from namera.scoring.local_signals import compute_local_signals
from namera.scoring.models import RankedName, ScoringProfile, Signal
from namera.scoring.normalizers import normalize_result


class RankingEngine:
    """Score and rank name candidates using weighted linear combination."""

    def __init__(self, profile: ScoringProfile):
        self.profile = profile

    def rank(
        self, candidates: dict[str, list[ProviderResult]]
    ) -> list[RankedName]:
        """Rank name candidates.

        Args:
            candidates: {name: [ProviderResult, ...]} from all providers

        Returns:
            Sorted list of RankedName, highest score first.
            Filtered-out names are appended at the end.
        """
        ranked = []
        for name, results in candidates.items():
            signals = self._collect_signals(name, results)
            filtered_out, filter_reason = self._apply_filters(signals)
            score = self._compute_score(signals) if not filtered_out else 0.0

            ranked.append(RankedName(
                name=name,
                composite_score=score,
                signals=signals,
                filtered_out=filtered_out,
                filter_reason=filter_reason,
            ))

        # Sort: non-filtered first by score desc, then filtered at end
        ranked.sort(key=lambda r: (not r.filtered_out, r.composite_score), reverse=True)
        return ranked

    def _collect_signals(
        self, name: str, results: list[ProviderResult]
    ) -> dict[str, Signal]:
        """Gather all signals for a name from provider results + local analysis."""
        signals: dict[str, Signal] = {}

        # Normalize provider results into signals
        for result in results:
            for signal in normalize_result(result):
                signals[signal.name] = signal

        # Add local string-analysis signals
        for signal in compute_local_signals(name):
            signals[signal.name] = signal

        return signals

    def _apply_filters(
        self, signals: dict[str, Signal]
    ) -> tuple[bool, str | None]:
        """Check hard filter thresholds. Returns (filtered_out, reason)."""
        for signal_name, min_threshold in self.profile.filters.items():
            signal = signals.get(signal_name)
            if signal and signal.value < min_threshold:
                return True, f"{signal_name} below threshold ({signal.value:.2f} < {min_threshold})"
        return False, None

    def _compute_score(self, signals: dict[str, Signal]) -> float:
        """Compute weighted composite score.

        Missing signals contribute 0 to the numerator but their weight
        stays in the denominator, so names with failed checks are not
        artificially boosted.
        """
        total = 0.0
        total_weight = sum(self.profile.weights.values())

        for signal_name, weight in self.profile.weights.items():
            signal = signals.get(signal_name)
            if signal is not None:
                total += signal.value * weight

        return total / total_weight if total_weight > 0 else 0.0
