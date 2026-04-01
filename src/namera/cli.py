from __future__ import annotations

import asyncio
import json as json_mod
import sys

import click
from rich.console import Console
from rich.table import Table

from namera.context import BusinessContext
from namera.core import rank_candidates, resolve_profile
from namera.output import render_results, render_results_json, render_results_table
from namera.permutations import generate_permutation_names, names_all_domains_taken
from namera.presets import TLD_PRESETS, resolve_tld_input
from namera.providers import register_all
from namera.providers.base import Availability, CheckType
from namera.ranking_display import compact_ranked, render_find_ranked, render_ranked_table
from namera.runner import run_checks, run_checks_multi_batched
from namera.session import InteractiveSession
from namera.theme import HEADING, WARNING, availability_style, styled

console = Console()

# --- Exit codes ---
EXIT_OK = 0
EXIT_INPUT_ERROR = 1
EXIT_PARTIAL_FAILURE = 2
EXIT_NETWORK_ERROR = 3


def _is_json_mode(output_format: str) -> bool:
    return output_format in ("json", "ndjson")


def _error_exit(
    code: int,
    error_key: str,
    message: str,
    fix: str | None = None,
    *,
    json_mode: bool = False,
) -> None:
    """Print an error (structured JSON if in json mode) and exit."""
    if json_mode:
        payload: dict = {"error": error_key, "message": message}
        if fix:
            payload["fix"] = fix
        click.echo(json_mod.dumps(payload), err=True)
    else:
        msg = f"Error: {message}"
        if fix:
            msg += f"\nFix: {fix}"
        click.echo(msg, err=True)
    raise SystemExit(code)


def _resolve_format(output_format: str, json_output: bool) -> str:
    """Resolve output format, giving --json flag precedence as alias.

    Auto-switches to JSON when stdout is not a TTY (i.e., piped to an agent)
    unless the user explicitly chose a format.
    """
    if json_output:
        return "json"
    if output_format == "table" and not sys.stdout.isatty():
        return "json"
    return output_format


def _resolve_context(context_json: str | None, *, json_mode: bool = False) -> BusinessContext:
    if context_json:
        try:
            return BusinessContext.from_json(context_json)
        except (json_mod.JSONDecodeError, TypeError, ValueError) as e:
            _error_exit(
                EXIT_INPUT_ERROR, "invalid_json",
                f"Invalid --context JSON: {e}",
                fix="namera find --example",
                json_mode=json_mode,
            )

    if not sys.stdin.isatty():
        stdin_data = sys.stdin.read().strip()
        if stdin_data:
            try:
                return BusinessContext.from_json(stdin_data)
            except (json_mod.JSONDecodeError, TypeError, ValueError) as e:
                _error_exit(
                    EXIT_INPUT_ERROR, "invalid_json",
                    f"Invalid JSON on stdin: {e}",
                    fix="namera find --example",
                    json_mode=json_mode,
                )

    session = InteractiveSession(console)
    ctx = session.run()
    if ctx is None:
        raise SystemExit(EXIT_OK)
    return ctx


@click.group()
@click.version_option()
def main():
    """Namera - Check name availability across domains, trademarks, and more."""
    register_all()


@main.command()
@click.argument("name")
@click.option("--tlds", default="com,net,org,io,dev", help="Preset name or comma-separated TLDs")
@click.option(
    "--format", "output_format",
    type=click.Choice(["table", "json", "ndjson", "csv"]),
    default="table", help="Output format",
)
@click.option(
    "--json", "json_output", is_flag=True, hidden=True, help="Shorthand for --format json",
)
@click.option("--only-available", "-a", is_flag=True, help="Show only available results")
@click.option("--verbose", "-v", is_flag=True, help="Include summary/context in JSON output")
def domain(
    name: str, tlds: str, output_format: str, json_output: bool,
    only_available: bool, verbose: bool,
):
    """Check domain availability for a name."""
    output_format = _resolve_format(output_format, json_output)
    tld_list = resolve_tld_input(tlds)
    results = asyncio.run(run_checks(name, [CheckType.DOMAIN], tlds=tld_list))

    if only_available:
        from namera.filters import filter_available_only

        results = filter_available_only(results)

    output = render_results(results, format=output_format, console=console, verbose=verbose)
    if output is not None:
        click.echo(output)


