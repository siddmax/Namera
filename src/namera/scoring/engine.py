"""Ranking engine — normalizes signals, applies weights, sorts candidates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from namera.providers.base import ProviderResult
from namera.scoring.local_signals import compute_local_signals
from namera.scoring.models import RankedName, ScoringProfile, Signal
from namera.scoring.normalizers import normalize_result

if TYPE_CHECKING:
    from namera.context import BusinessContext


class RankingEngine:
    """Score and rank name candidates using weighted linear combination."""

    def __init__(self, profile: ScoringProfile):
        self.profile = profile

    def rank(
        self,
        candidates: dict[str, list[ProviderResult]],
        context: BusinessContext | None = None,
    ) -> list[RankedName]:
        """Rank name candidates.

        Args:
            candidates: {name: [ProviderResult, ...]} from all providers
            context: Optional business context for semantic/style/audience signals

        Returns:
            Sorted list of RankedName, highest score first.
            Filtered-out names are appended at the end.
        """
        ranked = []
        for name, results in candidates.items():
            signals = self._collect_signals(name, results, context)
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
        self,
        name: str,
        results: list[ProviderResult],
        context: BusinessContext | None = None,
    ) -> dict[str, Signal]:
        """Gather all signals for a name from provider results + local analysis."""
        signals: dict[str, Signal] = {}

        # Normalize provider results into signals
        for result in results:
            for signal in normalize_result(result):
                signals[signal.name] = signal

        # Synthesize conservative trademark aggregate from exact + fuzzy
        exact = signals.get("trademark_exact")
        fuzzy = signals.get("trademark_fuzzy")
        if exact or fuzzy:
            values = [s.value for s in [exact, fuzzy] if s]
            signals["trademark"] = Signal(
                name="trademark", value=min(values),
                raw="aggregate", source="scoring",
            )

        # Add local string-analysis signals
        for signal in compute_local_signals(name):
            signals[signal.name] = signal

        # Add context-aware signals when business context is available
        if context:
            from namera.scoring.context_signals import compute_context_signals

            for signal in compute_context_signals(name, context):
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
