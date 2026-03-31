"""Naming agent — generates YC-style business names using Claude and checks availability."""

from __future__ import annotations

import asyncio
import json

from anthropic import Anthropic

# Import providers so they auto-register
import namera.providers.domain_api  # noqa: F401
import namera.providers.trademark  # noqa: F401
import namera.providers.whois  # noqa: F401
from namera.providers.base import CheckType, registry

SYSTEM_PROMPT = """\
You are Namera, a world-class brand naming expert. You specialize in creating \
short, punchy, YC-style startup names — the kind you'd see on a Y Combinator \
batch list or on the front page of Hacker News.

YC-style name characteristics:
- Short (1-2 syllables preferred, 3 max)
- Easy to spell and pronounce
- Memorable and distinctive
- Often: made-up words, creative misspellings, Latin/Greek roots, or compound words
- Examples: Stripe, Vercel, Figma, Notion, Loom, Retool, Supabase, Posthog, Vanta

Your workflow:
1. FIRST: Ask 2-3 focused clarifying questions about the business to generate better names. \
Ask about: target audience, vibe/personality, geographic scope, domain budget, any name preferences.
2. AFTER getting answers: Generate exactly 10 name suggestions.

When generating names, return them as a JSON array using this exact format:
```json
{"names": ["Name1", "Name2", "Name3", ...]}
```

Return ONLY the JSON block when generating names — no extra text around it.\
"""


def _extract_names(text: str) -> list[str] | None:
    """Try to extract a JSON names array from the assistant's response."""
    # Look for JSON block in the response
    for start_marker in ["```json\n", "```\n", "{"]:
        if start_marker in text:
            start = text.index(start_marker)
            if start_marker.startswith("```"):
                start += len(start_marker)
                end = text.index("```", start) if "```" in text[start:] else len(text)
                json_str = text[start:end].strip()
            else:
                json_str = text[start:]
            try:
                data = json.loads(json_str)
                if isinstance(data, dict) and "names" in data:
                    return data["names"]
            except json.JSONDecodeError:
                continue
    return None


async def check_name(name: str, tlds: list[str], price_max: float | None = None) -> dict:
    """Run all providers against a single name and return a structured result."""
    results = {"name": name, "domains": [], "trademark": None}

    # Domain checks
    for provider_cls in registry.list_by_type(CheckType.DOMAIN):
        provider = provider_cls()
        result = await provider.check(name.lower(), tlds=tlds, price_max=price_max)
        for d in result.details.get("domains", []):
            results["domains"].append(d)

    # Trademark check
    for provider_cls in registry.list_by_type(CheckType.TRADEMARK):
        provider = provider_cls()
        result = await provider.check(name, )
        results["trademark"] = {
            "status": result.available.value,
            "note": result.details.get("note", ""),
        }

    return results


async def check_all_names(
    names: list[str],
    tlds: list[str] | None = None,
    price_max: float | None = None,
) -> list[dict]:
    """Check all generated names concurrently."""
    if tlds is None:
        tlds = ["com", "ai", "app"]

    tasks = [check_name(name, tlds, price_max) for name in names]
    return await asyncio.gather(*tasks)


def run_conversation(
    on_assistant_message=None,
    on_user_input=None,
) -> tuple[list[str], list[dict]]:
    """Run the interactive naming conversation.

    Args:
        on_assistant_message: callback(text) — called when the agent speaks.
        on_user_input: callback(prompt) -> str — called to get user input.
            Defaults to built-in input().

    Returns:
        (names, checked_results) — the generated names and their availability checks.
    """
    if on_user_input is None:
        on_user_input = lambda prompt: input(prompt)  # noqa: E731

    client = Anthropic()
    messages = []

    # Step 1: Send initial business description
    if on_assistant_message:
        on_assistant_message(
            "Tell me about your business — what does it do, who is it for, "
            "and what makes it unique?"
        )

    user_input = on_user_input("\n> ")
    messages.append({"role": "user", "content": user_input})

    # Step 2: Clarifying questions loop
    names = None
    tlds = ["com", "ai", "app"]
    price_max = None

    while names is None:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages,
        )

        assistant_text = response.content[0].text
        messages.append({"role": "assistant", "content": assistant_text})

        # Check if we got names back
        names = _extract_names(assistant_text)
        if names:
            break

        # Otherwise it's a clarifying question — show it and get response
        if on_assistant_message:
            on_assistant_message(assistant_text)

        user_input = on_user_input("\n> ")

        # Let user set TLDs and budget inline
        if "tld:" in user_input.lower():
            # Parse "tld: com,ai,app" from the input
            for part in user_input.split(","):
                part = part.strip()
            tld_part = user_input.lower().split("tld:")[1].split(".")[0].strip()
            tlds = [t.strip() for t in tld_part.split(",")]

        if "budget:" in user_input.lower():
            try:
                budget_str = user_input.lower().split("budget:")[1].strip().split()[0]
                price_max = float(budget_str.replace("$", ""))
            except (ValueError, IndexError):
                pass

        messages.append({"role": "user", "content": user_input})

    # Step 3: Check all names
    checked = asyncio.run(check_all_names(names, tlds=tlds, price_max=price_max))

    return names, checked