@main.command()
@click.argument("name")
@click.option(
    "--format", "output_format",
    type=click.Choice(["table", "json", "ndjson", "csv"]),
    default="table", help="Output format",
)
@click.option(
    "--json", "json_output", is_flag=True, hidden=True, help="Shorthand for --format json",
)
@click.option("--verbose", "-v", is_flag=True, help="Include summary/context in JSON output")
def whois(name: str, output_format: str, json_output: bool, verbose: bool):
    """Run a WHOIS lookup on a domain."""
    output_format = _resolve_format(output_format, json_output)
    results = asyncio.run(run_checks(name, [CheckType.WHOIS]))

    output = render_results(results, format=output_format, console=console, verbose=verbose)
    if output is not None:
        click.echo(output)


@main.command()
@click.argument("name")
@click.option(
    "--format", "output_format",
    type=click.Choice(["table", "json", "ndjson", "csv"]),
    default="table", help="Output format",
)
@click.option(
    "--json", "json_output", is_flag=True, hidden=True, help="Shorthand for --format json",
)
@click.option("--verbose", "-v", is_flag=True, help="Include summary/context in JSON output")
def trademark(name: str, output_format: str, json_output: bool, verbose: bool):
    """Check trademark status for a name."""
    output_format = _resolve_format(output_format, json_output)
    results = asyncio.run(run_checks(name, [CheckType.TRADEMARK]))

    output = render_results(results, format=output_format, console=console, verbose=verbose)
    if output is not None:
        click.echo(output)


@main.command()
@click.argument("name")
@click.option("--tlds", default="com,net,org,io,dev", help="Preset name or comma-separated TLDs")
@click.option(
    "--format", "output_format",
    type=click.Choice(["table", "json", "ndjson", "csv"]),
    default="table", help="Output format",
)
@click.option(
    "--json", "json_output", is_flag=True, hidden=True, help="Shorthand for --format json",
)
@click.option("--only-available", "-a", is_flag=True, help="Show only available results")
@click.option("--verbose", "-v", is_flag=True, help="Include summary/context in JSON output")
@click.option("--concurrency", default=15, help="Max concurrent checks")
@click.option("--timeout", default=15.0, help="Timeout per check in seconds")
def search(
    name: str, tlds: str, output_format: str, json_output: bool,
    only_available: bool, verbose: bool, concurrency: int, timeout: float,
):
    """Run all checks (domain, whois, trademark) for a name."""
    output_format = _resolve_format(output_format, json_output)
    tld_list = resolve_tld_input(tlds)
    all_types = [CheckType.DOMAIN, CheckType.WHOIS, CheckType.TRADEMARK]
    results = asyncio.run(
        run_checks(name, all_types, concurrency=concurrency, timeout=timeout, tlds=tld_list)
    )

    if only_available:
        from namera.filters import filter_available_only

        results = filter_available_only(results)

    output = render_results(results, format=output_format, console=console, verbose=verbose)
    if output is not None:
        click.echo(output)


_CONTEXT_EXAMPLE = """\
{
  "description": "A mobile-first budget tracking app that helps users split expenses with friends",
  "name_candidates": ["splitly", "buddi", "pennypact"],
  "niche": "fintech",
  "target_audience": "millennials",
  "location": "US",
  "preferred_tlds": ["com", "io"],
  "name_style": "short",
  "checks": ["domain", "whois", "trademark"]
}

Required:  name_candidates (list of names to check)
Recommended: description (what the business does), niche (industry keyword)
Optional:  target_audience, location, name_style, preferred_tlds,
           max_domain_price, checks (domain/whois/trademark/social)\
"""


