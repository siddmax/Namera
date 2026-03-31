"""Non-blocking session logging to Supabase."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from namera.scoring.models import RankedName


def log_session(
    names: list[str],
    ranked: list[RankedName],
    profile: str = "default",
    niche: str | None = None,
) -> None:
    """Fire-and-forget session log to Supabase. Never blocks, never raises."""
    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get(
        "SUPABASE_SERVICE_ROLE_KEY",
        os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", ""),
    )
    if not url or not key:
        return

    top = ranked[0] if ranked else None

    payload = {
        "names": names,
        "niche": niche,
        "profile": profile,
        "top_name": top.name if top else None,
        "top_score": round(top.composite_score, 4) if top else None,
        "num_candidates": len(names),
    }

    try:
        httpx.post(
            f"{url}/rest/v1/namera.sessions",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=payload,
            timeout=5.0,
        )
    except Exception:
        pass  # Never fail the CLI for telemetry
