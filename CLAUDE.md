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
namera find --format json --context '...'      # Agent-friendly JSON output

# Scoring and ranking
namera rank name1 name2 name3                  # Rank names by composite score
namera rank --profile fintech --format json name1 name2  # Use a scoring profile
namera rank --context '{"name_candidates": [...], "niche": "fintech"}'

# Domain name generation
namera compose keyword --common-suffixes --tlds com,io  # Generate permutations
namera compose keyword --prefix get --suffix hq --check # Generate + check availability

# TLD presets
namera presets                                 # Show all available TLD presets

# Most commands support --format table|json|ndjson|csv
# `compose` supports --format text|json
# Output auto-switches to JSON when stdout is piped (agent-friendly)
namera domain myname --format json
namera search myname --format csv
namera find --format json --context '...' | jq .
```

## Agent Integration

Agents call `namera find --format json --context '<json>'` with a BusinessContext JSON.
**One command does everything:** compose name variations from keywords, check availability
across domains/trademarks/social, rank by composite score, and return structured results.

```json
{
  "description": "A mobile-first budget tracking app that helps users split expenses with friends and build savings habits",
  "name_candidates": ["neopay", "zestmoney"],
  "keywords": ["pay", "split"],
  "niche": "fintech",
  "target_audience": "millennials",
  "location": "US",
  "preferred_tlds": ["com", "io"],
  "name_style": "short",
  "checks": ["domain", "whois", "trademark"],
  "scoring_profile": "fintech",
  "weight_overrides": {"trademark": 0.3}
}
```

**Required:** at least one of `name_candidates` or `keywords`
- `name_candidates` — explicit names to check
- `keywords` — base words for auto-generating variations (e.g., `["pay"]` → pay, getpay, payapp, payhq, trypay, etc.)
  When both are provided, composed names are merged with explicit candidates (deduplicated).

**Recommended fields (improve results significantly):**
- `description` — freeform text describing what the business does. Can be a sentence, paragraph, or pasted business doc. This is the primary context used for relevance scoring and name evaluation.
- `niche` — short industry keyword (e.g., "fintech", "health"). Also drives automatic TLD selection via `TLD_HINTS`.

**Optional fields:**
- `target_audience`, `location`, `name_style` — refine scoring
- `preferred_tlds` — override auto-detected TLDs (e.g., `["com", "io"]`). Can also be a preset name (e.g., `["tech"]`)
- `checks` — limit to specific providers. Values: `domain`, `whois`, `trademark`, `social`
- `scoring_profile` — ranking profile name: `default`, `startup-saas`, `fintech`, `consumer`, `developer-tools`
- `weight_overrides` — override individual signal weights (merged with profile weights)
- `industry` — additional industry context

**Input modes:** `--context` flag > stdin pipe > interactive wizard (auto-detected).

**JSON output format** (returned by `find --format json`):
```json
{
  "ranked": [
    {
      "rank": 1,
      "name": "splitly",
      "score": 82.1,
      "domains": {"com": "available", "io": "taken"},
      "trademark": "clear",
      "social": {"github": "available", "twitter": "taken"},
      "quality": {"length": 90.0, "pronounceability": 75.0}
    }
  ],
  "filtered": [
    {"name": "badname", "reason": "trademark below threshold (0.00 < 0.5)"}
  ],
  "trademark_risks": ["badname"],
  "summary": {
    "candidates_checked": 5,
    "viable": 3,
    "filtered_out": 1,
    "profile": "fintech",
    "tlds_checked": ["com", "io"]
  }
}
```

**Typical agent workflow:**
1. Gather business context from the user (what they're building, who it's for)
2. Generate name candidates (or pass keywords to let Namera compose variations)
3. Call `namera find --format json --context '<json>'` — single call does compose + check + rank
4. Parse `ranked` array to recommend the best available names

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

## Providers

6 providers auto-register via `__init_subclass__` (imported in `cli.py`):

| Provider | Check Type | Source |
|----------|-----------|--------|
| `dns` | DOMAIN | DNS socket resolution, no API key |
| `rdap` | DOMAIN | RDAP → DNS → raw WHOIS cascading fallback |
| `whois` | WHOIS | Raw socket WHOIS (port 43) |
| `social` | SOCIAL | HTTP HEAD checks (GitHub, Twitter/X, Instagram) |
| `uspto` | TRADEMARK | Supabase Edge Function (exact match) |
| `trademark-similarity` | TRADEMARK | Supabase Edge Function (trigram fuzzy match) |

**Environment variables for providers:**
- `NAMERA_TRADEMARK_API_URL` — override trademark endpoint (default: Supabase Edge Function)

## Scoring Engine

Multi-signal weighted ranking in `scoring/`:

1. Provider results normalized to `Signal` objects (0–1 value)
2. Local signals computed for free: length, pronounceability, string quality
3. Signals weighted by profile, optional hard filters applied
4. Names sorted by composite score (non-filtered first)

**Built-in profiles** (`scoring/profiles.py`):
- `default` — balanced (domain_com 20%, trademark 20%, length 10%, pronounceability 10%)
- `startup-saas` — prioritizes .com (25%), hard filter: `domain_com >= 0.5`
- `fintech` — heavy trademark (25%), hard filter: `trademark >= 0.5`
- `consumer` — social handles (15%), pronounceability (15%)
- `developer-tools` — weights .dev/.io, GitHub handle

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
- JSON output via `--format json` — use `output.py` for rendering