@main.command()
@click.option(
    "--context", "context_json", default=None,
    help=(
        "Business context as JSON. "
        "Required: name_candidates. "
        "Recommended: description, niche. "
        "Optional: target_audience, location, name_style, preferred_tlds, "
        "max_domain_price, checks. "
        "Run with --example to see full schema."
    ),
)
@click.option("--example", is_flag=True, help="Print an example --context JSON and exit")
@click.option(
    "--format", "output_format",
    type=click.Choice(["table", "json", "ndjson", "csv"]),
    default="table", help="Output format",
)
@click.option(
    "--json", "json_output", is_flag=True, hidden=True, help="Shorthand for --format json",
)
@click.option("--only-available", "-a", is_flag=True, help="Show only available results")
@click.option(
    "--filter-trademarked/--no-filter-trademarked", default=False,
    help="Remove names with trademark conflicts from results",
)
@click.option("--verbose", "-v", is_flag=True, help="Include summary/context in JSON output")
@click.option("--concurrency", default=15, help="Max concurrent checks")
@click.option("--timeout", default=15.0, help="Timeout per check in seconds")
def find(
    context_json: str | None, example: bool, output_format: str, json_output: bool,
    only_available: bool, filter_trademarked: bool, verbose: bool,
    concurrency: int, timeout: float,
):
    """Discover and check name availability with business context.

    \b
    AI agents: pass --context with a JSON object containing at minimum
    name_candidates and ideally a description of the business.
    Run --example to see the full JSON schema.
    """
    if example:
        click.echo(_CONTEXT_EXAMPLE)
        return
    output_format = _resolve_format(output_format, json_output)
    json_mode = _is_json_mode(output_format)
    interactive = context_json is None and sys.stdin.isatty()
    ctx = _resolve_context(context_json, json_mode=json_mode)
    tlds = ctx.resolve_tlds()
    try:
        check_types = ctx.resolve_check_types()
    except ValueError as e:
        _error_exit(
            EXIT_INPUT_ERROR,
            "invalid_context",
            str(e),
            fix="namera find --example",
            json_mode=json_mode,
        )

    if not ctx.name_candidates:
        _error_exit(
            EXIT_INPUT_ERROR, "no_candidates",
            "No name candidates provided.",
            fix="namera find --context '{\"name_candidates\": [\"myname\"]}'",
            json_mode=json_mode,
        )

    if output_format == "table" and ctx.name_candidates:
        console.print(f"\n{styled(f'Checking {len(ctx.name_candidates)} name(s)...', HEADING)}\n")

    results = asyncio.run(
        run_checks_multi_batched(
            ctx.name_candidates, check_types,
            concurrency=concurrency,
            timeout=timeout,
            tlds=tlds,
            price_max=ctx.max_domain_price,
        )
    )

    # Auto-permute names where all preferred-TLD domains are taken
    taken_names = names_all_domains_taken(results, tlds)
    if taken_names:
        perm_names = generate_permutation_names(taken_names)
        existing = {n.lower() for n in ctx.name_candidates}
        perm_names = [n for n in perm_names if n.lower() not in existing]
        if perm_names:
            if output_format == "table":
                console.print(
                    styled(f"Trying variations for {len(taken_names)} taken name(s)...\n", HEADING)
                )
            perm_results = asyncio.run(
                run_checks_multi_batched(
                    perm_names, check_types,
                    concurrency=concurrency,
                    timeout=timeout,
                    tlds=tlds,
                    price_max=ctx.max_domain_price,
                )
            )
            results.extend(perm_results)
            ctx.name_candidates.extend(perm_names)

    # Filter trademarked names by canonical candidate identity.
    from namera.filters import filter_trademarked_results, get_trademark_risk_names

    risky_names = get_trademark_risk_names(results)

    if risky_names and output_format == "table":
        console.print(
            f"{styled('Trademark conflicts:', f'bold {WARNING}')} {', '.join(risky_names)}\n"
        )

    if filter_trademarked and risky_names:
        results = filter_trademarked_results(results)

    if only_available:
        from namera.filters import filter_available_only

        results = filter_available_only(results)

    # Interactive mode: rank and show top 10
    if interactive and output_format == "table":
        profile = resolve_profile("default")
        ranked = rank_candidates(ctx.name_candidates, results, profile)
        render_find_ranked(ranked, tlds, console)
    elif output_format == "json":
        click.echo(render_results_json(results, ctx, verbose=verbose))
    elif output_format == "table":
        render_results_table(console, results, ctx)
    else:
        output = render_results(results, format=output_format, console=console)
        if output is not None:
            click.echo(output)

    # Determine exit code based on results
    errored = [r for r in results if r.error]
    if errored and len(errored) == len(results):
        raise SystemExit(EXIT_NETWORK_ERROR)
    elif errored:
        raise SystemExit(EXIT_PARTIAL_FAILURE)


