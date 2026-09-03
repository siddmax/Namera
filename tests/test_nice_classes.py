from __future__ import annotations

from unittest.mock import AsyncMock, patch

import click
import pytest

from namera.cli import _parse_nice_classes
from namera.providers.base import Availability
from namera.providers.trademark_supabase import SupabaseTrademarkProvider


def test_parse_nice_classes():
    assert _parse_nice_classes("9,35,42") == [9, 35, 42]
    assert _parse_nice_classes(None) is None
    assert _parse_nice_classes("") is None


@pytest.mark.parametrize("bad", ["nine", "9,abc", "0", "46"])
def test_parse_nice_classes_rejects_bad_input(bad):
    with pytest.raises(click.BadParameter):
        _parse_nice_classes(bad)


@pytest.mark.asyncio
async def test_class_filter_cannot_clear_a_name_the_dataset_knows():
    """SPIRAL has live class-9 marks; a filtered miss must not read as clear."""
    async def fake_call(client, query, mode="both", threshold=0.3, nice_classes=None):
        if nice_classes:
            return {"exact": {"matches": [], "count": 0, "trademarked": False}}
        return {"exact": {"matches": [{"serial_number": "88560391"}], "count": 1,
                          "trademarked": True}}

    with patch("namera.providers.trademark_supabase._call_api", new=fake_call), \
         patch("namera.providers.trademark_supabase._build_client") as bc:
        bc.return_value.__aenter__ = AsyncMock(return_value=object())
        bc.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await SupabaseTrademarkProvider().check("spiral", nice_classes=[9, 35, 42])

    assert result.available is Availability.UNKNOWN
    assert "no class data" in (result.error or "")


@pytest.mark.asyncio
async def test_genuinely_unknown_name_still_clears_under_a_filter():
    async def fake_call(client, query, mode="both", threshold=0.3, nice_classes=None):
        return {"exact": {"matches": [], "count": 0, "trademarked": False}}

    with patch("namera.providers.trademark_supabase._call_api", new=fake_call), \
         patch("namera.providers.trademark_supabase._build_client") as bc:
        bc.return_value.__aenter__ = AsyncMock(return_value=object())
        bc.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await SupabaseTrademarkProvider().check("calmfirm", nice_classes=[9])

    assert result.available is Availability.AVAILABLE
