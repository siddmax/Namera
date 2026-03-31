# Namera

CLI tool for checking name availability across domains, trademarks, and more.
Designed to be called directly by AI agents (Claude Code, OpenClaw, Codex, etc.).

## Tech Stack

- Python 3.10+, Click (CLI), Rich (output), httpx (HTTP)
- Build: hatchling, src layout (`src/namera/`)
- Tests: pytest + pytest-asyncio

## Project Structure

```
src/namera/
  cli.py             # CLI entry point (Click group)
  providers/
    base.py           # Provider ABC, ProviderResult, ProviderRegistry
    domain.py         # DNS-based domain availability check
    whois.py          # Raw socket WHOIS lookup
    trademark.py      # Stub trademark provider (replace with real API)
```

## Commands

```bash
source .venv/bin/activate
namera domain <name>          # Check domain availability
namera whois <name>           # WHOIS lookup
namera trademark <name>       # Trademark check (stub)
namera search <name>          # Run all checks
```

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check src/ tests/
```

## Adding a New Provider

1. Create `src/namera/providers/yourprovider.py`
2. Subclass `Provider`, set `name` and `check_type` class attributes
3. Implement `async def check(self, query, **kwargs) -> ProviderResult`
4. Import it in `cli.py` so it auto-registers
5. Providers auto-register via `__init_subclass__` — no manual wiring needed

## Conventions

- All providers are async
- Use `ProviderResult` for all return values — never raw dicts
- Keep API keys in env vars, never hardcode
- Provider names should be lowercase kebab-case (e.g., `whois`, `trademark-stub`)
