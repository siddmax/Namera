# Namera

CLI tool for checking name availability across domains, trademarks, and more.
Designed to be called directly by AI agents (Codex, OpenClaw, Codex, etc.).

## Tech Stack

- Python 3.10+, Click (CLI), Rich (output), httpx (HTTP)
- Build: hatchling, src layout (`src/namera/`)
- Tests: pytest + pytest-asyncio

## Project Structure

```
src/namera/
  cli.py             # CLI entry point (Click group, 8 commands)
  context.py         # BusinessContext dataclass, TLD_HINTS, serialization
  session.py         # Interactive Q&A wizard (Rich prompts)
  output.py          # Multi-format rendering (JSON, NDJSON, CSV, Rich tables)
  cache.py           # SQLite result cache (~/.cache/namera/cache.db), per-provider TTLs
  composer.py        # Domain name generation from keywords + prefixes/suffixes
  filters.py         # Trademark risk flagging, available-only filtering
  presets.py         # 20 TLD presets (popular, tech, startup, fintech, geo-*, etc.)
  runner.py          # Async concurrent check runner with semaphore + caching
  retry.py           # Exponential backoff with jitter for transient errors
  theme.py           # Brand colors + availability styling
  telemetry.py       # Non-blocking session logging to Supabase
  providers/
    base.py           # Provider ABC, ProviderResult, ProviderRegistry, CheckType enum
    domain.py         # DNS-based domain availability (socket.gethostbyname)
    domain_api.py     # GoDaddy API (availability + pricing, falls back to DNS)
    rdap.py           # RDAP lookup with cascading fallbacks (RDAP → DNS → WHOIS)
    whois.py          # Raw socket WHOIS (port 43)
    social.py         # Social handle checks (GitHub, Twitter/X, Instagram)
    trademark.py      # Trademark provider hub (imports from trademark_supabase.py)
    trademark_supabase.py  # USPTO trademark lookup via Supabase Edge Function
  scoring/
    models.py         # Signal, ScoringProfile, RankedName dataclasses
    engine.py         # RankingEngine: collect signals → filter → weighted score → sort
    local_signals.py  # Zero-cost string analysis (length, pronounceability, quality)
    normalizers.py    # ProviderResult → Signal conversion for each check type
    profiles.py       # 5 built-in profiles (default, startup-saas, fintech, consumer, developer-tools)
```

## Commands

```bash
source .venv/bin/activate

# Direct commands (single name)
namera domain <name>          # Check domain availability
namera whois <name>           # WHOIS lookup
namera trademark <name>       # Trademark check (USPTO via Supabase Edge Function)
namera search <name>          # Run all checks (domain + whois + trademark)

# Context-aware discovery (multiple names, business context)
namera find                                    # Interactive wizard
namera find --context '{"name_candidates": ["name1"], "niche": "fintech"}'
namera find --json --context '...'             # Agent-friendly JSON output

# Scoring and ranking
namera rank name1 name2 name3                  # Rank names by composite score
namera rank --profile fintech --json name1 name2  # Use a scoring profile
namera rank --context '{"name_candidates": [...], "niche": "fintech"}'

# Domain name generation
namera compose keyword --common-suffixes --tlds com,io  # Generate permutations
namera compose keyword --prefix get --suffix hq --check # Generate + check availability

# TLD presets
namera presets                                 # Show all available TLD presets

# All commands support --format table|json|ndjson|csv and --json shorthand
# Output auto-switches to JSON when stdout is piped (agent-friendly)
namera domain myname --json
namera search myname --format csv
namera find --json --context '...' | jq .
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

Namera uses the **yurivan** Supabase project (shared with Yurivan).

**Schema:** `namera` (separate from other projects in the same Supabase instance)

**Trademark checks use a Supabase Edge Function** (`trademark-check`):
- Public endpoint: `https://wmnzjmrysnzjthldgffh.supabase.co/functions/v1/trademark-check`
- `verify_jwt=false` — no API key needed from CLI users
- The Edge Function uses `service_role` internally to query the `namera` schema
- Override URL via `NAMERA_TRADEMARK_API_URL` env var (e.g., for local dev)

```bash
# No credentials needed — just run:
namera trademark apple
```

**Trademark data:**
- 12.7M USPTO trademarks in `namera.trademarks` table
- RPC functions: `trademark_check` (exact), `trademark_similarity_search` (fuzzy), `trademark_batch_check` (multi)
- Indexes: B-tree on normalized text, GIN trigram for fuzzy, covering index for fast reads
- Monthly freshness check via pg_cron (`namera-data-freshness-check`)

**Import/refresh** (requires Doppler for DB write credentials):
```bash
# Full data import (needs psycopg + Doppler for service_role key):
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
