"""Tests for the scoring engine, models, normalizers, local signals, and profiles."""

from namera.context import BusinessContext
from namera.providers.base import Availability, CheckType, ProviderResult
from namera.scoring.engine import RankingEngine
from namera.scoring.local_signals import (
    compute_local_signals,
    score_distinctiveness,
    score_length,
    score_pronounceability,
    score_string_features,
)
from namera.scoring.models import RankedName, ScoringProfile, Signal
from namera.scoring.normalizers import (
    normalize_domain,
    normalize_social,
    normalize_trademark,
    normalize_whois,
)
from namera.scoring.profiles import PROFILES, get_profile, list_profiles

# --- Signal model ---

class TestSignal:
    def test_clamps_value(self):
        s = Signal(name="x", value=1.5)
        assert s.value == 1.0
        s2 = Signal(name="x", value=-0.3)
        assert s2.value == 0.0

    def test_normal_value(self):
        s = Signal(name="x", value=0.7, raw="test", source="dns")
        assert s.value == 0.7
        assert s.source == "dns"


class TestRankedName:
    def test_to_dict(self):
        r = RankedName(
            name="voxly",
            composite_score=0.85,
            signals={"length": Signal(name="length", value=0.9, raw=5, source="local")},
        )
        d = r.to_dict()
        assert d["name"] == "voxly"
        assert d["score"] == 85.0
        assert "length" in d["signals"]
        assert d["signals"]["length"] == 90.0


# --- Local signals ---

class TestScoreLength:
    def test_optimal_range(self):
        for name in ["uber", "lyft", "stripe", "namera"]:
            s = score_length(name)
            assert s.value == 1.0, f"{name} should score 1.0"

    def test_short_penalized(self):
        assert score_length("ab").value < score_length("uber").value

    def test_long_penalized(self):
        assert score_length("verylongbrandname").value < score_length("uber").value


class TestScorePronouncability:
    def test_cvcv_scores_high(self):
        # CVCV pattern names like "uber", "nike"
        s = score_pronounceability("niko")
        assert s.value >= 0.7

    def test_consonant_cluster_penalized(self):
        s = score_pronounceability("strngth")
        assert s.value < score_pronounceability("niko").value

    def test_no_vowels_penalized(self):
        s = score_pronounceability("bcrdf")
        assert s.value < 0.4

    def test_contextual_y_as_vowel(self):
        """'y' after a consonant should be treated as vowel: lyft, rhythm."""
        lyft = score_pronounceability("lyft")
        assert lyft.value > 0.5, f"lyft scored {lyft.value}, expected > 0.5"

    def test_digraph_not_penalized_as_cluster(self):
        """Common digraphs (sh, ch, th) should count as single consonant unit."""
        # "shred" has sh digraph + r — not a 3-consonant cluster
        shred = score_pronounceability("shred")
        # Without digraph handling this would be CCC+V+C, heavily penalized
        assert shred.value > 0.4

    def test_stripe_scores_reasonable(self):
        """Modern tech names shouldn't be underrated."""
        stripe = score_pronounceability("stripe")
        assert stripe.value > 0.4, f"stripe scored {stripe.value}"

    def test_syllable_bonus(self):
        """Names with 2-3 syllables should score higher than 1-syllable."""
        two_syl = score_pronounceability("namera")
        one_syl = score_pronounceability("brand")
        # 2-syllable gets bonus, should be competitive
        assert two_syl.value >= one_syl.value * 0.8


class TestScoreStringFeatures:
    def test_clean_alpha(self):
        s = score_string_features("voxly")
        assert s.value >= 0.8

    def test_digits_penalized(self):
        s = score_string_features("name123")
        assert s.value < score_string_features("namexyz").value

    def test_hyphens_penalized(self):
        s = score_string_features("my-brand")
        assert s.value < score_string_features("mybrand").value


