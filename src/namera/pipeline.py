from __future__ import annotations

from dataclasses import dataclass

from namera.composer import ComposerConfig, compose_fallback_variations, compose_labels
from namera.context import BusinessContext
from namera.filters import get_trademark_risk_names
from namera.providers.base import CheckType, ProviderResult
from namera.results import candidate_names_without_available_domains
from namera.runner import run_checks_multi_batched


@dataclass
class DiscoveryRun:
    context: BusinessContext
    tlds: list[str]
    check_types: list[CheckType]
    candidates: list[str]
    results: list[ProviderResult]
    risky_names: list[str]


def _merge_candidates(explicit: list[str], generated: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for candidate in [*explicit, *generated]:
        normalized = candidate.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(normalized)
    return merged


def _candidate_keys(candidates: list[str]) -> set[str]:
    return {candidate.lower() for candidate in candidates}


def compose_context_candidates(ctx: BusinessContext, tlds: list[str]) -> list[str]:
    """Merge explicit candidates with keyword-driven composer output."""
    generated: list[str] = []
    if ctx.keywords:
        generated = compose_labels(
            ComposerConfig(
                keywords=ctx.keywords,
                tlds=tlds,
                use_common_prefixes=True,
                use_common_suffixes=True,
            )
        )
    return _merge_candidates(ctx.name_candidates, generated)


async def run_discovery(
    ctx: BusinessContext,
    *,
    concurrency: int,
    timeout: float,
    include_variations: bool = True,
) -> DiscoveryRun:
    """Run the shared discovery pipeline used by CLI and programmatic API."""
    tlds = ctx.resolve_tlds()
    check_types = ctx.resolve_check_types()

    # Social checks must always run so ranking is invariant across output modes.
    if CheckType.SOCIAL not in check_types:
        check_types.append(CheckType.SOCIAL)

    candidates = compose_context_candidates(ctx, tlds)

    if not candidates:
        return DiscoveryRun(ctx, tlds, check_types, [], [], [])

    results = await run_checks_multi_batched(
        candidates,
        check_types,
        concurrency=concurrency,
        timeout=timeout,
        tlds=tlds,
    )

    if include_variations:
        taken = candidate_names_without_available_domains(results, tlds)
        existing_candidates = _candidate_keys(candidates)
        variations = _merge_candidates(
            [],
            [
                name
                for name in compose_fallback_variations(taken)
                if name.lower() not in existing_candidates
            ],
        )
        if variations:
            variation_results = await run_checks_multi_batched(
                variations,
                check_types,
                concurrency=concurrency,
                timeout=timeout,
                tlds=tlds,
            )
            candidates.extend(variations)
            results.extend(variation_results)

    ctx.name_candidates = candidates
    risky_names = get_trademark_risk_names(results)
    return DiscoveryRun(ctx, tlds, check_types, candidates, results, risky_names)
