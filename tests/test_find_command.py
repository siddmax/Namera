import json

from click.testing import CliRunner

from namera.cli import main


class TestFindCommand:
    def test_find_with_context_json_output(self):
        runner = CliRunner()
        ctx = json.dumps({
            "name_candidates": ["xyznonexistent12345"],
            "niche": "tech",
            "preferred_tlds": ["com"],
        })
        result = runner.invoke(main, ["find", "--json", "--context", ctx])
        # Exit 0 = all checks OK, 2 = partial failure (e.g. trademark unconfigured)
        assert result.exit_code in (0, 2)
        parsed = json.loads(result.output)
        assert "results" in parsed
        # Compact by default: no summary or context
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

    def test_find_stdin_pipe(self):
        runner = CliRunner()
        ctx = json.dumps({
            "name_candidates": ["xyznonexistent12345"],
            "preferred_tlds": ["com"],
        })
        result = runner.invoke(main, ["find", "--json"], input=ctx)
        assert result.exit_code in (0, 2)
        parsed = json.loads(result.output)
        assert "results" in parsed

    def test_find_table_output(self):
        runner = CliRunner()
        ctx = json.dumps({
            "name_candidates": ["xyznonexistent12345"],
            "preferred_tlds": ["com"],
        })
        result = runner.invoke(main, ["find", "--format", "table", "--context", ctx])
        assert result.exit_code in (0, 2)
        assert "xyznonexistent12345" in result.output


class TestExistingCommandsJson:
    def test_domain_json(self):
        runner = CliRunner()
        result = runner.invoke(main, ["domain", "xyznonexistent12345", "--json", "--tlds", "com"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "results" in parsed

    def test_search_json(self):
        runner = CliRunner()
        result = runner.invoke(main, ["search", "xyznonexistent12345", "--json", "--tlds", "com"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "results" in parsed
