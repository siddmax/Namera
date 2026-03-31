from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt  # noqa: F401 — Prompt used in _ask
from rich.table import Table

from namera.composer import COMMON_PREFIXES, COMMON_SUFFIXES, ComposerConfig, compose
from namera.context import BusinessContext
from namera.scoring.local_signals import compute_local_signals
from namera.theme import FIELD_LABEL, PANEL_BORDER, WARNING, styled

# How many candidates to keep after local pre-ranking
_MAX_CANDIDATES = 50


class InteractiveSession:
    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def run(self) -> BusinessContext | None:
        self.console.print(
            Panel(
                "[bold]Namera — Name Discovery Wizard[/bold]\n"
                "Enter keywords and we'll generate name permutations to check.",
                border_style=PANEL_BORDER,
            )
        )

        raw = self._ask("Keywords (comma-separated, e.g., pay,split,budget)")
        if not raw:
            self.console.print(styled("No keywords provided. Cancelled.", WARNING))
            return None

        keywords = [k.strip().lower() for k in raw.split(",") if k.strip()]
        if not keywords:
            self.console.print(styled("No keywords provided. Cancelled.", WARNING))
            return None

        # Generate permutations with common prefixes/suffixes
        config = ComposerConfig(
            keywords=keywords,
            tlds=["com"],
            use_common_prefixes=True,
            use_common_suffixes=True,
        )
        domains = compose(config)
        all_candidates = list(dict.fromkeys(d.split(".")[0] for d in domains))

        # Pre-rank by local signals (length, pronounceability, string quality)
        # to avoid excessive network calls
        candidates = _prerank(all_candidates, _MAX_CANDIDATES)

        ctx = BusinessContext(name_candidates=candidates)

        self._show_summary(ctx, config)

        if not Confirm.ask("Proceed with these checks?", default=True):
            self.console.print(styled("Cancelled.", WARNING))
            return None

        return ctx

    def _ask(self, question: str, default: str = "") -> str:
        return Prompt.ask(f"  {question}", default=default).strip()

    def _show_summary(self, ctx: BusinessContext, config: ComposerConfig | None = None):
        table = Table(show_header=False, border_style=PANEL_BORDER, padding=(0, 2))
        table.add_column("Field", style=FIELD_LABEL)
        table.add_column("Value")

        if config:
            table.add_row("Keywords", ", ".join(config.keywords))
            all_prefixes = list(config.prefixes)
            if config.use_common_prefixes:
                all_prefixes += [p for p in COMMON_PREFIXES if p not in all_prefixes]
            if all_prefixes:
                table.add_row("Prefixes", ", ".join(all_prefixes))
            all_suffixes = list(config.suffixes)
            if config.use_common_suffixes:
                all_suffixes += [s for s in COMMON_SUFFIXES if s not in all_suffixes]
            if all_suffixes:
                table.add_row("Suffixes", ", ".join(all_suffixes))

        if ctx.name_candidates:
            table.add_row("Names to check", str(len(ctx.name_candidates)))
            preview = ctx.name_candidates[:10]
            preview_str = ", ".join(preview)
            if len(ctx.name_candidates) > 10:
                preview_str += f" ... (+{len(ctx.name_candidates) - 10} more)"
            table.add_row("Preview", preview_str)

        self.console.print(Panel(table, title="Search Config", border_style=PANEL_BORDER))


def _prerank(candidates: list[str], limit: int) -> list[str]:
    """Rank candidates by local string signals and return the top `limit`."""
    if len(candidates) <= limit:
        return candidates

    scored: list[tuple[float, str]] = []
    for name in candidates:
        signals = compute_local_signals(name)
        # Simple average of all local signal values
        avg = sum(s.value for s in signals) / len(signals) if signals else 0.0
        scored.append((avg, name))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [name for _, name in scored[:limit]]
