from __future__ import annotations

import threading

from namera.scoring.models import RankedName
from namera.telemetry import _send_session_log, log_session


def test_log_session_basic(monkeypatch):
    calls: list[dict] = []
    thread_daemons: list[bool] = []
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("NAMERA_TELEMETRY_DISABLED", raising=False)

    def fake_send(payload: dict) -> None:
        calls.append(payload)

    class ImmediateThread:
        def __init__(self, *, target, args, daemon):
            self._target = target
            self._args = args
            self.daemon = daemon
            thread_daemons.append(daemon)

        def start(self):
            self._target(*self._args)

    monkeypatch.setattr("namera.telemetry._send_session_log", fake_send)
    monkeypatch.setattr(threading, "Thread", ImmediateThread)

    log_session(
        ["voxly"],
        [RankedName(name="voxly", composite_score=0.9)],
        "default",
        "tech",
    )

    assert calls
    assert calls[0]["names"] == ["voxly"]
    assert calls[0]["top_name"] == "voxly"
    assert calls[0]["niche"] == "tech"
    assert calls[0]["num_candidates"] == 1
    assert thread_daemons == [False]


def test_log_session_disabled_under_pytest(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_telemetry.py::test_log_session_disabled")
    monkeypatch.setattr("namera.telemetry._send_session_log", lambda payload: calls.append(payload))

    log_session(
        ["voxly"],
        [RankedName(name="voxly", composite_score=0.9)],
        "default",
        "tech",
    )

    assert calls == []


def test_log_session_disabled_in_ci(monkeypatch):
    calls: list[dict] = []
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("CI", "true")
    monkeypatch.setattr("namera.telemetry._send_session_log", lambda payload: calls.append(payload))

    log_session(
        ["voxly"],
        [RankedName(name="voxly", composite_score=0.9)],
        "default",
        "tech",
    )

    assert calls == []


def test_log_session_respects_explicit_opt_out(monkeypatch):
    calls: list[dict] = []
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("NAMERA_TELEMETRY_DISABLED", "1")
    monkeypatch.setattr("namera.telemetry._send_session_log", lambda payload: calls.append(payload))

    log_session(
        ["voxly"],
        [RankedName(name="voxly", composite_score=0.9)],
        "default",
        "tech",
    )

    assert calls == []



def test_send_session_log_swallows_errors(monkeypatch):
    class Response:
        def raise_for_status(self):
            raise RuntimeError("boom")

    monkeypatch.setattr("namera.telemetry.httpx.post", lambda *args, **kwargs: Response())
    # Should not raise — errors are swallowed
    _send_session_log({"niche": "tech", "top_name": "voxly"})
