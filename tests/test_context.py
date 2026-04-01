import json

import pytest

from namera.context import DEFAULT_TLDS, BusinessContext
from namera.providers.base import CheckType


class TestBusinessContext:
    def test_from_dict_full(self):
        data = {
            "name_candidates": ["neopay", "zestmoney"],
            "niche": "fintech",
            "industry": "financial services",
            "description": "A payment app",
            "target_audience": "millennials",
            "location": "US",
            "preferred_tlds": ["com", "io"],
            "name_style": "short",
            "checks": ["domain", "whois"],
        }
        ctx = BusinessContext.from_dict(data)
        assert ctx.name_candidates == ["neopay", "zestmoney"]
        assert ctx.niche == "fintech"
        assert ctx.preferred_tlds == ["com", "io"]
        assert ctx.checks == ["domain", "whois"]

    def test_from_dict_partial(self):
        ctx = BusinessContext.from_dict({"name_candidates": ["test"]})
        assert ctx.name_candidates == ["test"]
        assert ctx.niche is None
        assert ctx.preferred_tlds is None

    def test_from_dict_ignores_unknown_keys(self):
        ctx = BusinessContext.from_dict({"name_candidates": ["x"], "unknown_field": "ignored"})
        assert ctx.name_candidates == ["x"]
        assert not hasattr(ctx, "unknown_field")

    def test_from_json(self):
        j = '{"name_candidates": ["foo"], "niche": "tech"}'
        ctx = BusinessContext.from_json(j)
        assert ctx.name_candidates == ["foo"]
        assert ctx.niche == "tech"

    def test_from_json_invalid(self):
        with pytest.raises(json.JSONDecodeError):
            BusinessContext.from_json("not json")

    def test_from_json_requires_object(self):
        with pytest.raises(TypeError, match="JSON object"):
            BusinessContext.from_json('["foo"]')

    def test_name_candidates_must_be_list(self):
        with pytest.raises(TypeError, match="name_candidates"):
            BusinessContext.from_dict({"name_candidates": "foo"})

    def test_weight_overrides_must_be_numeric(self):
        with pytest.raises(TypeError, match="weight_overrides values"):
            BusinessContext.from_dict({
                "name_candidates": ["foo"],
                "weight_overrides": {"domain_com": "high"},
            })

    def test_to_dict_drops_none(self):
        ctx = BusinessContext(name_candidates=["test"], niche="fintech")
        d = ctx.to_dict()
        assert "niche" in d
        assert "industry" not in d
        assert "preferred_tlds" not in d

    def test_to_dict_drops_empty_list(self):
        ctx = BusinessContext()
        d = ctx.to_dict()
        assert "name_candidates" not in d


class TestResolveTlds:
    def test_explicit_tlds(self):
        ctx = BusinessContext(preferred_tlds=["xyz", "app"])
        assert ctx.resolve_tlds() == ["xyz", "app"]

    def test_niche_based_fintech(self):
        ctx = BusinessContext(niche="fintech")
        tlds = ctx.resolve_tlds()
        assert "com" in tlds
        assert "finance" in tlds

    def test_niche_based_case_insensitive(self):
        ctx = BusinessContext(niche="FinTech Startup")
        tlds = ctx.resolve_tlds()
        assert "finance" in tlds

    def test_fallback_defaults(self):
        ctx = BusinessContext()
        assert ctx.resolve_tlds() == DEFAULT_TLDS

    def test_unknown_niche_falls_back(self):
        ctx = BusinessContext(niche="underwater basket weaving")
        assert ctx.resolve_tlds() == DEFAULT_TLDS


class TestResolveCheckTypes:
    def test_all_by_default(self):
        ctx = BusinessContext()
        types = ctx.resolve_check_types()
        assert CheckType.DOMAIN in types
        assert CheckType.WHOIS in types
        assert CheckType.TRADEMARK in types

    def test_explicit_checks(self):
        ctx = BusinessContext(checks=["domain", "trademark"])
        types = ctx.resolve_check_types()
        assert types == [CheckType.DOMAIN, CheckType.TRADEMARK]

    def test_invalid_checks_raise(self):
        ctx = BusinessContext(checks=["bogus"])
        with pytest.raises(ValueError, match="Invalid checks"):
            ctx.resolve_check_types()

    def test_case_insensitive(self):
        ctx = BusinessContext(checks=["DOMAIN", "Whois"])
        types = ctx.resolve_check_types()
        assert CheckType.DOMAIN in types
        assert CheckType.WHOIS in types