class TestScoreDistinctiveness:
    def test_clean_invented_name(self):
        """Invented names without affixes should score high."""
        s = score_distinctiveness("voxly")
        assert s.value >= 0.7

    def test_common_prefix_penalized(self):
        """Names with composer prefixes should be penalized."""
        assert score_distinctiveness("getflux").value < score_distinctiveness("flux").value

    def test_common_suffix_penalized(self):
        """Names with composer suffixes should be penalized."""
        assert score_distinctiveness("fluxapp").value < score_distinctiveness("flux").value

    def test_common_word_penalized(self):
        """Names that are common English words face entity collision penalty."""
        s = score_distinctiveness("cloud")
        assert s.value < 0.8, f"'cloud' scored {s.value}, expected < 0.8"

    def test_invented_word_no_common_penalty(self):
        """Invented words should not be penalized for common word collision."""
        s = score_distinctiveness("voxly")
        assert s.value >= 0.7

    def test_generic_suffix_penalized(self):
        """Descriptive suffixes like -tion, -ment should be penalized."""
        s = score_distinctiveness("payment")
        assert s.value < score_distinctiveness("payvo").value

    def test_short_names_not_false_positive(self):
        """Short names shouldn't match affix patterns."""
        assert score_distinctiveness("get").value >= 0.7
        assert score_distinctiveness("app").value >= 0.7

    def test_both_prefix_and_suffix(self):
        """Names with both prefix and suffix get double penalty."""
        both = score_distinctiveness("getfluxapp")
        prefix_only = score_distinctiveness("getflux")
        assert both.value < prefix_only.value


class TestComputeLocalSignals:
    def test_returns_four_signals(self):
        signals = compute_local_signals("voxly")
        names = [s.name for s in signals]
        assert len(signals) == 4
        assert "length" in names
        assert "pronounceability" in names
        assert "string_features" in names
        assert "distinctiveness" in names


# --- Normalizers ---

class TestNormalizeDomain:
    def test_available_domains(self):
        result = ProviderResult(
            check_type=CheckType.DOMAIN,
            provider_name="rdap",
            query="voxly",
            available=Availability.AVAILABLE,
            details={"domains": [
                {"domain": "voxly.com", "available": "available"},
                {"domain": "voxly.io", "available": "taken"},
            ]},
        )
        signals = normalize_domain(result)
        by_name = {s.name: s for s in signals}
        assert by_name["domain_com"].value == 1.0
        assert by_name["domain_io"].value == 0.0
        assert by_name["domain_availability"].value == 0.5

    def test_boolean_domain_statuses_are_normalized(self):
        result = ProviderResult(
            check_type=CheckType.DOMAIN,
            provider_name="dns",
            query="voxly",
            available=Availability.AVAILABLE,
            details={"domains": [
                {"domain": "voxly.com", "available": True},
                {"domain": "voxly.io", "available": False},
            ]},
        )
        signals = normalize_domain(result)
        by_name = {s.name: s for s in signals}
        assert by_name["domain_com"].value == 1.0
        assert by_name["domain_io"].value == 0.0
        assert by_name["domain_availability"].value == 0.5


class TestNormalizeWhois:
    def test_available(self):
        result = ProviderResult(
            check_type=CheckType.WHOIS,
            provider_name="whois",
            query="voxly.com",
            available=Availability.AVAILABLE,
        )
        signals = normalize_whois(result)
        assert signals[0].value == 1.0

    def test_taken(self):
        result = ProviderResult(
            check_type=CheckType.WHOIS,
            provider_name="whois",
            query="google.com",
            available=Availability.TAKEN,
        )
        signals = normalize_whois(result)
        assert signals[0].value == 0.0


class TestNormalizeTrademark:
    def test_exact_available(self):
        """Exact provider should emit trademark_exact signal."""
        result = ProviderResult(
            check_type=CheckType.TRADEMARK,
            provider_name="uspto",
            query="voxly",
            available=Availability.AVAILABLE,
            details={"matches": [], "match_count": 0},
        )
        signals = normalize_trademark(result)
        by_name = {s.name: s for s in signals}
        assert by_name["trademark_exact"].value == 1.0
        assert "trademark_fuzzy" not in by_name

    def test_fuzzy_taken_with_similarity(self):
        """Similarity provider should emit trademark_fuzzy + clearance signals."""
        result = ProviderResult(
            check_type=CheckType.TRADEMARK,
            provider_name="trademark-similarity",
            query="apple",
            available=Availability.TAKEN,
            details={"max_similarity": 0.95},
        )
        signals = normalize_trademark(result)
        by_name = {s.name: s for s in signals}
        assert by_name["trademark_fuzzy"].value == 0.0
        assert "trademark_exact" not in by_name
        assert by_name["trademark_clearance"].value <= 0.1


