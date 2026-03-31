from __future__ import annotations

import asyncio

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Import providers so they auto-register
import namera.providers.domain  # noqa: F401
import namera.providers.domain_api  # noqa: F401
import namera.providers.trademark  # noqa: F401
import namera.providers.whois  # noqa: F401
from namera.providers.base import Availability, CheckType, registry

console = Console()


def _availability_style(av: Availability) -> tuple[str, str]:
    return {
        Availability.AVAILABLE: ("Available", "green"),
        Availability.TAKEN: ("Taken", "red"),
        Availability.UNKNOWN: ("Unknown", "yellow"),
    }[av]


async def _run_checks(name: str, check_types: list[CheckType], **kwargs):
    results = []
    for ct in check_types:
        for provider_cls in registry.list_by_type(ct):
            provider = provider_cls()
            result = await provider.check(name, **kwargs)
            results.append(result)
    return results


@click.group()
@click.version_option()
def main():
    """Namera - Check name availability across domains, trademarks, and more."""


@main.command()
@click.argument("name")
@click.option("--tlds", default="com,net,org,io,dev", help="Comma-separated TLDs to check")
def domain(name: str, tlds: str):
    """Check domain availability for a name."""
    tld_list = [t.strip() for t in tlds.split(",")]
    results = asyncio.run(_run_checks(name, [CheckType.DOMAIN], tlds=tld_list))

    for r in results:
        table = Table(title=f"Domain availability: {name}")
        table.add_column("Domain", style="bold")
        table.add_column("Status")

        for d in r.details.get("domains", []):
            label, style = _availability_style(Availability(d["available"]))
            table.add_row(d["domain"], f"[{style}]{label}[/{style}]")

        console.print(table)


@main.command()
@click.argument("name")
def whois(name: str):
    """Run a WHOIS lookup on a domain."""
    results = asyncio.run(_run_checks(name, [CheckType.WHOIS]))

    for r in results:
        if r.error:
            console.print(f"[red]Error:[/red] {r.error}")
        else:
            label, style = _availability_style(r.available)
            console.print(f"[bold]{r.query}[/bold]: [{style}]{label}[/{style}]")
            if r.details.get("raw") and click.get_current_context().obj != "quiet":
                console.print(r.details["raw"][:1000])


@main.command()
@click.argument("name")
def trademark(name: str):
    """Check trademark status for a name."""
    results = asyncio.run(_run_checks(name, [CheckType.TRADEMARK]))

    for r in results:
        if r.error:
            console.print(f"[red]Error:[/red] {r.error}")
        else:
            label, style = _availability_style(r.available)
            console.print(f"[bold]{r.query}[/bold]: [{style}]{label}[/{style}]")
            if r.details.get("note"):
                console.print(f"  Note: {r.details['note']}")


@main.command()
@click.argument("name")
@click.option("--tlds", default="com,net,org,io,dev", help="Comma-separated TLDs to check")
def search(name: str, tlds: str):
    """Run all checks (domain, whois, trademark) for a name."""
    tld_list = [t.strip() for t in tlds.split(",")]
    all_types = [CheckType.DOMAIN, CheckType.WHOIS, CheckType.TRADEMARK]
    results = asyncio.run(_run_checks(name, all_types, tlds=tld_list))

    table = Table(title=f"Name search: {name}")
    table.add_column("Check", style="bold")
    table.add_column("Provider")
    table.add_column("Query")
    table.add_column("Status")
    table.add_column("Notes")

    for r in results:
        label, style = _availability_style(r.available)
        notes = r.error or ""
        if r.check_type == CheckType.DOMAIN:
            for d in r.details.get("domains", []):
                dl, ds = _availability_style(Availability(d["available"]))
                table.add_row("domain", r.provider_name, d["domain"], f"[{ds}]{dl}[/{ds}]", "")
        else:
            if r.details.get("note"):
                notes = r.details["note"]
            table.add_row(
                r.check_type.value, r.provider_name, r.query, f"[{style}]{label}[/{style}]", notes
            )

    console.print(table)


@main.command()
@click.option("--tlds", default="com,ai,app", help="Comma-separated TLDs to check")
@click.option("--budget", type=float, default=None, help="Max domain price in USD")
def generate(tlds: str, budget: float | None):
    """Generate YC-style business names with AI and check availability."""
    import os

    if not os.getenv("ANTHROPIC_API_KEY"):
        console.print(
            "[red]Error:[/red] Set ANTHROPIC_API_KEY env var to use the naming agent.\n"
            "  export ANTHROPIC_API_KEY=sk-ant-..."
        )
        raise SystemExit(1)

    from namera.agent import run_conversation

    def on_message(text: str):
        console.print(Panel(text, title="[bold cyan]Namera[/bold cyan]", border_style="cyan"))

    def on_input(prompt: str) -> str:
        return console.input(f"[bold green]You:[/bold green]{prompt}")

    console.print()
    console.print("[bold]Welcome to Namera — YC-style name generator[/bold]")
    console.print("Describe your business and I'll come up with great names.\n")

    names, results = run_conversation(
        on_assistant_message=on_message,
        on_user_input=on_input,
    )

    # Display results table
    console.print()
    table = Table(title="[bold]Name suggestions + availability[/bold]")
    table.add_column("Name", style="bold")

    tld_list = [t.strip() for t in tlds.split(",")]
    for tld in tld_list:
        table.add_column(f".{tld}", justify="center")
    table.add_column("Price", justify="right")
    table.add_column("Trademark", justify="center")

    for result in results:
        row = [result["name"]]

        # Domain columns
        domain_map = {d["domain"]: d for d in result.get("domains", [])}
        for tld in tld_list:
            domain_key = f"{result['name'].lower()}.{tld}"
            d = domain_map.get(domain_key, {})
            if d.get("available"):
                status = "[green]✓[/green]"
            elif d.get("error"):
                status = "[yellow]?[/yellow]"
            else:
                status = "[red]✗[/red]"
            row.append(status)

        # Price (show cheapest available)
        prices = [
            d["price"]
            for d in result.get("domains", [])
            if d.get("available") and d.get("price")
        ]
        if prices:
            cheapest = min(prices)
            price_str = f"${cheapest:.2f}"
            if budget and cheapest > budget:
                price_str = f"[red]{price_str}[/red]"
            else:
                price_str = f"[green]{price_str}[/green]"
            row.append(price_str)
        else:
            row.append("—")

        # Trademark
        tm = result.get("trademark", {})
        if tm:
            tm_status = tm.get("status", "unknown")
            if tm_status == "available":
                row.append("[green]Clear[/green]")
            elif tm_status == "taken":
                row.append("[red]Conflict[/red]")
            else:
                row.append("[yellow]Unknown[/yellow]")
        else:
            row.append("—")

        table.add_row(*row)

    console.print(table)
    console.print()
