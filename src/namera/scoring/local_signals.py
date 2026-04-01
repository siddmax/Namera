"""Local string-analysis signals — zero network, zero cost, <1ms."""

from __future__ import annotations

import re

from namera.scoring.models import Signal

# Vowels including contextual y
_VOWELS = set("aeiou")
_CONSONANTS = set("bcdfghjklmnpqrstvwxyz")

# Common English digraphs that function as a single phonetic unit
_DIGRAPHS = {"sh", "ch", "th", "ph", "wh", "ck", "ng", "qu", "gh"}


def _is_contextual_vowel_y(name: str, pos: int) -> bool:
    """Return True when 'y' at *pos* acts as a vowel.

    y is a vowel when: not word-initial AND preceded by a consonant.
    Examples: lyft (y=vowel), rhythm (y=vowel), yes (y=consonant), yak (y=consonant).
    """
    if pos == 0:
        return False
    prev = name[pos - 1].lower()
    return prev in _CONSONANTS


def _build_phonetic_pattern(name: str) -> str:
    """Build a CV pattern that handles contextual y and digraphs."""
    lower = name.lower()
    pattern = []
    i = 0
    while i < len(lower):
        ch = lower[i]

        # Check for digraphs (two chars → single consonant unit)
        if i + 1 < len(lower) and lower[i : i + 2] in _DIGRAPHS:
            pattern.append("C")
            i += 2
            continue

        if ch == "y":
            if _is_contextual_vowel_y(lower, i):
                pattern.append("V")
            else:
                pattern.append("C")
        elif ch in _VOWELS:
            pattern.append("V")
        elif ch in _CONSONANTS:
            pattern.append("C")
        # Skip non-alpha characters
        i += 1

    return "".join(pattern)


def _estimate_syllables(name: str) -> int:
    """Rough syllable count based on vowel groups."""
    lower = name.lower()
    # Treat y as vowel in non-initial position
    vowel_chars = set("aeiou")
    count = 0
    prev_vowel = False
    for i, ch in enumerate(lower):
        is_v = ch in vowel_chars or (ch == "y" and _is_contextual_vowel_y(lower, i))
        if is_v and not prev_vowel:
            count += 1
        prev_vowel = is_v
    return max(1, count)


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
    """Score pronounceability using enhanced CV-pattern analysis.

    Handles contextual y (lyft=CVCC not CCCC), common digraphs (sh, th, ch as
    single units), and uses softer penalties for consonant clusters.
    """
    lower = name.lower()
    if not lower or not lower.isalpha():
        return Signal(name="pronounceability", value=0.3, raw=lower, source="local")

    pattern = _build_phonetic_pattern(lower)
    if not pattern:
        return Signal(name="pronounceability", value=0.3, raw=lower, source="local")

    score = 1.0

    # Reward alternating CV patterns
    alternations = sum(
        1 for i in range(1, len(pattern)) if pattern[i] != pattern[i - 1]
    )
    alt_ratio = alternations / max(len(pattern) - 1, 1)
    score *= 0.4 + 0.6 * alt_ratio

    # Penalize consonant clusters — softer than before
    clusters = re.findall(r"C{3,}", pattern)
    if clusters:
        longest = max(len(c) for c in clusters)
        if longest == 3:
            score *= 0.8  # mild penalty for 3-consonant cluster
        else:
            score *= max(0.3, 1.0 - (longest - 2) * 0.15)

    # Penalize no vowels
    if "V" not in pattern:
        score *= 0.2

    # Reward starting with a consonant (more natural)
    if pattern and pattern[0] == "C":
        score *= 1.05

    # Reward vowel ratio between 25-55% (widened range)
    vowel_ratio = pattern.count("V") / len(pattern)
    if 0.25 <= vowel_ratio <= 0.55:
        score *= 1.05
    elif vowel_ratio < 0.15 or vowel_ratio > 0.75:
        score *= 0.8

    # Bonus for 2-3 syllables (optimal for brand names)
    syllables = _estimate_syllables(lower)
    if syllables in (2, 3):
        score *= 1.08

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


