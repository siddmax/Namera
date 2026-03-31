# Namera

Name your startup like a YC founder. Namera is a CLI tool that generates short, punchy business names, checks domain availability with pricing, and screens for trademark conflicts — all from your terminal.

## What It Does

1. **Describe your business** — tell Namera what you're building
2. **Answer a few questions** — target audience, vibe, geography, budget
3. **Get name suggestions** — short, memorable, easy to spell (think Stripe, Vercel, Figma)
4. **Ranked results** — names are scored and ranked by domain availability, pricing, and trademark status, giving you the top 10 to choose from

```
 Name suggestions + availability
┌──────────┬──────┬──────┬──────┬─────────┬───────────┐
│ Name     │ .com │ .ai  │ .app │ Price   │ Trademark │
├──────────┼──────┼──────┼──────┼─────────┼───────────┤
│ Trekr    │  ✓   │  ✓   │  ✓   │  $12.99 │  Unknown  │
│ Volo     │  ✗   │  ✓   │  ✓   │  $29.00 │  Unknown  │
│ Nexora   │  ✓   │  ✓   │  ✗   │  $10.99 │  Unknown  │
└──────────┴──────┴──────┴──────┴─────────┴───────────┘
```

## Install

```bash
git clone https://github.com/siddmax/Namera.git
cd Namera
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Quick Start

### Generate names with AI

```bash
export ANTHROPIC_API_KEY=sk-ant-...    # required for AI naming
namera generate
```

Options:

```bash
namera generate --tlds com,ai,app     # specify TLDs to check (default: com,ai,app)
namera generate --budget 50           # set max domain price in USD
```

### Check a specific name

```bash
namera search myname                  # run all checks (domain, whois, trademark)
namera domain myname                  # domain availability only
namera domain myname --tlds com,io    # specific TLDs
namera whois myname.com               # WHOIS lookup
namera trademark myname               # trademark check
```

## Configuration

Namera uses environment variables for API keys. None are required for basic lookups — API keys unlock richer results.

| Variable | Required | What it does |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | For `generate` | Powers AI name generation via Claude |
| `GODADDY_API_KEY` | No | Enables domain pricing (falls back to DNS without it) |
| `GODADDY_API_SECRET` | No | Paired with the API key above |
| `GODADDY_ENV` | No | `production` or `ote` (default: `ote` for testing) |

## How It Works

Namera has a modular provider system. Each lookup (domain, WHOIS, trademark) is a provider that can be swapped or extended independently.

```
src/namera/
  cli.py                  # CLI entry point (Click)
  agent.py                # AI naming agent (Claude)
  ranker.py               # Scoring algorithm — ranks names by availability, price, trademark
  providers/
    base.py               # Provider ABC + auto-registration
    domain.py             # DNS-based domain check
    domain_api.py         # GoDaddy API (availability + pricing)
    whois.py              # Raw socket WHOIS lookup
    trademark.py          # Trademark check (stub)
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

## Tech Stack

- Python 3.10+
- [Click](https://click.palletsprojects.com/) — CLI framework
- [Rich](https://rich.readthedocs.io/) — terminal UI and tables
- [httpx](https://www.python-httpx.org/) — async HTTP
- [Anthropic SDK](https://docs.anthropic.com/en/docs/sdks) — AI name generation

## License

MIT
