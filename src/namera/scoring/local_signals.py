"""Local string-analysis signals — zero network, zero cost, <1ms."""

from __future__ import annotations

import re

from namera.scoring.models import Signal

# Consonant-Vowel pattern for pronounceability
_VOWELS = set("aeiou")
_CONSONANTS = set("bcdfghjklmnpqrstvwxyz")


def score_length(name: str) -> Signal:
    """Score name length. Optimal range: 4-8 characters.

    4-8 chars = 1.0, penalty increases outside that range.
    Based on research: consumer recall drops 78% past 12 characters.
    """
    n = len(name)
    if 4 <= n <= 8:
        score = 1.0
    elif n == 3 or n == 9:
        score = 0.8
    elif n == 2 or n == 10:
        score = 0.6
    elif n == 11 or n == 12:
        score = 0.4
    elif n == 1:
        score = 0.2
    else:
        score = max(0.1, 1.0 - (n - 8) * 0.08)

    return Signal(name="length", value=score, raw=n, source="local")


def score_pronounceability(name: str) -> Signal:
    """Score pronounceability using CV-pattern analysis.

    CVCV patterns (like 'Uber', 'Nike', 'Lyft') score highest.
    Consonant clusters and unusual patterns score lower.
    """
    lower = name.lower()
    if not lower or not lower.isalpha():
        return Signal(name="pronounceability", value=0.3, raw=lower, source="local")

    # Build CV pattern
    pattern = ""
    for ch in lower:
        if ch in _VOWELS:
            pattern += "V"
        elif ch in _CONSONANTS:
            pattern += "C"

    if not pattern:
        return Signal(name="pronounceability", value=0.3, raw=lower, source="local")

    score = 1.0

    # Reward alternating CV patterns
    alternations = sum(
        1 for i in range(1, len(pattern)) if pattern[i] != pattern[i - 1]
    )
    alt_ratio = alternations / max(len(pattern) - 1, 1)
    score *= 0.4 + 0.6 * alt_ratio

    # Penalize consonant clusters > 2
    clusters = re.findall(r"C{3,}", pattern)
    if clusters:
        longest = max(len(c) for c in clusters)
        score *= max(0.3, 1.0 - (longest - 2) * 0.2)

    # Penalize no vowels
    if "V" not in pattern:
        score *= 0.2

    # Reward starting with a consonant (more natural)
    if pattern and pattern[0] == "C":
        score *= 1.05

    # Reward vowel ratio between 30-50%
    vowel_ratio = pattern.count("V") / len(pattern)
    if 0.3 <= vowel_ratio <= 0.5:
        score *= 1.05
    elif vowel_ratio < 0.2 or vowel_ratio > 0.7:
        score *= 0.8

    return Signal(
        name="pronounceability",
        value=min(1.0, score),
        raw=pattern,
        source="local",
    )


def score_string_features(name: str) -> Signal:
    """Score general string quality: character diversity, digit-free, etc."""
    lower = name.lower()
    score = 1.0

    # Penalize digits
    digit_count = sum(1 for c in lower if c.isdigit())
    if digit_count:
        score *= max(0.3, 1.0 - digit_count * 0.15)

    # Penalize hyphens/underscores
    special = sum(1 for c in lower if c in "-_")
    if special:
        score *= max(0.4, 1.0 - special * 0.2)

    # Reward unique character ratio (not too repetitive)
    if lower:
        unique_ratio = len(set(lower)) / len(lower)
        if unique_ratio < 0.4:
            score *= 0.7  # too repetitive like "aaaa"

    # Penalize all-consonant or all-vowel
    has_vowel = any(c in _VOWELS for c in lower if c.isalpha())
    has_consonant = any(c in _CONSONANTS for c in lower if c.isalpha())
    if not has_vowel or not has_consonant:
        score *= 0.4

    return Signal(name="string_features", value=min(1.0, score), raw=lower, source="local")


def compute_local_signals(name: str) -> list[Signal]:
    """Compute all local signals for a name."""
    return [
        score_length(name),
        score_pronounceability(name),
        score_string_features(name),
    ]
