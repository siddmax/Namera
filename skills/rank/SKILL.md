---
name: namera:rank
description: Score and rank name candidates using domain, trademark, social, and linguistic signals.
allowed-tools:
  - Bash
  - Read
---

# /namera:rank — Score & Rank Names

You are running the Namera ranking flow. Your job is to score and rank name candidates across multiple signals.

## Workflow

### Step 1: Get candidates

Ask the user for:
- **Name candidates** — the names to rank (required, at least 2)
- **Niche/context** — optional business context for relevance scoring

If the user already provided names in their message, skip the questions.

### Step 2: Run the command

**Simple (names as arguments):**
```bash
source /Users/Tanzim/Documents/Vibe\ Code/Claude\ Code/Namera/.venv/bin/activate && \
doppler run -- namera rank name1 name2 name3 --json
```

**With context (for better scoring):**
```bash
source /Users/Tanzim/Documents/Vibe\ Code/Claude\ Code/Namera/.venv/bin/activate && \
doppler run -- namera rank --json --context '{
  "name_candidates": ["name1", "name2", "name3"],
  "niche": "fintech"
}'
```

**Important:**
- Use `doppler run --` for trademark checks
- Use `--json` for parseable output
- Activate the virtualenv first

### Step 3: Present results

Parse the JSON and present a ranked table showing:

1. **Rank** — position by composite score
2. **Name** — the candidate
3. **Score** — composite score (0-1)
4. **Key signals** — .com availability, trademark status, social availability, length, pronounceability

Highlight the top pick and explain why it scored highest. If any names were filtered out (e.g., trademark conflict), explain why.

## Scoring Signals

- **domain_com** — is the .com available?
- **trademark** — any trademark conflicts?
- **social_availability** — social handle availability
- **length** — shorter is generally better
- **pronounceability** — how easy to say/remember
