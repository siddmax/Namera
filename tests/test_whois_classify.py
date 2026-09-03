from __future__ import annotations

from namera.providers.base import Availability
from namera.providers.whois import classify_whois_response

# Trimmed real responses from whois.verisign-grs.com.
TAKEN = """   Domain Name: SOLOSTUDIO.COM
   Registrar: Realtime Register B.V.
   Creation Date: 2000-08-10T20:04:08Z
"""

AVAILABLE = """No match for "SPIRALSOLO.COM".
>>> Last update of whois database: 2026-09-03T00:00:00Z <<<
"""

RATE_LIMITED = """You have exceeded the maximum allowed number of requests.
Please try again later.
"""


def test_registered_domain_is_taken():
    assert classify_whois_response(TAKEN) is Availability.TAKEN


def test_explicit_no_match_is_available():
    assert classify_whois_response(AVAILABLE) is Availability.AVAILABLE


def test_rate_limited_response_is_unknown_not_available():
    """The solostudio.com bug: no record != available."""
    assert classify_whois_response(RATE_LIMITED) is Availability.UNKNOWN


def test_empty_response_is_unknown():
    assert classify_whois_response("") is Availability.UNKNOWN