def score_distinctiveness(name: str) -> Signal:
    """Score name distinctiveness — penalizes generic, common, and composed names.

    Combines:
    1. Composer affix penalty (get-, try-, -app, -hub, etc.)
    2. Common English word penalty (entity ambiguity / SEO collision)
    3. Descriptive/generic suffix penalty (-ment, -tion, -ing patterns)
    """
    from namera.composer import COMMON_PREFIXES, COMMON_SUFFIXES

    lower = name.lower()
    penalty = 0.0

    # 1. Composer affix penalty (only 3+ char affixes to avoid false positives)
    for prefix in COMMON_PREFIXES:
        if len(prefix) >= 3 and lower.startswith(prefix) and len(lower) > len(prefix) + 2:
            penalty += 0.25
            break

    for suffix in COMMON_SUFFIXES:
        if len(suffix) >= 3 and lower.endswith(suffix) and len(lower) > len(suffix) + 2:
            penalty += 0.25
            break

    # 2. Common word penalty — names that ARE common words face SEO/entity collision
    if lower in _COMMON_WORDS:
        penalty += 0.30

    # 3. Descriptive/generic suffix penalty (per USPTO: descriptive marks are weak)
    generic_suffixes = ("ment", "tion", "ness", "able", "ible", "ings")
    if any(lower.endswith(s) for s in generic_suffixes) and len(lower) > 6:
        penalty += 0.15

    return Signal(
        name="distinctiveness",
        value=max(0.0, 1.0 - penalty),
        raw=lower,
        source="local",
    )


# ~1000 most common English words that would cause entity/SEO collision.
# Names matching these face ambiguity: "spark" competes with Apache Spark, etc.
_COMMON_WORDS = frozenset("""
able about above accept across act add age ago agree air all allow also always
among amount and animal another answer any appear apple area arm around art ask
at away back bad bank base be beat beauty because become bed begin behind believe
below best better between big bird bit black blood blue board body bone book
born both box boy brain break bring brother build burn business but buy by call
came can capital car care carry case catch cause center century certain chair
chance change charge check child children choice choose church circle city claim
class clean clear close cloud cold color come common company complete contain
control cool copy corner cost could count country course cover cross cry cup
current cut dance dark data daughter day dead deal dear decide deep degree design
develop die different difficult direct discover do doctor does dog dollar door
double down draw dream dress drink drive drop dry during each ear early earth
east eat edge effect egg eight either else employ end energy engine enough enter
even evening ever every example except excite exercise expect experience explain
eye face fact fair fall family famous far farm fast father feel feet few field
fight fill final find fine finger finish fire first fish fit five flat floor
flower fly follow food foot for force foreign forest forget form forward four
free fresh friend from front fruit full fun game garden gate gather general
gentle get girl give glad glass go god gold gone good got govern grand grass
great green grew ground group grow guess gun hair half hand happen happy hard hat
have head hear heart heat heavy help her here high hill him his hold hole home
hope horse hot hotel hour house how hundred hunt hurry hurt idea if imagine
important inch include increase industry inside instead interest into iron island
join joy jump just justice keep key kill kind king knew knock know land language
large last late laugh law lay lead learn least leave left less let letter level
lie life lift light like line list listen little live long look lose lot love low
machine made main make man many map mark market master matter may mean measure
meat meet member mention middle might mile milk million mind mine mint minute miss
modern moment money month moon more morning most mother mountain mouth move much
music must name nation nature near necessary need never new news next nice night
nine noise nor north nose not note nothing notice now number object observe ocean
offer office often oil old once one only open operate opinion order other our out
outside over own page paint pair paper part particular party pass past pattern pay
peace people percent perfect perhaps period person pick piece place plain plan
plant play please point poor position possible power practice prepare present
press pretty print private probably problem produce program promise protect prove
provide public pull purpose push put quarter question quick quiet quite race rain
raise range reach read ready real reason receive record red remember repeat reply
report rest result return rich ride right ring rise river road rock roll room
round rule run safe said sail salt same sand sat save saw say sea seat second
seed seem self sell send sentence serve set seven several shall shape share sharp
she shine ship shirt short should shoulder shout show shut side sight sign silver
simple since sing sit six size skin sleep small smell smile smoke snow soft soil
some son song soon sort sound south space speak special speed spend spoke spring
square stage stand star start state stay step still stock stone stood stop store
story straight strange street strong student study such sudden sugar suggest suit
summer sun supply sure surprise sweet swim table tail take talk tall teach team
tell ten test thank thick thin thing think third those though thought three throw
tie time tiny together told tomorrow tone took top touch toward town trade train
travel tree true trust try turn type uncle under unit until up upon use usual
valley value very visit voice wait walk wall want war warm wash watch water wave
way wear weather week weight well went were west western what wheel when where
which while white whole wide wife will win wind window winter wire wise wish with
woman wonder wood word work world would write wrong year yet young
""".split())


def compute_local_signals(name: str) -> list[Signal]:
    """Compute all local signals for a name."""
    return [
        score_length(name),
        score_pronounceability(name),
        score_string_features(name),
        score_distinctiveness(name),
    ]
