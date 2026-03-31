---
name: namera:find
description: Full name discovery flow — takes business context, checks availability across domains, trademarks, and social, returns ranked results.
allowed-tools:
  - Bash
  - Read
---

# /namera:find — Name Discovery

You are running the Namera name discovery flow. Your job is to help the user find and validate name candidates for their project or business.

## Workflow

### Step 1: Gather Context

Ask the user what they're building. You need at minimum:
- **Name candidates** — the names they want to check
- **Description** — what the product/business does (1-2 sentences is fine)

Optional but helpful:
- **Niche** — industry keyword (e.g., "fintech", "health", "devtools")
- **Target audience** — who it's for
- **Preferred TLDs** — e.g., .com, .io, .dev
- **Name style** — short, compound, invented, etc.

If the user already provided this context in their message, skip the questions and proceed.

### Step 2: Ensure Namera is installed

Check if `namera` is available:

```bash
which namera || pip install -e /path/to/namera
```

If not installed and the repo is local, install from the local path. Otherwise:

```bash
pip install namera
```

### Step 3: Build and run the command

Construct a `namera find` command with the context as JSON:

```bash
source /Users/Tanzim/Documents/Vibe\ Code/Claude\ Code/Namera/.venv/bin/activate && \
doppler run -- namera find --json --context '{
  "description": "<user description>",
  "name_candidates": ["name1", "name2", "name3"],
  "niche": "<niche>",
  "target_audience": "<audience>",
  "preferred_tlds": ["com", "io"],
  "checks": ["domain", "whois", "trademark"]
}'
```

**Important:**
- Always use `--json` for structured output you can parse
- Use `doppler run --` prefix to inject Supabase credentials for trademark checks
- Activate the virtualenv first

### Step 4: Present results

Parse the JSON output and present results clearly:

1. **Top recommendations** — names with best overall scores (domain available + no trademark conflicts)
2. **Domain availability** — which TLDs are available for each name
3. **Trademark status** — any conflicts found
4. **Your recommendation** — based on the scores, suggest the best 1-2 names and why

Format as a clean summary, not raw JSON. Highlight the winner.

## Error Handling

- If `namera` is not installed, install it first
- If Doppler is not configured, skip trademark checks: remove `"trademark"` from checks
- If a name has 0 results, it likely timed out — suggest retrying with `--timeout 30`
