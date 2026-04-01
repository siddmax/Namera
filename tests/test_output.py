from __future__ import annotations

import csv
import io
import json

import pytest
from click.testing import CliRunner
from rich.console import Console

from namera.output import (
    render_results,
    render_results_csv,
    render_results_json,
    render_results_ndjson,
    render_results_table,
)
from namera.providers.base import Availability, CheckType, ProviderResult


@pytest.fixture
def domain_result() -> ProviderResult:
    return ProviderResult(
        check_type=CheckType.DOMAIN,
        provider_name="dns",
        query="example",
        available=Availability.TAKEN,
        details={
            "domains": [
                {"domain": "example.com", "available": "taken"},
                {"domain": "example.net", "available": "available"},
            ]
        },
    )


@pytest.fixture
def whois_result() -> ProviderResult:
    return ProviderResult(
        check_type=CheckType.WHOIS,
        provider_name="whois",
        query="example.com",
        available=Availability.TAKEN,
        details={"raw": "Domain Name: EXAMPLE.COM\n..."},
    )


@pytest.fixture
def trademark_result() -> ProviderResult:
    return ProviderResult(
        check_type=CheckType.TRADEMARK,
        provider_name="trademark-stub",
        query="example",
        available=Availability.UNKNOWN,
        details={"note": "Stub provider"},
    )


@pytest.fixture
def error_result() -> ProviderResult:
    return ProviderResult(
        check_type=CheckType.WHOIS,
        provider_name="whois",
        query="example.xyz",
        available=Availability.UNKNOWN,
        error="No WHOIS server known for .xyz",
    )


@pytest.fixture
def all_results(domain_result, whois_result, trademark_result):
    return [domain_result, whois_result, trademark_result]


# --- JSON tests ---


class TestRenderResultsJson:
    def test_returns_valid_json(self, all_results):
        output = render_results_json(all_results)
        parsed = json.loads(output)
        assert "results" in parsed

    def test_compact_by_default(self, whois_result):
        output = render_results_json([whois_result])
        assert "\n" not in output.strip()
        parsed = json.loads(output)
        assert "type" in parsed["results"][0]
        assert "status" in parsed["results"][0]
        assert "summary" not in parsed
        assert "context" not in parsed

    def test_compact_omits_null_errors(self, whois_result):
        output = render_results_json([whois_result])
        parsed = json.loads(output)
        assert "error" not in parsed["results"][0]

    def test_verbose_includes_summary_and_context(self, all_results):
        output = render_results_json(all_results, context="myquery", verbose=True)
        parsed = json.loads(output)
        assert "summary" in parsed
        assert parsed["context"] == "myquery"
        assert "\n" in output

    def test_flattens_domain_results(self, domain_result):
        output = render_results_json([domain_result])
        parsed = json.loads(output)
        assert len(parsed["results"]) == 2
        assert parsed["results"][0]["query"] == "example.com"
        assert parsed["results"][1]["query"] == "example.net"

    def test_excludes_raw_whois(self, whois_result):
        output = render_results_json([whois_result], verbose=True)
        raw_str = json.dumps(json.loads(output))
        assert "Domain Name: EXAMPLE.COM" not in raw_str

    def test_no_context_key_when_none(self, all_results):
        output = render_results_json(all_results, verbose=True)
        parsed = json.loads(output)
        assert "context" not in parsed


# --- NDJSON tests ---


