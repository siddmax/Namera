from __future__ import annotations

from dataclasses import dataclass, field

# Common prefixes and suffixes for domain name generation
COMMON_PREFIXES = [
    "get", "try", "use", "go", "my", "the", "hey",
]

COMMON_SUFFIXES = [
    "app", "hq", "io", "ly", "fy", "hub", "lab", "labs", "dev",
]


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


def compose(config: ComposerConfig) -> list[str]:
    """Generate domain permutations from config.

    Returns a deduplicated list of domain names (e.g., ["getfoo.com", "foohub.io"]).

    The cartesian product is: (prefixes x keywords x suffixes) x tlds
    Where each combo of prefix+keyword+suffix forms the domain label.
    Keywords with no prefix/suffix are always included.
    """
    prefixes = list(config.prefixes)
    suffixes = list(config.suffixes)

    if config.use_common_prefixes:
        prefixes = _dedup(prefixes + COMMON_PREFIXES)
    if config.use_common_suffixes:
        suffixes = _dedup(suffixes + COMMON_SUFFIXES)

    labels: set[str] = set()
    for keyword in config.keywords:
        keyword = keyword.lower().strip()
        if not keyword:
            continue

        # Base: just the keyword
        bases = [keyword]

        # Prefix combos
        for p in prefixes:
            bases.append(f"{p}{keyword}")

        # Suffix combos
        for s in suffixes:
            bases.append(f"{keyword}{s}")

        # Prefix + suffix combos
        for p in prefixes:
            for s in suffixes:
                bases.append(f"{p}{keyword}{s}")

        for base in bases:
            if len(base) <= config.max_length:
                labels.add(base)

    # Generate full domain names
    domains: list[str] = []
    seen: set[str] = set()
    for label in sorted(labels):
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
