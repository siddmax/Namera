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
  context.py         # BusinessContext dataclass, TLD_HINTS, serialization
  session.py         # Interactive Q&A wizard (Rich prompts)
  output.py          # Shared rendering (JSON + Rich tables)
  enricher.py        # Relevance scoring based on business context
  providers/
    base.py           # Provider ABC, ProviderResult, ProviderRegistry
    domain.py         # DNS-based domain availability check
    whois.py          # Raw socket WHOIS lookup
    trademark.py      # Trademark provider hub (imports from trademark_supabase.py)
    trademark_supabase.py  # USPTO trademark lookup via Supabase (exact + similarity)
```

## Commands

```bash
source .venv/bin/activate

# Direct commands (single name)
namera domain <name>          # Check domain availability
namera whois <name>           # WHOIS lookup
namera trademark <name>       # Trademark check (stub)
namera search <name>          # Run all checks

# Context-aware discovery (multiple names, business context)
namera find                                    # Interactive wizard
namera find --context '{"name_candidates": ["name1"], "niche": "fintech"}'
namera find --json --context '...'             # Agent-friendly JSON output

# All commands support --json for machine-readable output
namera domain myname --json
namera search myname --json
```

## Agent Integration

Agents call `namera find --json --context '<json>'` with a BusinessContext JSON:

```json
{
  "description": "A mobile-first budget tracking app that helps users split expenses with friends and build savings habits",
  "name_candidates": ["neopay", "zestmoney"],
  "niche": "fintech",
  "target_audience": "millennials",
  "location": "US",
  "preferred_tlds": ["com", "io"],
  "max_domain_price": 50.0,
  "name_style": "short",
  "checks": ["domain", "whois", "trademark"]
}
```

**Required fields:**
- `name_candidates` — the names to check availability for

**Recommended fields (improve results significantly):**
- `description` — freeform text describing what the business does. Can be a sentence, paragraph, or pasted business doc. This is the primary context used for relevance scoring and name evaluation.
- `niche` — short industry keyword (e.g., "fintech", "health"). Also drives automatic TLD selection via `TLD_HINTS`.

**Optional fields:**
- `target_audience`, `location`, `name_style` — refine scoring
- `preferred_tlds` — override auto-detected TLDs (e.g., `["com", "io"]`)
- `max_domain_price` — budget filter
- `checks` — limit to specific providers (default: all). Values: `domain`, `whois`, `trademark`, `social`

**Input modes:** `--context` flag > stdin pipe > interactive wizard (auto-detected).

**Typical agent workflow:**
1. Gather business context from the user (what they're building, who it's for)
2. Generate name candidates
3. Call `namera find --json --context '<json>'` with description + candidates
4. Parse JSON results to recommend the best available names

## Supabase Setup

Namera uses the **yurivan** Supabase project (shared with Yurivan). Credentials are managed via **Doppler**.

```bash
# Doppler config lives in doppler.yaml (project: yurivan, config: dev)
# Run any command with Supabase env vars:
doppler run -- namera trademark apple

# Or export for the session:
eval $(doppler secrets download --no-file --format env)
```

**Schema:** `namera` (separate from other projects in the same Supabase instance)

**Key env vars** (all in Doppler `yurivan/dev`):
- `NEXT_PUBLIC_SUPABASE_URL` — Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` — for writes (import script)
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` — for reads (CLI queries)

**Trademark data:**
- 12.7M USPTO trademarks in `namera.trademarks` table
- RPC functions: `trademark_check` (exact), `trademark_similarity_search` (fuzzy), `trademark_batch_check` (multi)
- Indexes: B-tree on normalized text, GIN trigram for fuzzy, covering index for fast reads
- Monthly freshness check via pg_cron (`namera-data-freshness-check`)

**Import/refresh:**
```bash
# Full data import (needs psycopg):
pip install "psycopg[binary]>=3.1"
doppler run -- python scripts/import_trademarks.py --live-only
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
- BusinessContext is the single input object for `find` — extend it for new fields
- JSON output via `--json` flag on all commands — use `output.py` for rendering