class TestRenderResultsNdjson:
    def test_each_line_is_valid_json(self, all_results):
        output = render_results_ndjson(all_results)
        lines = output.strip().split("\n")
        for line in lines:
            parsed = json.loads(line)
            assert "type" in parsed
            assert "query" in parsed

    def test_correct_number_of_lines(self, all_results):
        output = render_results_ndjson(all_results)
        lines = output.strip().split("\n")
        # 2 domain sub-results + 1 whois + 1 trademark = 4
        assert len(lines) == 4

    def test_flattens_domains(self, domain_result):
        output = render_results_ndjson([domain_result])
        lines = output.strip().split("\n")
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["query"] == "example.com"

    def test_no_summary_line(self, all_results):
        """NDJSON should not have a summary/envelope line."""
        output = render_results_ndjson(all_results)
        lines = output.strip().split("\n")
        for line in lines:
            parsed = json.loads(line)
            assert "results" not in parsed

    def test_error_result(self, error_result):
        output = render_results_ndjson([error_result])
        parsed = json.loads(output.strip())
        assert parsed["error"] == "No WHOIS server known for .xyz"


# --- CSV tests ---


class TestRenderResultsCsv:
    def test_has_header_row(self, all_results):
        output = render_results_csv(all_results)
        reader = csv.reader(io.StringIO(output))
        header = next(reader)
        assert header == ["type", "provider", "query", "status", "error"]

    def test_correct_columns(self, whois_result):
        output = render_results_csv([whois_result])
        reader = csv.reader(io.StringIO(output))
        header = next(reader)
        row = next(reader)
        assert len(row) == len(header)
        assert row[0] == "whois"
        assert row[1] == "whois"
        assert row[2] == "example.com"
        assert row[3] == "taken"

    def test_correct_number_of_data_rows(self, all_results):
        output = render_results_csv(all_results)
        reader = csv.reader(io.StringIO(output))
        rows = list(reader)
        # header + 2 domain + 1 whois + 1 trademark = 5
        assert len(rows) == 5

    def test_flattens_domains(self, domain_result):
        output = render_results_csv([domain_result])
        reader = csv.reader(io.StringIO(output))
        rows = list(reader)
        # header + 2 domain entries
        assert len(rows) == 3
        assert rows[1][2] == "example.com"
        assert rows[2][2] == "example.net"

    def test_error_in_csv(self, error_result):
        output = render_results_csv([error_result])
        reader = csv.reader(io.StringIO(output))
        next(reader)  # skip header
        row = next(reader)
        assert row[4] == "No WHOIS server known for .xyz"


# --- Table tests ---


class TestRenderResultsTable:
    def test_renders_without_error(self, all_results):
        c = Console(file=io.StringIO(), width=120)
        render_results_table(c, all_results)
        output = c.file.getvalue()
        assert len(output) > 0

    def test_renders_with_context(self, all_results):
        c = Console(file=io.StringIO(), width=120)
        render_results_table(c, all_results, context="testquery")
        output = c.file.getvalue()
        assert "testquery" in output


# --- Dispatcher tests ---


class TestRenderResultsDispatcher:
    def test_dispatches_json(self, all_results):
        output = render_results(all_results, format="json")
        assert output is not None
        parsed = json.loads(output)
        assert "results" in parsed

    def test_dispatches_ndjson(self, all_results):
        output = render_results(all_results, format="ndjson")
        assert output is not None
        lines = output.strip().split("\n")
        for line in lines:
            json.loads(line)

    def test_dispatches_csv(self, all_results):
        output = render_results(all_results, format="csv")
        assert output is not None
        assert "type,provider,query,status,error" in output

    def test_dispatches_table(self, all_results):
        c = Console(file=io.StringIO(), width=120)
        output = render_results(all_results, format="table", console=c)
        assert output is None
        table_text = c.file.getvalue()
        assert len(table_text) > 0

    def test_table_creates_default_console(self, all_results):
        # Should not raise even without a console arg
        output = render_results(all_results, format="table")
        assert output is None

    def test_unknown_format_raises(self, all_results):
        with pytest.raises(ValueError, match="Unknown format"):
            render_results(all_results, format="xml")


class TestCliFormatOption:
    def test_search_format_option(self):
        from namera.cli import main

        runner = CliRunner()
        result = runner.invoke(
            main, ["trademark", "zzz-nonexistent-test", "--format", "json"]
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "results" in parsed
