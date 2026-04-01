from __future__ import annotations

import json

from click.testing import CliRunner

from namera.cli import main
from namera.providers.base import Availability, CheckType, ProviderResult


def test_compose_check_uses_runner(monkeypatch):
    runner = CliRunner()
    captured: dict = {}

    def _mock_checks(names, check_types, **kwargs):
        captured["names"] = list(names)
        captured["check_types"] = list(check_types)
        captured["kwargs"] = kwargs
        return _async_return([
            ProviderResult(
                check_type=CheckType.DOMAIN,
                provider_name="rdap",
                query="flux",
                candidate_name="flux",
                available=Availability.AVAILABLE,
                details={"domains": [{"domain": "flux.com", "available": "available"}]},
            )
        ])

    monkeypatch.setattr("namera.cli.run_checks_multi_batched", _mock_checks)

    result = runner.invoke(main, ["compose", "flux", "--check", "--format", "json"])

    assert result.exit_code == 0, result.output
    assert captured["names"] == ["flux"]
    assert captured["check_types"] == [CheckType.DOMAIN]
    assert captured["kwargs"]["tlds"] == ["com"]
    parsed = json.loads(result.output)
    assert parsed["results"][0]["query"] == "flux.com"


async def _async_return(value):
    return value
