"""Ranking display and serialization helpers extracted from cli.py."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from namera.scoring.models import RankedName, ScoringProfile
from namera.theme import TABLE_TITLE, WARNING, styled

FIND_TOP_N = 10


def compact_ranked(r: RankedName) -> dict:
    """Compact serialization of a RankedName for agent consumption."""
    entry: dict = {"name": r.name, "score": round(r.composite_score, 3)}
    sigs = {k: round(v.value, 2) for k, v in r.signals.items() if v.value > 0}
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
        elif r.composite_score >= 0.7:
            score_str = styled(f"{r.composite_score:.2f}", "bright_green")
        elif r.composite_score >= 0.4:
            score_str = styled(f"{r.composite_score:.2f}", "bright_yellow")
        else:
            score_str = styled(f"{r.composite_score:.2f}", "red")

        def _signal_display(name: str) -> str:
            sig = r.signals.get(name)
            if sig is None:
                return styled("-", "dim")
            if sig.value >= 0.7:
                return styled(f"{sig.value:.1f}", "bright_green")
            if sig.value >= 0.4:
                return styled(f"{sig.value:.1f}", "bright_yellow")
            return styled(f"{sig.value:.1f}", "red")

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
