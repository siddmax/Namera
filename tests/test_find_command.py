import json

from click.testing import CliRunner

from namera.cli import main
from namera.providers.base import Availability, CheckType, ProviderResult


def _stub_find_results(names: list[str]) -> list[ProviderResult]:
    results: list[ProviderResult] = []
    for name in names:
        results.extend([
            ProviderResult(
                check_type=CheckType.DOMAIN,
                provider_name="rdap",
                query=name,
                candidate_name=name,
                available=Availability.AVAILABLE,
                details={"domains": [{"domain": f"{name}.com", "available": "available"}]},
            ),
            ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="uspto",
                query=name,
                candidate_name=name,
                available=Availability.AVAILABLE,
                details={"matches": [], "match_count": 0},
            ),
        ])
    return results


class TestFindCommand:
    def test_find_with_context_json_output(self, monkeypatch):
        runner = CliRunner()
        monkeypatch.setattr(
            "namera.cli.run_checks_multi_batched",
            lambda names, check_types, **kwargs: _async_return(_stub_find_results(names)),
        )
        ctx = json.dumps({
            "name_candidates": ["voxly"],
            "niche": "tech",
            "preferred_tlds": ["com"],
        })
        result = runner.invoke(main, ["find", "--json", "--context", ctx])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "results" in parsed
        assert "summary" not in parsed
        assert "context" not in parsed

    def test_find_no_names_errors(self):
        runner = CliRunner()
        ctx = json.dumps({"niche": "tech"})
        result = runner.invoke(main, ["find", "--json", "--context", ctx])
        assert result.exit_code == 1

    def test_find_invalid_json_errors(self):
        runner = CliRunner()
        result = runner.invoke(main, ["find", "--json", "--context", "{bad"])
        assert result.exit_code == 1

    def test_find_rejects_non_object_json(self):
        runner = CliRunner()
        result = runner.invoke(main, ["find", "--json", "--context", "[]"])
        assert result.exit_code == 1

    def test_find_rejects_string_name_candidates(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["find", "--json", "--context", '{"name_candidates":"foo"}'],
        )
        assert result.exit_code == 1

    def test_find_stdin_pipe(self, monkeypatch):
        runner = CliRunner()
        monkeypatch.setattr(
            "namera.cli.run_checks_multi_batched",
            lambda names, check_types, **kwargs: _async_return(_stub_find_results(names)),
        )
        ctx = json.dumps({
            "name_candidates": ["voxly"],
            "preferred_tlds": ["com"],
        })
        result = runner.invoke(main, ["find", "--json"], input=ctx)
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "results" in parsed

    def test_find_table_output(self, monkeypatch):
        runner = CliRunner()
        monkeypatch.setattr(
            "namera.cli.run_checks_multi_batched",
            lambda names, check_types, **kwargs: _async_return(_stub_find_results(names)),
        )
        ctx = json.dumps({
            "name_candidates": ["voxly"],
            "preferred_tlds": ["com"],
        })
        result = runner.invoke(main, ["find", "--format", "table", "--context", ctx])
        assert result.exit_code == 0
        assert "voxly" in result.output


class TestExistingCommandsJson:
    def test_domain_json(self, monkeypatch):
        runner = CliRunner()
        monkeypatch.setattr(
            "namera.cli.run_checks",
            lambda name, check_types, **kwargs: _async_return([
                ProviderResult(
                    check_type=CheckType.DOMAIN,
                    provider_name="rdap",
                    query=name,
                    candidate_name=name,
                    available=Availability.AVAILABLE,
                    details={"domains": [{"domain": f"{name}.com", "available": "available"}]},
                )
            ]),
        )
        result = runner.invoke(main, ["domain", "voxly", "--json", "--tlds", "com"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "results" in parsed

    def test_search_json(self, monkeypatch):
        runner = CliRunner()
        monkeypatch.setattr(
            "namera.cli.run_checks",
            lambda name, check_types, **kwargs: _async_return([
                ProviderResult(
                    check_type=CheckType.DOMAIN,
                    provider_name="rdap",
                    query=name,
                    candidate_name=name,
                    available=Availability.AVAILABLE,
                    details={"domains": [{"domain": f"{name}.com", "available": "available"}]},
                )
            ]),
        )
        result = runner.invoke(main, ["search", "voxly", "--json", "--tlds", "com"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "results" in parsed

    def test_rank_rejects_non_object_json(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rank", "--json", "--context", "[]"])
        assert result.exit_code == 1

    def test_rank_rejects_string_name_candidates(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rank", "--json", "--context", '{"name_candidates":"foo"}'])
        assert result.exit_code == 1


async def _async_return(value):
    return value
