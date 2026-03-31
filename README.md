# Namera

Name your startup like a YC founder. Namera is a CLI tool that generates domain name ideas, checks availability and pricing across TLDs, screens for trademark conflicts, and ranks everything — so you pick from the best options, not all of them.

## What It Does

1. **Describe your business** — pass context about what you're building, your niche, audience, and preferences
2. **Generate name candidates** — compose names from keywords with prefixes, suffixes, and permutations
3. **Check everything** — domain availability, WHOIS, RDAP, trademark status, and social handles
4. **Get ranked results** — names are scored by availability, pricing, trademark safety, and string quality, giving you the top picks

```
 Ranked results: namera
┌──────┬────────────┬───────┬────────────┬───────────┐
│ Rank │ Name       │ Score │ .com       │ Trademark │
├──────┼────────────┼───────┼────────────┼───────────┤
│  1   │ getnamera  │  92   │ Available  │  Clear    │
│  2   │ trynamera  │  87   │ Available  │  Clear    │
│  3   │ namerahq   │  84   │ Available  │  Clear    │
└──────┴────────────┴───────┴────────────┴───────────┘
```

## Install

```bash
git clone https://github.com/siddmax/Namera.git
cd Namera
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Claude Code Plugin

Use Namera directly inside Claude Code with `/namera:find`, `/namera:rank`, `/namera:compose`, and `/namera:search`.

### Install the plugin

```bash
claude plugin install https://github.com/siddmax/Namera.git
```

### Skills

| Skill | What it does |
|---|---|
| `/namera:find` | Full discovery — business context to ranked available names |
| `/namera:compose` | Generate domain name permutations from keywords |
| `/namera:rank` | Score and rank name candidates |
| `/namera:search` | Run all checks (domain, WHOIS, trademark) on a single name |

### Example

```
> /namera:find

What are you building?
> A mobile-first budget tracker for Gen Z

Name ideas?
> splitly, buddi, pennypact

# Returns ranked results with domain, trademark, and social availability
```

## Commands

### `find` — Discover names with business context

The main command for AI agents and structured input. Pass a JSON context with your business info and name candidates.

```bash
# See the full JSON schema
namera find --example

# Run a search
namera find --context '{"name_candidates": ["voxly", "dataprime"], "description": "fintech analytics platform", "niche": "finance"}'

# Only show available names
namera find --context '...' --only-available

# Output as JSON, CSV, or NDJSON
namera find --context '...' --format json
```

### `compose` — Generate name permutations from keywords

```bash
# Add common prefixes and suffixes
namera compose namera --common-prefixes --common-suffixes

# Custom prefixes/suffixes with availability check
namera compose namera --prefix get --prefix try --suffix hq --check

# Specify TLDs
namera compose namera --common-suffixes --tlds com,io

# Output as JSON
namera compose namera --common-prefixes --json
```

### `rank` — Score and rank name candidates

```bash
# Rank multiple names
namera rank voxly dataprime nimbus

# Rank with a scoring profile
namera rank voxly dataprime --profile fintech

# Rank with full business context
namera rank --context '{"name_candidates": ["voxly"], "niche": "fintech"}' --json
```

### `search` — Run all checks on a single name

```bash
namera search myname
namera search myname --tlds com,io,ai
```

### `domain` — Check domain availability

```bash
namera domain myname
namera domain myname --tlds com,ai,app
```

### `whois` — WHOIS lookup

```bash
namera whois myname.com
```

### `trademark` — Trademark check

```bash
namera trademark myname
```

### `presets` — View TLD presets

```bash
namera presets
```

Available presets: `popular`, `tech`, `startup`, `cheap`, `premium`, `finance`, `design`, `security`, `gaming`, `social`, `ecommerce`, `education`, `health`, `food`, `travel`, `media`, `creative`, `geo-us`, `geo-eu`, `geo-asia`

Use presets anywhere TLDs are accepted:

```bash
namera compose myname --tlds startup --check
namera rank myname --tlds fintech
```

## Configuration

Namera uses environment variables for API keys. None are required for basic lookups.

| Variable | Required | What it does |
|----------|----------|-------------|
| `GODADDY_API_KEY` | No | Enables domain pricing via GoDaddy API |
| `GODADDY_API_SECRET` | No | Paired with the API key above |
| `GODADDY_ENV` | No | `production` or `ote` (default: `ote`) |
| `SUPABASE_URL` | No | Supabase URL for trademark database |
| `SUPABASE_SERVICE_ROLE_KEY` | No | Supabase key for trademark lookups |

## Architecture

```
src/namera/
  cli.py                          # CLI entry point (Click)
  composer.py                     # Name permutation generator
  context.py                      # Business context parser
  filters.py                      # Result filtering
  output.py                       # Output formatting (table, JSON, CSV)
  presets.py                      # TLD preset definitions
  runner.py                       # Concurrent provider runner
  cache.py                        # Result caching
  retry.py                        # Retry logic for providers
  session.py                      # Session management
  theme.py                        # Terminal theme/colors
  telemetry.py                    # Usage telemetry
  scoring/
    engine.py                     # Scoring engine
    models.py                     # Score data models
    local_signals.py              # String quality analysis (length, pronounceability)
    normalizers.py                # Score normalization
    profiles.py                   # Scoring profiles (fintech, tech, etc.)
  providers/
    base.py                       # Provider ABC + auto-registration
    domain.py                     # DNS-based domain check
    domain_api.py                 # GoDaddy API (availability + pricing)
    rdap.py                       # RDAP protocol lookup
    whois.py                      # Raw socket WHOIS lookup
    social.py                     # Social handle availability
    trademark.py                  # Trademark check (stub)
    trademark_supabase.py         # Trademark check via Supabase
```

### Adding a provider

1. Create `src/namera/providers/yourprovider.py`
2. Subclass `Provider`, set `name` and `check_type`
3. Implement `async def check(self, query, **kwargs) -> ProviderResult`
4. Import it in `cli.py` — it auto-registers, no wiring needed

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v                      # run tests
ruff check src/ tests/                # lint
```

To import trademark data into Supabase:

```bash
pip install -e ".[import]"
python scripts/import_trademarks.py
```

## Tech Stack

- Python 3.10+
- [Click](https://click.palletsprojects.com/) — CLI framework
- [Rich](https://rich.readthedocs.io/) — terminal UI and tables
- [httpx](https://www.python-httpx.org/) — async HTTP
- [Supabase](https://supabase.com/) — trademark database (optional)

## License

MIT
