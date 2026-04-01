from __future__ import annotations

from dataclasses import dataclass, field

# Common prefixes and suffixes for domain name generation
COMMON_PREFIXES = [
    "get", "try", "use", "go", "my", "the", "hey",
]

COMMON_SUFFIXES = [
    "app", "hq", "io", "ly", "fy", "hub", "lab", "labs", "dev",
]

# Smaller affix set for low-cost post-check variation retries.
FALLBACK_VARIATION_PREFIXES = COMMON_PREFIXES[:5]
FALLBACK_VARIATION_SUFFIXES = COMMON_SUFFIXES[:2]
MAX_FALLBACK_VARIATION_KEYWORDS = 5


@dataclass
class ComposerConfig:
    """Configuration for domain name permutation."""

    keywords: list[str] = field(default_factory=list)
    prefixes: list[str] = field(default_factory=list)
    suffixes: list[str] = field(default_factory=list)
    tlds: list[str] = field(default_factory=lambda: ["com"])
    max_length: int = 63  # max domain label length per DNS spec
    use_common_prefixes: bool = False
    use_common_suffixes: bool = False
    include_affix_combinations: bool = True
    max_keywords: int | None = None


def compose_labels(config: ComposerConfig) -> list[str]:
    """Generate a deduplicated list of candidate labels without TLDs."""
    prefixes = list(config.prefixes)
    suffixes = list(config.suffixes)

    if config.use_common_prefixes:
        prefixes = _dedup(prefixes + COMMON_PREFIXES)
    if config.use_common_suffixes:
        suffixes = _dedup(suffixes + COMMON_SUFFIXES)

    labels: set[str] = set()
    keywords = config.keywords
    if config.max_keywords is not None:
        keywords = keywords[: config.max_keywords]

    for keyword in keywords:
        keyword = keyword.lower().strip()
        if not keyword:
            continue

        if len(keyword) <= config.max_length:
            labels.add(keyword)

        for prefix in prefixes:
            label = f"{prefix}{keyword}"
            if len(label) <= config.max_length:
                labels.add(label)

        for suffix in suffixes:
            label = f"{keyword}{suffix}"
            if len(label) <= config.max_length:
                labels.add(label)

        if config.include_affix_combinations:
            for prefix in prefixes:
                for suffix in suffixes:
                    label = f"{prefix}{keyword}{suffix}"
                    if len(label) <= config.max_length:
                        labels.add(label)

    return sorted(labels)


def compose_fallback_variations(base_names: list[str]) -> list[str]:
    """Generate low-cost fallback variations for taken base names."""
    return compose_labels(
        ComposerConfig(
            keywords=base_names,
            prefixes=FALLBACK_VARIATION_PREFIXES,
            suffixes=FALLBACK_VARIATION_SUFFIXES,
            include_affix_combinations=False,
            max_keywords=MAX_FALLBACK_VARIATION_KEYWORDS,
        )
    )


def compose(config: ComposerConfig) -> list[str]:
    """Generate domain permutations from config.

    Returns a deduplicated list of domain names (e.g., ["getfoo.com", "foohub.io"]).

    The cartesian product is: (prefixes x keywords x suffixes) x tlds
    Where each combo of prefix+keyword+suffix forms the domain label.
    Keywords with no prefix/suffix are always included.
    """
    labels = compose_labels(config)

    domains: list[str] = []
    seen: set[str] = set()
    for label in labels:
        for tld in config.tlds:
            domain = f"{label}.{tld}"
            if domain not in seen:
                seen.add(domain)
                domains.append(domain)

    return domains


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        lower = item.lower().strip()
        if lower and lower not in seen:
            seen.add(lower)
            result.append(lower)
    return result
