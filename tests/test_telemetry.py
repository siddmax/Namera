from __future__ import annotations

import threading

from namera.scoring.models import RankedName
from namera.telemetry import _send_session_log, _telemetry_api_key, log_session


def test_telemetry_prefers_publishable_or_anon_keys(monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role")
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon")

    assert _telemetry_api_key() == "anon"


def test_log_session_is_non_blocking(monkeypatch):
    calls: list[tuple[str, str, dict]] = []

    def fake_send(url: str, key: str, payload: dict) -> None:
        calls.append((url, key, payload))

    class ImmediateThread:
        def __init__(self, *, target, args, daemon):
            self._target = target
            self._args = args
            self.daemon = daemon

        def start(self):
            self._target(*self._args)

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "publishable")
    monkeypatch.setattr("namera.telemetry._send_session_log", fake_send)
    monkeypatch.setattr(threading, "Thread", ImmediateThread)

    log_session(
        ["voxly"],
        [RankedName(name="voxly", composite_score=0.9)],
        "default",
        "tech",
    )

    assert calls
    assert calls[0][1] == "publishable"
    assert calls[0][2]["top_name"] == "voxly"


def test_send_session_log_checks_http_errors(monkeypatch):
    class Response:
        def raise_for_status(self):
            raise RuntimeError("boom")

    monkeypatch.setattr("namera.telemetry.httpx.post", lambda *args, **kwargs: Response())
    _send_session_log("https://example.supabase.co", "publishable", {"names": ["voxly"]})
