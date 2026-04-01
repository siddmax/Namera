"""Tests for the scoring engine, models, normalizers, local signals, and profiles."""

from namera.providers.base import Availability, CheckType, ProviderResult
from namera.scoring.engine import RankingEngine
from namera.scoring.local_signals import (
    compute_local_signals,
    score_length,
    score_pronounceability,
    score_string_features,
)
from namera.scoring.models import RankedName, ScoringProfile, Signal
from namera.scoring.normalizers import (
    normalize_domain,
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
        assert d["score"] == 0.85
        assert "length" in d["signals"]
        assert d["signals"]["length"]["value"] == 0.9


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


class TestComputeLocalSignals:
    def test_returns_three_signals(self):
        signals = compute_local_signals("voxly")
        names = [s.name for s in signals]
        assert "length" in names
        assert "pronounceability" in names
        assert "string_features" in names


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
            provider_name="domain-api",
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
    def test_available_no_similarity(self):
        result = ProviderResult(
            check_type=CheckType.TRADEMARK,
            provider_name="uspto",
            query="voxly",
            available=Availability.AVAILABLE,
            details={"matches": [], "match_count": 0},
        )
        signals = normalize_trademark(result)
        by_name = {s.name: s for s in signals}
        assert by_name["trademark"].value == 1.0

    def test_taken_with_similarity(self):
        result = ProviderResult(
            check_type=CheckType.TRADEMARK,
            provider_name="trademark-similarity",
            query="apple",
            available=Availability.TAKEN,
            details={"max_similarity": 0.95},
        )
        signals = normalize_trademark(result)
        by_name = {s.name: s for s in signals}
        assert by_name["trademark"].value == 0.0
        assert by_name["trademark_clearance"].value <= 0.1


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
