from __future__ import annotations

from namera.presets import (
    TLD_PRESETS,
    get_all_preset_names,
    get_preset,
    resolve_tld_input,
)


def test_get_preset_returns_tlds_for_known_preset():
    result = get_preset("tech")
    assert result == ["com", "io", "dev", "ai", "app", "tech", "cloud", "code"]


def test_get_preset_returns_tlds_for_popular():
    result = get_preset("popular")
    assert result == ["com", "net", "org", "io", "co", "dev"]


def test_get_preset_returns_none_for_unknown():
    result = get_preset("nonexistent-preset")
    assert result is None


def test_get_preset_is_case_insensitive():
    assert get_preset("Tech") == get_preset("tech")
    assert get_preset("GAMING") == get_preset("gaming")


def test_get_all_preset_names_returns_sorted_list():
    names = get_all_preset_names()
    assert names == sorted(names)
    assert len(names) == len(TLD_PRESETS)


def test_get_all_preset_names_contains_expected():
    names = get_all_preset_names()
    assert "tech" in names
    assert "popular" in names
    assert "startup" in names
    assert "gaming" in names


def test_resolve_tld_input_with_preset_name():
    result = resolve_tld_input("tech")
    assert result == TLD_PRESETS["tech"]


def test_resolve_tld_input_with_comma_separated_tlds():
    result = resolve_tld_input("com,net,org")
    assert result == ["com", "net", "org"]


def test_resolve_tld_input_strips_dots_and_whitespace():
    result = resolve_tld_input(".com, .net , .org")
    assert result == ["com", "net", "org"]


def test_resolve_tld_input_strips_leading_dots():
    result = resolve_tld_input(".io,.dev")
    assert result == ["io", "dev"]


def test_resolve_tld_input_ignores_empty_segments():
    result = resolve_tld_input("com,,net,")
    assert result == ["com", "net"]


def test_all_presets_have_at_least_3_tlds():
    for name, tlds in TLD_PRESETS.items():
        assert len(tlds) >= 3, f"Preset '{name}' has only {len(tlds)} TLDs"


def test_no_duplicate_tlds_within_any_preset():
    for name, tlds in TLD_PRESETS.items():
        assert len(tlds) == len(set(tlds)), (
            f"Preset '{name}' has duplicates: {tlds}"
        )
