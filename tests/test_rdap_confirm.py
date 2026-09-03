from __future__ import annotations

from unittest.mock import patch

import pytest

from namera.providers.base import Availability
from namera.providers.rdap import RdapProvider


@pytest.mark.asyncio
async def test_rdap_404_is_overridden_when_whois_has_a_record():
    """The .io/.co/.sh/.me bug: a stale RDAP endpoint 404s on a live domain."""
    with patch(
        "namera.providers.rdap._whois_fallback",
        return_value=Availability.TAKEN,
    ):
        assert await RdapProvider._confirm_available("spiral.io") == (
            Availability.TAKEN,
            "whois",
        )


@pytest.mark.asyncio
async def test_rdap_404_stands_when_whois_agrees():
    with patch(
        "namera.providers.rdap._whois_fallback",
        return_value=Availability.AVAILABLE,
    ):
        assert await RdapProvider._confirm_available("spiralsolo.com") == (
            Availability.AVAILABLE,
            "rdap",
        )


@pytest.mark.asyncio
async def test_inconclusive_whois_does_not_overturn_rdap():
    """WHOIS UNKNOWN is not evidence of a registration — RDAP still wins."""
    with patch(
        "namera.providers.rdap._whois_fallback",
        return_value=Availability.UNKNOWN,
    ):
        assert await RdapProvider._confirm_available("spiralsolo.com") == (
            Availability.AVAILABLE,
            "rdap",
        )


@pytest.mark.asyncio
async def test_tld_without_a_whois_server_trusts_rdap():
    assert await RdapProvider._confirm_available("spiral.nexus") == (
        Availability.AVAILABLE,
        "rdap",
    )
