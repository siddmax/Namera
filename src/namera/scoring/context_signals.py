"""Context-aware scoring signals driven by BusinessContext fields."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from namera.scoring.models import Signal

if TYPE_CHECKING:
    from namera.context import BusinessContext

# Minimal English stopwords for keyword extraction
_STOPWORDS = frozenset(
    "a an the and or but in on at to for of is it that this with from by as "
    "be are was were been has have had do does did will would can could should "
    "may might shall must not no nor so if then than too very just about also "
    "more most other some such only over after before between under through "
    "up out into during each all both few many much how what which who whom "
    "where when while".split()
)

# Suffixes associated with playful/consumer naming
_PLAYFUL_SUFFIXES = ("ly", "ify", "fy", "ie", "ee", "oo", "io")

# Audience keywords mapped to scoring preferences
_ENTERPRISE_KEYWORDS = frozenset(
    "enterprise b2b business corporate professional saas platform".split()
)
_CONSUMER_KEYWORDS = frozenset(
    "consumer gen-z genz teen young millennial social viral tiktok".split()
)
_DEVELOPER_KEYWORDS = frozenset(
    "developer dev engineer devops infrastructure api sdk cli tool".split()
)


def _extract_keywords(text: str) -> set[str]:
    """Extract content words from text, removing stopwords."""
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if len(w) >= 3 and w not in _STOPWORDS}


def compute_context_signals(
    name: str, context: BusinessContext,
) -> list[Signal]:
    """Compute all context-dependent signals for a name."""
    signals: list[Signal] = []

    if context.description:
        signals.append(_score_semantic_fit(name, context.description))

    if context.name_style:
        signals.append(_score_style_fit(name, context.name_style))

    if context.target_audience:
        signals.append(_score_audience_fit(name, context.target_audience))

    return signals


def _score_semantic_fit(name: str, description: str) -> Signal:
    """Score how well a name relates to the business description.

    Uses substring matching: for each keyword extracted from the description,
    check whether it (or a stem of it) appears as a substring of the name.
    """
    keywords = _extract_keywords(description)
    if not keywords:
        return Signal(name="semantic_fit", value=0.5, raw="no keywords", source="context")

    lower_name = name.lower()
    matches = 0

    for kw in keywords:
        # Check if keyword or its first 4+ chars appear in the name
        if kw in lower_name:
            matches += 1
        elif len(kw) >= 4 and kw[:4] in lower_name:
            matches += 0.5

    # Normalize: even 1-2 keyword matches is meaningful
    if matches >= 2:
        score = 1.0
    elif matches >= 1:
        score = 0.75
    elif matches >= 0.5:
        score = 0.5
    else:
        # No match doesn't mean bad — invented names are fine
        score = 0.3

    return Signal(
        name="semantic_fit", value=score,
        raw=f"{matches}/{len(keywords)}", source="context",
    )


def _score_style_fit(name: str, style: str) -> Signal:
    """Score how well a name matches the requested naming style."""
    lower_name = name.lower()
    style_lower = style.lower().strip()
    score = 0.5  # neutral default

    if style_lower == "short":
        n = len(lower_name)
        if n <= 5:
            score = 1.0
        elif n <= 7:
            score = 0.75
        elif n <= 9:
            score = 0.5
        else:
            score = 0.2

    elif style_lower == "invented" or style_lower == "creative":
        # Reward names that don't look like common English words
        # Simple heuristic: unusual letter combos, no common suffixes
        has_unusual = any(
            bigram in lower_name
            for bigram in ("xy", "zz", "xo", "qy", "vx", "kz")
        )
        is_short_punchy = len(lower_name) <= 6 and not lower_name.endswith(("ing", "tion", "ment"))
        if has_unusual:
            score = 0.9
        elif is_short_punchy:
            score = 0.7
        else:
            score = 0.4

    elif style_lower == "descriptive":
        # Reward longer, word-like names
        if len(lower_name) >= 6 and lower_name.isalpha():
            score = 0.8
        else:
            score = 0.4

    return Signal(name="style_fit", value=score, raw=style_lower, source="context")


def _score_audience_fit(name: str, audience: str) -> Signal:
    """Score how well a name fits the target audience."""
    lower_name = name.lower()
    audience_words = _extract_keywords(audience)

    is_enterprise = bool(audience_words & _ENTERPRISE_KEYWORDS)
    is_consumer = bool(audience_words & _CONSUMER_KEYWORDS)
    is_developer = bool(audience_words & _DEVELOPER_KEYWORDS)

    score = 0.5  # neutral

    if is_enterprise:
        # Penalize playful suffixes, reward clean/professional names
        if any(lower_name.endswith(s) for s in _PLAYFUL_SUFFIXES):
            score = 0.3
        elif lower_name.isalpha() and len(lower_name) <= 10:
            score = 0.8
        else:
            score = 0.6

    elif is_consumer:
        # Reward short, catchy names
        if len(lower_name) <= 6:
            score = 0.9
        elif len(lower_name) <= 8:
            score = 0.7
        else:
            score = 0.4

    elif is_developer:
        # Reward concise, technical-sounding names
        if len(lower_name) <= 7 and lower_name.isalpha():
            score = 0.8
        else:
            score = 0.5

    return Signal(name="audience_fit", value=score, raw=audience, source="context")
