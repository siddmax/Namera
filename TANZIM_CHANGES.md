# Tanzim's Contributions — Namera

## What I Built

Two of the core services for Namera: the **naming agent** and the **domain lookup service**.

---

### 1. Naming Agent (`src/namera/agent.py`)

The AI-powered engine that generates YC-style business names.

**How it works:**
- User describes their business via `namera generate` CLI command
- Claude (Sonnet) asks 2-3 clarifying questions (target audience, vibe, geography, budget)
- After answers, generates exactly 10 YC-style name suggestions
- Each name is automatically checked against all registered providers (domain availability, WHOIS, trademark)
- Results displayed in a rich table showing availability per TLD, pricing, and trademark status

**Key components:**
- `SYSTEM_PROMPT` — Instructs Claude on YC naming style (short, punchy, memorable — think Stripe, Vercel, Figma)
- `_extract_names(text)` — Parses JSON name arrays from Claude's responses
- `check_name(name, tlds, price_max)` — Runs a single name through all providers
- `check_all_names(names, tlds, price_max)` — Runs all names concurrently via asyncio.gather
- `run_conversation(on_assistant_message, on_user_input)` — The interactive conversation loop with callback hooks for UI

**Env var required:** `ANTHROPIC_API_KEY`

---

### 2. Domain Lookup Service (`src/namera/providers/domain_api.py`)

Real domain availability + pricing via GoDaddy API.

**How it works:**
- Checks domain availability for each name across specified TLDs (default: .com, .ai, .app)
- Returns availability status, price in USD, and whether it's within the user's budget
- Falls back to DNS resolution automatically when no GoDaddy API key is set

**Provider: `GoDaddyDomainProvider`**
- Name: `domain-api`
- Supports both GoDaddy OTE (testing) and Production environments
- Budget filtering: pass `price_max` to flag domains over budget

**Env vars (optional — falls back to DNS without them):**
- `GODADDY_API_KEY`
- `GODADDY_API_SECRET`
- `GODADDY_ENV` — `"production"` or `"ote"` (default: ote)

---

### 3. CLI Command (`namera generate`)

Added to `src/namera/cli.py`:

```bash
namera generate                    # Interactive name generation
namera generate --tlds com,ai,app  # Specify TLDs to check
namera generate --budget 50        # Set max domain price in USD
```

**Output:** Rich table with columns: Name | .com | .ai | .app | Price | Trademark
- Green ✓ = available, Red ✗ = taken, Yellow ? = error
- Price shown for cheapest available domain
- Red price = over budget

---

### 4. Modified Files

| File | Change |
|------|--------|
| `pyproject.toml` | Added `anthropic>=0.40` dependency |
| `src/namera/cli.py` | Added `generate` command + domain_api import |

### 5. Tests Added

| File | Tests |
|------|-------|
| `tests/test_agent.py` | 4 tests — JSON name extraction (block, inline, missing, surrounding text) |
| `tests/test_domain_api.py` | 2 tests — DNS fallback behavior, result structure |

All 6 tests pass. Lint clean via ruff.

---

## How to Test Locally

```bash
cd Namera
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v              # Run tests

# Try the generate command (needs Anthropic API key)
export ANTHROPIC_API_KEY=sk-ant-...
namera generate
```

## Architecture Notes

- The naming agent uses Sidd's provider pattern — auto-registration via `__init_subclass__`
- Domain API provider follows the same `Provider` ABC as all other providers
- The agent imports providers explicitly so they register before checking names
- `run_conversation()` uses callbacks so the CLI can control rendering (Rich panels/tables)