class TestNormalizeSocial:
    def test_per_platform_signals(self):
        result = ProviderResult(
            check_type=CheckType.SOCIAL,
            provider_name="social",
            query="voxly",
            available=Availability.AVAILABLE,
            details={"platforms": {
                "twitter": "available",
                "github": "taken",
            }},
        )
        signals = normalize_social(result)
        by_name = {s.name: s for s in signals}
        assert by_name["social_twitter"].value == 1.0
        assert by_name["social_github"].value == 0.0

    def test_aggregate_signal(self):
        result = ProviderResult(
            check_type=CheckType.SOCIAL,
            provider_name="social",
            query="voxly",
            available=Availability.AVAILABLE,
            details={"platforms": {
                "twitter": "available",
                "github": "taken",
                "instagram": "available",
            }},
        )
        signals = normalize_social(result)
        by_name = {s.name: s for s in signals}
        assert by_name["social_availability"].value == 2.0 / 3.0

    def test_partial_status(self):
        result = ProviderResult(
            check_type=CheckType.SOCIAL,
            provider_name="social",
            query="voxly",
            available=Availability.PARTIAL,
            details={"platforms": {"twitter": "partial"}},
        )
        signals = normalize_social(result)
        by_name = {s.name: s for s in signals}
        assert by_name["social_twitter"].value == 0.5

    def test_empty_platforms(self):
        result = ProviderResult(
            check_type=CheckType.SOCIAL,
            provider_name="social",
            query="voxly",
            available=Availability.UNKNOWN,
            details={"platforms": {}},
        )
        signals = normalize_social(result)
        assert len(signals) == 0


# --- Profiles ---

class TestProfiles:
    def test_default_exists(self):
        assert "default" in PROFILES

    def test_get_profile_returns_default(self):
        p = get_profile("nonexistent")
        assert p.name == "default"

    def test_list_profiles(self):
        names = list_profiles()
        assert "default" in names
        assert "fintech" in names

    def test_weights_are_reasonable(self):
        for name, profile in PROFILES.items():
            total = sum(profile.weights.values())
            assert 0.8 <= total <= 1.2, f"Profile {name} weights sum to {total}"

    def test_all_profiles_have_context_weights(self):
        """All profiles should include context signal weights."""
        for name, profile in PROFILES.items():
            assert "semantic_fit" in profile.weights, f"{name} missing semantic_fit"
            assert "distinctiveness" in profile.weights, f"{name} missing distinctiveness"


# --- Ranking engine ---

class TestRankingEngine:
    def _make_results(self, name: str, com_available: bool, tm_available: bool):
        """Helper to create mock provider results."""
        return [
            ProviderResult(
                check_type=CheckType.DOMAIN,
                provider_name="rdap",
                query=name,
                available=Availability.AVAILABLE if com_available else Availability.TAKEN,
                details={"domains": [
                    {"domain": f"{name}.com",
                     "available": "available" if com_available else "taken"},
                ]},
            ),
            ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="uspto",
                query=name,
                available=Availability.AVAILABLE if tm_available else Availability.TAKEN,
                details={"matches": [], "match_count": 0},
            ),
        ]

    def test_ranks_by_score_descending(self):
        profile = get_profile("default")
        engine = RankingEngine(profile)

        candidates = {
            "goodname": self._make_results("goodname", com_available=True, tm_available=True),
            "badname": self._make_results("badname", com_available=False, tm_available=False),
        }
        ranked = engine.rank(candidates)
        assert ranked[0].name == "goodname"
        assert ranked[0].composite_score > ranked[1].composite_score

    def test_filters_applied(self):
        profile = ScoringProfile(
            name="strict",
            weights={"domain_com": 0.5, "trademark": 0.5},
            filters={"domain_com": 0.5},
        )
        engine = RankingEngine(profile)

        candidates = {
            "available": self._make_results("available", True, True),
            "notavail": self._make_results("notavail", False, True),
        }
        ranked = engine.rank(candidates)
        filtered = [r for r in ranked if r.filtered_out]
        assert len(filtered) == 1
        assert filtered[0].name == "notavail"

    def test_empty_candidates(self):
        engine = RankingEngine(get_profile("default"))
        ranked = engine.rank({})
        assert ranked == []

    def test_single_candidate(self):
        engine = RankingEngine(get_profile("default"))
        candidates = {"solo": self._make_results("solo", True, True)}
        ranked = engine.rank(candidates)
        assert len(ranked) == 1
        assert ranked[0].composite_score > 0


