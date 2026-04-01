"""Non-blocking session logging via Supabase Edge Function."""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from namera.scoring.models import RankedName

_TELEMETRY_TIMEOUT = 2.0

# Public endpoint — no API key needed (verify_jwt=false on the Edge Function).
_DEFAULT_ENDPOINT = (
    "https://wmnzjmrysnzjthldgffh.supabase.co/functions/v1/session-log"
)
_SESSION_LOG_URL = os.environ.get("NAMERA_SESSION_LOG_URL", _DEFAULT_ENDPOINT)

_TOP_N = 3  # Only send the top-N ranked names, not the full candidate list
_MAX_STORED_NAMES = 25


def log_session(
    names: list[str],
    ranked: list[RankedName],
    profile: str = "default",
    niche: str | None = None,
) -> None:
    """Best-effort telemetry that never blocks the user-facing CLI path."""
    top = ranked[:_TOP_N]

    payload: dict = {
        "names": names[:_MAX_STORED_NAMES],
        "niche": niche,
        "profile": profile,
        "num_candidates": len(names),
        "top_name": top[0].name if top else None,
        "top_score": round(top[0].composite_score * 100, 1) if top else None,
    }

    worker = threading.Thread(
        target=_send_session_log,
        args=(payload,),
        daemon=True,
    )
    worker.start()


def _send_session_log(payload: dict) -> None:
    try:
        response = httpx.post(
            _SESSION_LOG_URL,
            headers={
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=_TELEMETRY_TIMEOUT,
        )
        response.raise_for_status()
    except Exception:
        pass
