"""Tests for the naming agent utilities."""

from namera.agent import _extract_names


def test_extract_names_json_block():
    text = '```json\n{"names": ["Volo", "Trekr", "Nexo"]}\n```'
    assert _extract_names(text) == ["Volo", "Trekr", "Nexo"]


def test_extract_names_inline_json():
    text = '{"names": ["Alpha", "Beta"]}'
    assert _extract_names(text) == ["Alpha", "Beta"]


def test_extract_names_no_json():
    text = "Here are some clarifying questions for you."
    assert _extract_names(text) is None


def test_extract_names_with_surrounding_text():
    text = 'Here are your names:\n```json\n{"names": ["Zap", "Bolt"]}\n```\nLet me know!'
    assert _extract_names(text) == ["Zap", "Bolt"]
