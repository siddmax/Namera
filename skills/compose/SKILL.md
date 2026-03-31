---
name: namera:compose
description: Generate domain name permutations from keywords with optional availability checking.
allowed-tools:
  - Bash
  - Read
---

# /namera:compose — Name Permutations

You are running the Namera compose flow. Your job is to generate domain name variations from keywords and optionally check their availability.

## Workflow

### Step 1: Get keywords

Ask the user for:
- **Keywords** — the base words to build names from (required)
- **Prefixes/suffixes** — any custom ones they want (optional)
- **Use common prefixes/suffixes?** — adds get, try, my, app, hq, hub, etc. (optional)
- **TLDs** — which TLDs to generate for (default: .com)
- **Check availability?** — whether to also run DNS checks (optional)

If the user already provided keywords in their message, skip the questions.

### Step 2: Run the command

```bash
source /Users/Tanzim/Documents/Vibe\ Code/Claude\ Code/Namera/.venv/bin/activate && \
namera compose <keyword1> <keyword2> \
  --common-prefixes --common-suffixes \
  --tlds com,io \
  --check --json
```

**Flags:**
- `--prefix <p>` / `--suffix <s>` — custom affixes (repeatable)
- `--common-prefixes` / `--common-suffixes` — include standard affixes
- `--tlds com,io` — TLDs to generate
- `--check` — also run availability checks
- `--json` — structured output
- `--max-length 15` — limit domain label length

### Step 3: Present results

If `--check` was used:
- Group results by available vs taken
- Highlight the best available options
- Note total generated vs available count

If no check:
- Show the full list of generated domains
- Suggest running with `--check` to verify availability
