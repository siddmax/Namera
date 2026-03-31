from __future__ import annotations

import csv
import io
import json
from enum import Enum
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.table import Table

from namera.providers.base import Availability, CheckType, ProviderResult
from namera.theme import FIELD_LABEL, TABLE_TITLE, availability_style, styled

if TYPE_CHECKING:
    from namera.context import BusinessContext


class _Encoder(json.JSONEncoder):
    """JSON encoder that handles Enum values."""

    def default(self, o):
        if isinstance(o, Enum):
            return o.value
        return super().default(o)


def _flatten_results(results: list[ProviderResult], compact: bool = False) -> list[dict]:
    """Flatten domain sub-results into individual entries.

    When compact=True, omit null/empty fields and use short keys for token efficiency.
    """
    flat = []
    for r in results:
        if r.check_type == CheckType.DOMAIN and r.details.get("domains"):
            for d in r.details["domains"]:
                raw_avail = d["available"]
                if isinstance(raw_avail, bool):
                    status = "available" if raw_avail else "taken"
                else:
                    status = raw_avail
                entry: dict = {
                    "type": r.check_type.value,
                    "query": d["domain"],
                    "status": status,
                }
                if not compact:
                    entry["provider"] = r.provider_name
                if r.error:
                    entry["error"] = r.error
                flat.append(entry)
        else:
            entry = {
                "type": r.check_type.value,
                "query": r.query,
                "status": r.available.value,
            }
            if not compact:
                entry["provider"] = r.provider_name
                details = {
                    k: v for k, v in r.details.items()
                    if k != "raw" and v not in (None, "", {})
                }
                if details:
                    entry["details"] = details
            if r.error:
                entry["error"] = r.error
            flat.append(entry)
    return flat


def _context_payload(context: Any) -> Any:
    """Convert context to a JSON-serializable form."""
    if context is None:
        return None
    if hasattr(context, "to_dict"):
        return context.to_dict()
    return context


def render_results_json(
    results: list[ProviderResult],
    context: BusinessContext | str | None = None,
    verbose: bool = False,
) -> str:
    """Render results as JSON. Compact by default, verbose adds summary+context."""
    flat = _flatten_results(results, compact=not verbose)
    payload: dict = {"results": flat}

    if verbose:
        available_count = sum(1 for r in flat if r["status"] == "available")
        taken_count = sum(1 for r in flat if r["status"] == "taken")
        unknown_count = sum(1 for r in flat if r["status"] == "unknown")
        payload["summary"] = {
            "total": len(flat),
            "available": available_count,
            "taken": taken_count,
            "unknown": unknown_count,
        }
        ctx_payload = _context_payload(context)
        if ctx_payload:
            payload["context"] = ctx_payload

    if verbose:
        return json.dumps(payload, cls=_Encoder, indent=2)
    return json.dumps(payload, cls=_Encoder, separators=(",", ":"))


def render_results_ndjson(
    results: list[ProviderResult],
    context: BusinessContext | str | None = None,
) -> str:
    """Render results as newline-delimited JSON (one object per line)."""
    flat = _flatten_results(results, compact=True)
    lines = [json.dumps(entry, cls=_Encoder, separators=(",", ":")) for entry in flat]
    return "\n".join(lines)


def render_results_csv(
    results: list[ProviderResult],
    context: BusinessContext | str | None = None,
) -> str:
    """Render results as CSV with header row."""
    flat = _flatten_results(results, compact=False)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["type", "provider", "query", "status", "error"])
    for entry in flat:
        writer.writerow([
            entry["type"],
            entry.get("provider", ""),
            entry["query"],
            entry["status"],
            entry.get("error", ""),
        ])
    return buf.getvalue().rstrip("\n")


def render_results_table(
    console: Console,
    results: list[ProviderResult],
    context: BusinessContext | str | None = None,
) -> None:
    """Render results as a Rich table."""
    if context and hasattr(context, "name_candidates"):
        title = f"Results: {', '.join(context.name_candidates)}"
    elif context:
        title = f"Results: {context}"
    else:
        title = "Results"

    table = Table(title=title, title_style=TABLE_TITLE)
    table.add_column("Check", style=FIELD_LABEL)
    table.add_column("Provider")
    table.add_column("Query")
    table.add_column("Status")
    table.add_column("Notes")

    for r in results:
        if r.check_type == CheckType.DOMAIN and r.details.get("domains"):
            for d in r.details["domains"]:
                avail = d["available"]
                if isinstance(avail, bool):
                    avail = Availability.AVAILABLE if avail else Availability.TAKEN
                else:
                    avail = Availability(avail)
                dl, ds = availability_style(avail)
                relevance = d.get("relevance", "")
                table.add_row(
                    "domain", r.provider_name, d["domain"],
                    styled(dl, ds), relevance,
                )
        else:
            label, st = availability_style(r.available)
            notes = r.error or ""
            if r.details.get("note"):
                notes = r.details["note"]
            relevance = r.details.get("relevance", "")
            if relevance:
                notes = f"{notes}  {relevance}" if notes else relevance
            table.add_row(
                r.check_type.value, r.provider_name, r.query,
                styled(label, st), notes,
            )

    console.print(table)


def render_results(
    results: list[ProviderResult],
    format: str = "table",
    context: BusinessContext | str | None = None,
    console: Console | None = None,
    verbose: bool = False,
) -> str | None:
    """Dispatch to the appropriate renderer based on format."""
    if format == "json":
        return render_results_json(results, context, verbose=verbose)
    elif format == "ndjson":
        return render_results_ndjson(results, context)
    elif format == "csv":
        return render_results_csv(results, context)
    elif format == "table":
        if console is None:
            console = Console()
        render_results_table(console, results, context)
        return None
    else:
        raise ValueError(f"Unknown format: {format}")
