---
name: namera:search
description: Run all checks (domain, WHOIS, trademark) on a single name.
allowed-tools:
  - Bash
  - Read
---

# /namera:search — Single Name Check

You are running the Namera search flow. Your job is to run comprehensive checks on a single name.

## Workflow

### Step 1: Get the name

Ask the user which name they want to check. If they already provided it in their message, proceed directly.

### Step 2: Run the command

```bash
source /Users/Tanzim/Documents/Vibe\ Code/Claude\ Code/Namera/.venv/bin/activate && \
doppler run -- namera search <name> --json --tlds com,net,org,io,dev
```

**Options:**
- `--tlds com,io,dev` — which TLDs to check (default: com,net,org,io,dev)
- `--json` — structured output
- `-a` / `--only-available` — show only available results
- `--verbose` — include extra context in output

**Important:**
- Use `doppler run --` for trademark checks
- Activate the virtualenv first

### Step 3: Present results

Parse the JSON and present a clear summary:

1. **Domain availability** — list each TLD with available/taken status
2. **WHOIS info** — registration details if taken
3. **Trademark status** — any conflicts found in USPTO database

Give a clear verdict: is this name safe to use? Flag any risks (trademark conflicts, all TLDs taken, etc.).