@main.command()
@click.argument("names", nargs=-1)
@click.option("--context", "context_json", default=None, help="Business context as JSON string")
@click.option("--profile", "profile_name", default="default", help="Scoring profile name")
@click.option("--tlds", default="com,net,org,io,dev", help="Preset name or comma-separated TLDs")
@click.option(
    "--format", "output_format",
    type=click.Choice(["table", "json"]),
    default="table", help="Output format",
)
@click.option(
    "--json", "json_output", is_flag=True, hidden=True, help="Shorthand for --format json",
)
@click.option("--concurrency", default=15, help="Max concurrent checks")
@click.option("--timeout", default=15.0, help="Timeout per check in seconds")
def rank(
    names: tuple[str, ...], context_json: str | None, profile_name: str,
    tlds: str, output_format: str, json_output: bool, concurrency: int, timeout: float,
):
    """Rank name candidates by composite score.

    Runs domain, WHOIS, trademark, and social checks, then scores and ranks
    using local string analysis + provider signals.

    Examples:\n
      namera rank voxly dataprime nimbus\n
      namera rank voxly dataprime --profile fintech --json\n
      namera rank --context '{"name_candidates": ["voxly"], "niche": "fintech"}'
    """
    output_format = _resolve_format(output_format, json_output)
    json_mode = _is_json_mode(output_format)

    # Resolve names from args or context
    if context_json:
        try:
            ctx = BusinessContext.from_json(context_json)
        except (json_mod.JSONDecodeError, TypeError, ValueError) as e:
            _error_exit(
                EXIT_INPUT_ERROR, "invalid_json",
                f"Invalid --context JSON: {e}",
                fix="namera rank name1 name2  (or use --context with valid JSON)",
                json_mode=json_mode,
            )
        name_list = ctx.name_candidates
        if ctx.scoring_profile:
            profile_name = ctx.scoring_profile
        tld_list = ctx.resolve_tlds()
    elif names:
        name_list = list(names)
        ctx = BusinessContext(name_candidates=name_list)
        tld_list = resolve_tld_input(tlds)
    else:
        _error_exit(
            EXIT_INPUT_ERROR, "no_candidates",
            "Provide name(s) as arguments or via --context.",
            fix=(
                "namera rank name1 name2  "
                "(or namera rank --context '{\"name_candidates\": [...]}')"
            ),
            json_mode=json_mode,
        )

    if not name_list:
        _error_exit(
            EXIT_INPUT_ERROR, "no_candidates",
            "No name candidates provided.",
            fix="namera rank name1 name2",
            json_mode=json_mode,
        )

    profile = resolve_profile(profile_name, ctx.weight_overrides)

    if output_format == "table":
        msg = f"Ranking {len(name_list)} name(s) with profile: {profile.name}"
        console.print(f"\n{styled(msg, HEADING)}\n")

    # Run all checks for all names concurrently
    all_types = [CheckType.DOMAIN, CheckType.WHOIS, CheckType.TRADEMARK, CheckType.SOCIAL]
    results = asyncio.run(
        run_checks_multi_batched(
            name_list, all_types,
            concurrency=concurrency,
            timeout=timeout,
            tlds=tld_list,
            price_max=ctx.max_domain_price,
        )
    )

    ranked = rank_candidates(name_list, results, profile)

    # Log session (non-blocking, best-effort)
    from namera.telemetry import log_session
    log_session(name_list, ranked, profile.name, ctx.niche)

    # Output
    if output_format == "json":
        payload = {
            "ranked": [compact_ranked(r) for r in ranked],
        }
        click.echo(json_mod.dumps(payload, separators=(",", ":")))
    else:
        render_ranked_table(ranked, profile, console)


