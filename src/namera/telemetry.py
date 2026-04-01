"""Non-blocking session logging to Supabase."""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from namera.scoring.models import RankedName

_TELEMETRY_TIMEOUT = 2.0


def log_session(
    names: list[str],
    ranked: list[RankedName],
    profile: str = "default",
    niche: str | None = None,
) -> None:
    """Best-effort telemetry that never blocks the user-facing CLI path."""
    url = _telemetry_base_url()
    key = _telemetry_api_key()
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

    worker = threading.Thread(
        target=_send_session_log,
        args=(url, key, payload),
        daemon=True,
    )
    worker.start()


def _telemetry_base_url() -> str | None:
    return os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")


def _telemetry_api_key() -> str | None:
    return (
        os.environ.get("SUPABASE_PUBLISHABLE_KEY")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )


def _send_session_log(url: str, key: str, payload: dict) -> None:
    try:
        response = httpx.post(
            f"{url}/rest/v1/namera.sessions",
            headers={
                "apikey": key,
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=payload,
            timeout=_TELEMETRY_TIMEOUT,
        )
        response.raise_for_status()
    except Exception:
        pass
