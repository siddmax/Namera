"""Namera MCP server — exposes name availability checks to AI agents.

Uses the Model Context Protocol (MCP) over stdio transport so agents like
Claude Code, ChatGPT, and Codex can call Namera tools directly.

Install: pip install namera[mcp]
Run:     namera-mcp
"""

from __future__ import annotations

import sys


def _check_mcp_dependency():
    try:
        import mcp  # noqa: F401
    except ImportError:
        print(
            "Error: MCP support requires the 'mcp' package.\n"
            "Install it with: pip install namera[mcp]",
            file=sys.stderr,
        )
        sys.exit(1)


_check_mcp_dependency()

import asyncio
import json
import logging
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from namera.context import BusinessContext
from namera.core import check_and_rank, check_single, resolve_profile
from namera.providers.base import Availability, CheckType, ProviderResult
from namera.ranking_display import build_find_json
from namera.results import group_results_by_candidate

logger = logging.getLogger(__name__)

mcp_server = FastMCP(
    "namera",
    instructions=(
        "Check name availability across domains, trademarks, and social handles. "
        "Scores and ranks name candidates for startups and projects."
    ),
)


def _serialize_result(r: ProviderResult) -> dict:
    """Convert a ProviderResult to a JSON-serializable dict."""
    return {
        "check_type": r.check_type.value if hasattr(r.check_type, "value") else str(r.check_type),
        "provider": r.provider_name,
        "query": r.query,
        "available": r.available.value if hasattr(r.available, "value") else str(r.available),
        "details": r.details or {},
        "error": r.error,
    }


def _make_warnings(results: list[ProviderResult]) -> list[dict]:
    """Extract warnings from results that errored or returned UNKNOWN."""
    warnings = []
    for r in results:
        if r.error:
            warnings.append({
                "provider": r.provider_name,
                "error": r.error,
                "recoverable": "timed out" in (r.error or "").lower(),
            })
    return warnings


@mcp_server.tool()
async def check_name(
    name: str,
    checks: list[str] | None = None,
    tlds: list[str] | None = None,
) -> str:
    """Check a single name's availability across domains, trademarks, and social handles.

    Args:
        name: The name to check (e.g., "voxly", "acmepay").
        checks: Which checks to run. Options: "domain", "whois", "trademark", "social".
                Defaults to ["domain", "whois", "trademark"].
        tlds: Which TLDs to check for domain availability. Defaults to ["com", "net", "org", "io", "dev"].

    Returns JSON with provider results and any warnings for failed checks.
    """
    from namera.providers import register_all
    register_all()

    if not name or not name.strip():
        return json.dumps({"error": "Name is required", "results": []})

    name = name.strip().lower()
    check_map = {
        "domain": CheckType.DOMAIN,
        "whois": CheckType.WHOIS,
        "trademark": CheckType.TRADEMARK,
        "social": CheckType.SOCIAL,
    }
    check_types = []
    if checks:
        for c in checks:
            ct = check_map.get(c.lower())
            if ct:
                check_types.append(ct)
    if not check_types:
        check_types = [CheckType.DOMAIN, CheckType.WHOIS, CheckType.TRADEMARK]

    tld_list = tlds or ["com", "net", "org", "io", "dev"]

    results = await check_single(name, check_types, tlds=tld_list)
    warnings = _make_warnings(results)

    response = {
        "name": name,
        "results": [_serialize_result(r) for r in results],
    }
    if warnings:
        response["warnings"] = warnings

    return json.dumps(response)


@mcp_server.tool()
async def find_names(
    context: str,
) -> str:
    """Check multiple name candidates with business context, score, and rank them.

    Args:
        context: JSON string with business context. Required field: "name_candidates" (list of names).
                 Optional: "niche", "description", "preferred_tlds", "checks", "scoring_profile",
                 "weight_overrides", "keywords", "target_audience", "location", "name_style".

    Returns JSON with ranked results, filtered names, and summary.
    """
    try:
        ctx_data = json.loads(context)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}", "ranked": []})

    try:
        ctx = BusinessContext.from_dict(ctx_data)
    except (TypeError, ValueError) as e:
        return json.dumps({"error": f"Invalid context: {e}", "ranked": []})

    if not ctx.name_candidates and not ctx.keywords:
        return json.dumps({
            "error": "No name_candidates or keywords provided",
            "ranked": [],
        })

    results, ranked = await check_and_rank(ctx)

    tlds = ctx.resolve_tlds()
    profile = resolve_profile(ctx.scoring_profile or "default", ctx.weight_overrides)

    from namera.filters import get_trademark_risk_names
    risky_names = get_trademark_risk_names(results)

    payload = build_find_json(ranked, tlds, profile, ctx, risky_names or None)
    return json.dumps(payload)


def main():
    """Entry point for namera-mcp console script."""
    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    main()