class TestTrademarkSignalPrecedence:
    """P0 regression: exact TAKEN must never be overwritten by fuzzy AVAILABLE."""

    def test_exact_taken_dominates_fuzzy_available(self):
        """When exact says TAKEN and fuzzy says AVAILABLE, aggregate must be TAKEN (0.0)."""
        profile = ScoringProfile(
            name="test",
            weights={"trademark": 1.0},
            filters={"trademark": 0.5},
        )
        engine = RankingEngine(profile)

        # Simulate what the batched runner returns: exact first, then similarity
        results = [
            ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="uspto",
                query="apple",
                available=Availability.TAKEN,
                details={"matches": [{"mark": "APPLE"}], "match_count": 1},
            ),
            ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="trademark-similarity",
                query="apple",
                available=Availability.AVAILABLE,
                details={"max_similarity": 0.1},
            ),
        ]

        candidates = {"apple": results}
        ranked = engine.rank(candidates)

        assert len(ranked) == 1
        r = ranked[0]
        # The conservative aggregate should be min(exact=0.0, fuzzy=1.0) = 0.0
        assert r.signals["trademark"].value == 0.0
        # Should be filtered out by the trademark >= 0.5 filter
        assert r.filtered_out is True

    def test_both_available_means_clear(self):
        """When both exact and fuzzy say AVAILABLE, aggregate should be 1.0."""
        profile = ScoringProfile(
            name="test",
            weights={"trademark": 1.0},
        )
        engine = RankingEngine(profile)

        results = [
            ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="uspto",
                query="voxly",
                available=Availability.AVAILABLE,
                details={"matches": []},
            ),
            ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="trademark-similarity",
                query="voxly",
                available=Availability.AVAILABLE,
                details={"max_similarity": 0.0},
            ),
        ]

        candidates = {"voxly": results}
        ranked = engine.rank(candidates)
        assert ranked[0].signals["trademark"].value == 1.0


class TestContextAwareScoring:
    """P1: Business context should influence ranking."""

    def _make_full_results(self, name: str):
        return [
            ProviderResult(
                check_type=CheckType.DOMAIN,
                provider_name="rdap",
                query=name,
                available=Availability.AVAILABLE,
                details={"domains": [
                    {"domain": f"{name}.com", "available": "available"},
                ]},
            ),
            ProviderResult(
                check_type=CheckType.TRADEMARK,
                provider_name="uspto",
                query=name,
                available=Availability.AVAILABLE,
                details={"matches": []},
            ),
        ]

    def test_semantic_fit_boosts_relevant_name(self):
        """A name matching the business description should score higher."""
        profile = get_profile("default")
        engine = RankingEngine(profile)

        ctx = BusinessContext(
            name_candidates=["splitpay", "voxly"],
            description="An app to split expenses with friends",
        )

        candidates = {
            "splitpay": self._make_full_results("splitpay"),
            "voxly": self._make_full_results("voxly"),
        }
        ranked = engine.rank(candidates, context=ctx)

        by_name = {r.name: r for r in ranked}
        # splitpay matches "split" + "expenses" keywords
        assert by_name["splitpay"].signals["semantic_fit"].value > \
               by_name["voxly"].signals["semantic_fit"].value

    def test_no_context_still_works(self):
        """Ranking without context should work fine (no context signals emitted)."""
        profile = get_profile("default")
        engine = RankingEngine(profile)

        candidates = {"test": self._make_full_results("test")}
        ranked = engine.rank(candidates, context=None)
        assert len(ranked) == 1
        assert "semantic_fit" not in ranked[0].signals
