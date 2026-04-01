"""Ranking display and serialization helpers extracted from cli.py."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

from namera.scoring.models import RankedName, ScoringProfile
from namera.theme import TABLE_TITLE, WARNING, styled

if TYPE_CHECKING:
    from namera.context import BusinessContext

FIND_TOP_N = 10


def build_find_json(
    ranked: list[RankedName],
    tlds: list[str],
    profile: ScoringProfile,
    context: BusinessContext | None = None,
    trademark_risks: list[str] | None = None,
    rate_limited: bool = False,
) -> dict:
    """Build comprehensive JSON output combining find + rank for agents.

    Returns a single payload with ranked results, filtered names, and summary.
    """
    ranked_entries = []
    filtered_entries = []

    for r in ranked:
        if r.filtered_out:
            filtered_entries.append({"name": r.name, "reason": r.filter_reason})
            continue

        entry: dict = {
            "rank": len(ranked_entries) + 1,
            "name": r.name,
            "score": round(r.composite_score * 100, 1),
        }

        # Domain availability per TLD
        domains = {}
        for tld in tlds:
            sig = r.signals.get(f"domain_{tld}")
            if sig:
                if sig.value >= 1.0:
                    domains[tld] = "available"
                elif sig.value == 0.0:
                    domains[tld] = "taken"
                else:
                    domains[tld] = "unknown"
        if domains:
            entry["domains"] = domains

        # Trademark status
        tm = r.signals.get("trademark")
        if tm:
            if tm.value >= 1.0:
                entry["trademark"] = "clear"
            elif tm.value == 0.0:
                entry["trademark"] = "risk"
            else:
                entry["trademark"] = "unknown"

        # Social handle availability
        social = {}
        for key, sig in r.signals.items():
            if key.startswith("social_") and key != "social_availability":
                platform = key.removeprefix("social_")
                social[platform] = "available" if sig.value >= 1.0 else "taken"
        if social:
            entry["social"] = social

        # Quality signals
        quality = {}
        for k in ("length", "pronounceability", "string_features"):
            sig = r.signals.get(k)
            if sig and sig.value > 0:
                quality[k] = round(sig.value * 100, 1)
        if quality:
            entry["quality"] = quality

        ranked_entries.append(entry)

    payload: dict = {"ranked": ranked_entries}

    if filtered_entries:
        payload["filtered"] = filtered_entries

    if trademark_risks:
        payload["trademark_risks"] = trademark_risks

    summary: dict = {
        "candidates_checked": len(ranked),
        "viable": len(ranked_entries),
        "filtered_out": len(filtered_entries),
        "profile": profile.name,
        "tlds_checked": tlds,
    }
    if rate_limited:
        summary["rate_limited"] = True
        summary["rate_limited_note"] = (
            "Trademark checks were rate-limited. "
            "Trademark scores may be incomplete. Retry after 60s."
        )
    payload["summary"] = summary

    return payload


def compact_ranked(r: RankedName) -> dict:
    """Compact serialization of a RankedName for agent consumption."""
    entry: dict = {"name": r.name, "score": round(r.composite_score * 100, 1)}
    sigs = {k: round(v.value * 100, 1) for k, v in r.signals.items() if v.value > 0}
    if sigs:
        entry["signals"] = sigs
    if r.filtered_out:
        entry["filtered"] = True
        if r.filter_reason:
            entry["reason"] = r.filter_reason
    return entry


def render_find_ranked(
    ranked: list[RankedName],
    tlds: list[str],
    console: Console,
) -> None:
    """Filter ranked results to viable names and display top N."""

    def _is_viable(r: RankedName) -> bool:
        if r.filtered_out:
            return False
        has_available_domain = any(
            r.signals.get(f"domain_{tld}") and r.signals[f"domain_{tld}"].value >= 1.0
            for tld in tlds
        )
        if not has_available_domain:
            return False
        tm = r.signals.get("trademark")
        if tm and tm.value == 0.0:
            return False
        return True

    viable = [r for r in ranked if _is_viable(r)]
    top = viable[:FIND_TOP_N]

    if not top:
        console.print(styled("No available names found.", WARNING))
        return

    table = Table(title=styled("Ranked results", TABLE_TITLE))
    table.add_column("Rank", style="bold", justify="right")
    table.add_column("Name", style="bold")
    table.add_column("Score", justify="right")
    table.add_column(".com", justify="center")
    table.add_column("Trademark", justify="center")

    for i, r in enumerate(top, 1):
        score_int = int(r.composite_score * 100)
        if score_int >= 70:
            score_str = styled(str(score_int), "bright_green")
        elif score_int >= 40:
            score_str = styled(str(score_int), "bright_yellow")
        else:
            score_str = styled(str(score_int), "red")

        com_sig = r.signals.get("domain_com")
        if com_sig and com_sig.value >= 1.0:
            com_str = styled("Available", "bright_green")
        elif com_sig and com_sig.value == 0.0:
            com_str = styled("Taken", "red")
        else:
            com_str = styled("-", "dim")

        tm_sig = r.signals.get("trademark")
        if tm_sig and tm_sig.value >= 1.0:
            tm_str = styled("Clear", "bright_green")
        elif tm_sig and tm_sig.value == 0.0:
            tm_str = styled("Risk", "red")
        else:
            tm_str = styled("-", "dim")

        table.add_row(str(i), r.name, score_str, com_str, tm_str)

    console.print(table)


def render_ranked_table(
    ranked: list[RankedName],
    profile: ScoringProfile,
    console: Console,
) -> None:
    """Render ranked results as a Rich table with signal breakdowns."""
    table = Table(title=f"Rankings (profile: {profile.name})", title_style=TABLE_TITLE)
    table.add_column("#", style="bold", justify="right")
    table.add_column("Name", style="bold")
    table.add_column("Score", justify="right")
    table.add_column(".com", justify="center")
    table.add_column("Trademark", justify="center")
    table.add_column("Social", justify="center")
    table.add_column("Length", justify="center")
    table.add_column("Pronounce", justify="center")

    for i, r in enumerate(ranked, 1):
        if r.filtered_out:
            score_str = styled("FILTERED", WARNING)
        else:
            score_int = int(r.composite_score * 100)
            if score_int >= 70:
                score_str = styled(str(score_int), "bright_green")
            elif score_int >= 40:
                score_str = styled(str(score_int), "bright_yellow")
            else:
                score_str = styled(str(score_int), "red")

        def _signal_display(name: str) -> str:
            sig = r.signals.get(name)
            if sig is None:
                return styled("-", "dim")
            val = int(sig.value * 100)
            if val >= 70:
                return styled(str(val), "bright_green")
            if val >= 40:
                return styled(str(val), "bright_yellow")
            return styled(str(val), "red")

        table.add_row(
            str(i),
            r.name,
            score_str,
            _signal_display("domain_com"),
            _signal_display("trademark"),
            _signal_display("social_availability"),
            _signal_display("length"),
            _signal_display("pronounceability"),
        )

    console.print(table)

    filtered = [r for r in ranked if r.filtered_out]
    if filtered:
        for r in filtered:
            console.print(f"  {styled(r.name, 'dim')}: {r.filter_reason}")
        console.print()