async def _run_checks_for_domains(domains: list[str]):
    """Check availability for a list of fully-qualified domain names."""
    import socket as _socket

    from namera.providers.base import Availability as _Av

    async def _check_one(domain_name: str) -> dict:
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, _socket.gethostbyname, domain_name)
            return {"domain": domain_name, "available": _Av.TAKEN.value}
        except _socket.gaierror:
            return {"domain": domain_name, "available": _Av.AVAILABLE.value}

    tasks = [_check_one(d) for d in domains]
    return await asyncio.gather(*tasks)


@main.command("compose")
@click.argument("keywords", nargs=-1, required=True)
@click.option("--tlds", default="com", help="Preset name or comma-separated TLDs")
@click.option("--prefix", "-p", multiple=True, help="Prefixes to prepend (repeatable)")
@click.option("--suffix", "-s", multiple=True, help="Suffixes to append (repeatable)")
@click.option(
    "--common-prefixes", is_flag=True, help="Include common prefixes (get, try, my, ...)",
)
@click.option(
    "--common-suffixes", is_flag=True, help="Include common suffixes (app, hq, hub, ...)",
)
@click.option("--max-length", default=63, help="Max domain label length")
@click.option("--check", is_flag=True, help="Also check availability (runs domain checks)")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def compose_cmd(
    keywords, tlds, prefix, suffix, common_prefixes, common_suffixes,
    max_length, check, json_output,
):
    """Generate domain name permutations from keywords.

    Examples:\n
      namera compose namera --common-suffixes --tlds com,io\n
      namera compose namera --prefix get --prefix try --suffix hq\n
      namera compose namera --common-prefixes --common-suffixes --check
    """
    from namera.composer import ComposerConfig
    from namera.composer import compose as run_compose

    tld_list = resolve_tld_input(tlds)
    config = ComposerConfig(
        keywords=list(keywords),
        prefixes=list(prefix),
        suffixes=list(suffix),
        tlds=tld_list,
        max_length=max_length,
        use_common_prefixes=common_prefixes,
        use_common_suffixes=common_suffixes,
    )

    domains = run_compose(config)

    if not check:
        if json_output:
            click.echo(json_mod.dumps({"domains": domains}, separators=(",", ":")))
        else:
            for d in domains:
                click.echo(d)
            click.echo(f"\n{len(domains)} domain(s) generated.", err=True)
    else:
        domain_results = asyncio.run(_run_checks_for_domains(domains))

        if json_output:
            output_data = [
                {"query": r["domain"], "status": r["available"]}
                for r in domain_results
            ]
            click.echo(json_mod.dumps({"results": output_data}, separators=(",", ":")))
        else:
            table = Table(title="Compose + Check")
            table.add_column("Domain", style="bold")
            table.add_column("Status")

            for r in domain_results:
                avail = r["available"]
                if isinstance(avail, bool):
                    avail = Availability.AVAILABLE if avail else Availability.TAKEN
                else:
                    avail = Availability(avail)
                label, st = availability_style(avail)
                table.add_row(r["domain"], styled(label, st))

            console.print(table)


@main.command()
def presets():
    """Show available TLD presets."""
    table = Table(title="TLD Presets")
    table.add_column("Preset", style="bold")
    table.add_column("TLDs")
    table.add_column("Count", justify="right")

    for name in sorted(TLD_PRESETS):
        tlds = TLD_PRESETS[name]
        table.add_row(name, ", ".join(f".{t}" for t in tlds), str(len(tlds)))

    console.print(table)
