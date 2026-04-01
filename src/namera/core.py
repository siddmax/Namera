"""Programmatic API for Namera — usable without Click CLI."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from namera.context import BusinessContext
from namera.pipeline import run_discovery
from namera.providers.base import CheckType, ProviderResult
from namera.results import group_results_by_candidate
from namera.runner import run_checks
from namera.scoring.engine import RankingEngine
from namera.scoring.models import RankedName, ScoringProfile
from namera.scoring.profiles import get_profile


def resolve_profile(
    profile_name: str = "default",
    weight_overrides: dict[str, float] | None = None,
) -> ScoringProfile:
    """Load a scoring profile and apply optional weight overrides."""
    profile = get_profile(profile_name)
    if weight_overrides:
        merged = {**profile.weights, **weight_overrides}
        profile = ScoringProfile(
            name=f"{profile.name}+overrides",
            weights=merged,
            filters=profile.filters,
            description=profile.description,
        )
    return profile


def rank_candidates(
    name_list: Sequence[str],
    results: list[ProviderResult],
    profile: ScoringProfile,
    context: BusinessContext | None = None,
) -> list[RankedName]:
    """Group results by candidate and rank them with the given profile."""
    candidates = group_results_by_candidate(name_list, results)
    engine = RankingEngine(profile)
    return engine.rank(candidates, context=context)


async def check_single(
    name: str,
    check_types: list[CheckType],
    **kwargs,
) -> list[ProviderResult]:
    """Run all provider checks for a single name."""
    return await run_checks(name, check_types, **kwargs)


async def check_and_rank(
    ctx: BusinessContext,
    concurrency: int = 15,
    timeout: float = 15.0,
) -> tuple[list[ProviderResult], list[RankedName]]:
    """Full pipeline: run checks for all candidates, then rank.

    Returns (results, ranked) tuple.
    """
    from namera.providers import register_all
    register_all()

    if not ctx.name_candidates and not ctx.keywords:
        return [], []
    discovery = await run_discovery(
        ctx,
        concurrency=concurrency,
        timeout=timeout,
    )

    profile_name = ctx.scoring_profile or "default"
    profile = resolve_profile(profile_name, ctx.weight_overrides)
    ranked = rank_candidates(discovery.candidates, discovery.results, profile, context=ctx)

    return discovery.results, ranked


def check_and_rank_sync(
    ctx: BusinessContext,
    concurrency: int = 15,
    timeout: float = 15.0,
) -> tuple[list[ProviderResult], list[RankedName]]:
    """Synchronous wrapper around check_and_rank."""
    return asyncio.run(check_and_rank(ctx, concurrency, timeout))
