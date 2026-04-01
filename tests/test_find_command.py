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
            ProviderResult(
                check_type=CheckType.SOCIAL,
                provider_name="social",
                query=name,
                candidate_name=name,
                available=Availability.AVAILABLE,
                details={"platforms": {"twitter": "available", "github": "available"}},
            ),
        ])
    return results


class TestFindCommand:
    def test_find_with_context_json_output(self, monkeypatch):
        runner = CliRunner()
        monkeypatch.setattr(
            "namera.pipeline.run_checks_multi_batched",
            lambda names, check_types, **kwargs: _async_return(_stub_find_results(names)),
        )
        ctx = json.dumps({
            "name_candidates": ["voxly"],
            "niche": "tech",
            "preferred_tlds": ["com"],
        })
        result = runner.invoke(main, ["find", "--format", "json", "--context", ctx])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "ranked" in parsed
        assert "summary" in parsed
        assert len(parsed["ranked"]) == 1
        assert parsed["ranked"][0]["name"] == "voxly"
        assert "score" in parsed["ranked"][0]
        assert "domains" in parsed["ranked"][0]

    def test_find_no_names_errors(self):
        runner = CliRunner()
        ctx = json.dumps({"niche": "tech"})
        result = runner.invoke(main, ["find", "--format", "json", "--context", ctx])
        assert result.exit_code != 0

    def test_find_invalid_json_errors(self):
        runner = CliRunner()
        result = runner.invoke(main, ["find", "--format", "json", "--context", "{bad"])
        assert result.exit_code != 0

    def test_find_rejects_non_object_json(self):
        runner = CliRunner()
        result = runner.invoke(main, ["find", "--format", "json", "--context", "[]"])
        assert result.exit_code != 0

    def test_find_rejects_string_name_candidates(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["find", "--format", "json", "--context", '{"name_candidates":"foo"}'],
        )
        assert result.exit_code != 0

    def test_find_stdin_pipe(self, monkeypatch):
        runner = CliRunner()
        monkeypatch.setattr(
            "namera.pipeline.run_checks_multi_batched",
            lambda names, check_types, **kwargs: _async_return(_stub_find_results(names)),
        )
        ctx = json.dumps({
            "name_candidates": ["voxly"],
            "preferred_tlds": ["com"],
        })
        result = runner.invoke(main, ["find", "--format", "json"], input=ctx)
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "ranked" in parsed
        assert "summary" in parsed

    def test_find_table_output(self, monkeypatch):
        runner = CliRunner()
        monkeypatch.setattr(
            "namera.pipeline.run_checks_multi_batched",
            lambda names, check_types, **kwargs: _async_return(_stub_find_results(names)),
        )
        ctx = json.dumps({
            "name_candidates": ["voxly"],
            "preferred_tlds": ["com"],
        })
        result = runner.invoke(main, ["find", "--format", "table", "--context", ctx])
        assert result.exit_code == 0
        assert "voxly" in result.output


    def test_find_keywords_compose(self, monkeypatch):
        """Keywords in context should auto-generate candidates via compose."""
        runner = CliRunner()
        captured_names = []

        def _mock_checks(names, check_types, **kwargs):
            captured_names.extend(names)
            return _async_return(_stub_find_results(names))

        monkeypatch.setattr("namera.pipeline.run_checks_multi_batched", _mock_checks)
        ctx = json.dumps({
            "keywords": ["flux"],
            "preferred_tlds": ["com"],
        })
        result = runner.invoke(main, ["find", "--format", "json", "--context", ctx])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "ranked" in parsed
        # Should have generated names from keywords (flux, getflux, fluxapp, etc.)
        assert len(captured_names) > 1
        assert "flux" in captured_names

    def test_find_keywords_merged_with_candidates(self, monkeypatch):
        """Keywords + explicit candidates should be merged without duplicates."""
        runner = CliRunner()
        captured_names = []

        def _mock_checks(names, check_types, **kwargs):
            captured_names.extend(names)
            return _async_return(_stub_find_results(names))

        monkeypatch.setattr("namera.pipeline.run_checks_multi_batched", _mock_checks)
        ctx = json.dumps({
            "name_candidates": ["flux"],
            "keywords": ["flux"],
            "preferred_tlds": ["com"],
        })
        result = runner.invoke(main, ["find", "--format", "json", "--context", ctx])
        assert result.exit_code == 0
        # "flux" should appear only once despite being in both fields
        assert captured_names.count("flux") == 1

    def test_find_respects_explicit_checks(self, monkeypatch):
        runner = CliRunner()
        captured: list[CheckType] = []

        def _mock_checks(names, check_types, **kwargs):
            captured.extend(check_types)
            return _async_return(_stub_find_results(names))

        monkeypatch.setattr("namera.pipeline.run_checks_multi_batched", _mock_checks)
        ctx = json.dumps({
            "name_candidates": ["flux"],
            "checks": ["domain", "trademark"],
            "preferred_tlds": ["com"],
        })
        result = runner.invoke(main, ["find", "--format", "json", "--context", ctx])
        assert result.exit_code == 0
        # Social is always injected for ranking determinism
        assert CheckType.DOMAIN in captured
        assert CheckType.TRADEMARK in captured
        assert CheckType.SOCIAL in captured


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
        result = runner.invoke(main, ["domain", "voxly", "--format", "json", "--tlds", "com"])
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
        result = runner.invoke(main, ["search", "voxly", "--format", "json", "--tlds", "com"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "results" in parsed

    def test_rank_rejects_non_object_json(self):
        runner = CliRunner()
        result = runner.invoke(main, ["rank", "--format", "json", "--context", "[]"])
        assert result.exit_code != 0

    def test_rank_rejects_string_name_candidates(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["rank", "--format", "json", "--context", '{"name_candidates":"foo"}'],
        )
        assert result.exit_code != 0

    def test_rank_respects_context_checks(self, monkeypatch):
        runner = CliRunner()
        captured: list[CheckType] = []

        def _mock_checks(names, check_types, **kwargs):
            captured.extend(check_types)
            return _async_return(_stub_find_results(names))

        monkeypatch.setattr("namera.cli.run_checks_multi_batched", _mock_checks)
        ctx = json.dumps({
            "name_candidates": ["voxly"],
            "checks": ["domain", "trademark"],
            "preferred_tlds": ["com"],
        })
        result = runner.invoke(main, ["rank", "--format", "json", "--context", ctx])
        assert result.exit_code == 0
        assert captured == [CheckType.DOMAIN, CheckType.TRADEMARK]


async def _async_return(value):
    return value


# ---------------------------------------------------------------------------
# BDD-style regression tests for ranking policy
# ---------------------------------------------------------------------------

def _stub_results_with_trademark(
    names: list[str],
    *,
    exact_taken: set[str] | None = None,
    fuzzy_taken: set[str] | None = None,
) -> list[ProviderResult]:
    """Build provider results with configurable trademark verdicts."""
    exact_taken = exact_taken or set()
    fuzzy_taken = fuzzy_taken or set()
    results: list[ProviderResult] = []
    for name in names:
        # Domain: all available
        results.append(ProviderResult(
            check_type=CheckType.DOMAIN,
            provider_name="rdap",
            query=name,
            candidate_name=name,
            available=Availability.AVAILABLE,
            details={"domains": [{"domain": f"{name}.com", "available": "available"}]},
        ))
        # Exact trademark
        exact_avail = Availability.TAKEN if name in exact_taken else Availability.AVAILABLE
        results.append(ProviderResult(
            check_type=CheckType.TRADEMARK,
            provider_name="uspto",
            query=name,
            candidate_name=name,
            available=exact_avail,
            details={
                "matches": [{"mark": name.upper()}] if name in exact_taken else [],
                "match_count": 1 if name in exact_taken else 0,
            },
        ))
        # Fuzzy trademark
        fuzzy_avail = Availability.TAKEN if name in fuzzy_taken else Availability.AVAILABLE
        results.append(ProviderResult(
            check_type=CheckType.TRADEMARK,
            provider_name="trademark-similarity",
            query=name,
            candidate_name=name,
            available=fuzzy_avail,
            details={"max_similarity": 0.98 if name in fuzzy_taken else 0.0},
        ))
        # Social: all available
        results.append(ProviderResult(
            check_type=CheckType.SOCIAL,
            provider_name="social",
            query=name,
            candidate_name=name,
            available=Availability.AVAILABLE,
            details={"platforms": {"twitter": "available", "github": "available"}},
        ))
    return results


class TestTrademarkExactConflictPolicy:
    """Given an exact trademark hit and fuzzy miss, the name is rejected."""

    def test_exact_conflict_rejects_name_in_fintech_profile(self, monkeypatch):
        runner = CliRunner()
        monkeypatch.setattr(
            "namera.pipeline.run_checks_multi_batched",
            lambda names, check_types, **kw: _async_return(
                _stub_results_with_trademark(
                    names, exact_taken={"apple"}, fuzzy_taken=set(),
                )
            ),
        )
        ctx = json.dumps({
            "name_candidates": ["apple", "voxly"],
            "niche": "fintech",
            "preferred_tlds": ["com"],
            "scoring_profile": "fintech",
        })
        result = runner.invoke(main, ["find", "--format", "json", "--context", ctx])
        assert result.exit_code == 0, result.output
        parsed = json.loads(result.output)

        ranked_names = [r["name"] for r in parsed["ranked"]]
        filtered_names = [f["name"] for f in parsed.get("filtered", [])]

        # "apple" has exact trademark conflict — must be filtered out
        assert "apple" in filtered_names, (
            f"apple should be filtered by fintech trademark gate, "
            f"got ranked={ranked_names} filtered={filtered_names}"
        )
        assert "voxly" in ranked_names


class TestRankingDeterminismAcrossModes:
    """Given identical checks, JSON and table ranking are identical."""

    def test_json_and_table_produce_same_rank_order(self, monkeypatch):
        runner = CliRunner()
        stub = _stub_results_with_trademark(
            ["alpha", "bravo", "charlie"],
            exact_taken=set(),
            fuzzy_taken=set(),
        )
        monkeypatch.setattr(
            "namera.pipeline.run_checks_multi_batched",
            lambda names, check_types, **kw: _async_return(stub),
        )
        ctx = json.dumps({
            "name_candidates": ["alpha", "bravo", "charlie"],
            "preferred_tlds": ["com"],
        })

        # JSON mode
        json_result = runner.invoke(main, ["find", "--format", "json", "--context", ctx])
        assert json_result.exit_code == 0, json_result.output
        json_ranked = [r["name"] for r in json.loads(json_result.output)["ranked"]]

        # Direct scoring (same path as table mode)
        from namera.core import rank_candidates, resolve_profile

        profile = resolve_profile("default")
        ranked = rank_candidates(["alpha", "bravo", "charlie"], stub, profile)
        table_ranked = [r.name for r in ranked if not r.filtered_out]

        assert json_ranked == table_ranked, (
            f"JSON order {json_ranked} != table order {table_ranked}"
        )


class TestSemanticallyRelevantNamesOutrank:
    """Given a fintech brief, semantically relevant names outrank irrelevant ones."""

    def test_name_matching_description_ranks_higher(self, monkeypatch):
        runner = CliRunner()
        monkeypatch.setattr(
            "namera.pipeline.run_checks_multi_batched",
            lambda names, check_types, **kw: _async_return(
                _stub_results_with_trademark(names),
            ),
        )
        ctx = json.dumps({
            "name_candidates": ["splitpay", "zephyr"],
            "description": "An app to split bills and expenses with friends",
            "niche": "fintech",
            "preferred_tlds": ["com"],
        })
        result = runner.invoke(main, ["find", "--format", "json", "--context", ctx])
        assert result.exit_code == 0, result.output
        parsed = json.loads(result.output)
        ranked = parsed["ranked"]

        # splitpay matches "split" + "bills" / "expenses" keywords
        scores = {r["name"]: r["score"] for r in ranked}
        assert scores["splitpay"] > scores["zephyr"], (
            f"splitpay ({scores['splitpay']}) should outrank zephyr ({scores['zephyr']}) "
            f"for a 'split expenses' brief"
        )


class TestDistinctivenessScoring:
    """Given a common word name, distinctiveness score is penalized."""

    def test_common_word_scores_lower_than_invented(self):
        from namera.scoring.local_signals import score_distinctiveness

        cloud = score_distinctiveness("cloud")
        voxly = score_distinctiveness("voxly")
        assert voxly.value > cloud.value, (
            f"invented 'voxly' ({voxly.value}) should outscore common word "
            f"'cloud' ({cloud.value})"
        )

    def test_descriptive_suffix_penalized(self):
        from namera.scoring.local_signals import score_distinctiveness

        payment = score_distinctiveness("payment")
        payvo = score_distinctiveness("payvo")
        assert payvo.value > payment.value, (
            f"fanciful 'payvo' ({payvo.value}) should outscore descriptive "
            f"'payment' ({payment.value})"
        )
