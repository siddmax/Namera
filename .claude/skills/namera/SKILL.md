---
name: namera
description: Check name availability across domains, trademarks, and social handles. Use when the user wants to check if a business name is available, find available names, rank name candidates, or generate domain name ideas. Triggers on "check name", "is X available", "find a name", "rank names", "domain check".
argument-hint: <name or business description>
---

# Namera - Name Availability Checker

Run name availability checks using the `namera` CLI. Always activate the venv first.

## Quick Reference

```
source .venv/bin/activate
```

Run all namera commands from the project root (`/Users/sidsharma/Namera`).

**Single name check:**
```bash
namera search <name> --json
```

**Multiple names with context (primary agent workflow):**
```bash
namera find --json --context '<BusinessContext JSON>'
```

**Rank and compare names:**
```bash
namera rank --json <name1> <name2> <name3>
namera rank --json --profile fintech <name1> <name2>
```

**Generate domain permutations:**
```bash
namera compose <keyword> --common-suffixes --tlds com,io --check --json
```

## Workflow

### 1. Gather Context

Ask the user for:
- What they're building (becomes `description`)
- Name candidates they're considering (becomes `name_candidates`)
- Industry/niche if not obvious (becomes `niche`)

### 2. Build BusinessContext JSON

Minimum viable:
```json
{"name_candidates": ["name1", "name2"]}
```

Recommended (much better results):
```json
{
  "description": "What the business does",
  "name_candidates": ["name1", "name2"],
  "niche": "fintech",
  "checks": ["domain", "trademark"],
  "scoring_profile": "default"
}
```

See [reference.md](reference.md) for all fields and scoring profiles.

### 3. Run Check

```bash
cd /Users/sidsharma/Namera && source .venv/bin/activate && namera find --json --context '<JSON>'
```

Parse the JSON output. Handle exit codes:
- 0 = success
- 1 = input error (bad JSON, no candidates)
- 2 = partial failure (some checks failed)
- 3 = all checks failed (network error)

### 4. Present Results

From the JSON output, highlight:
- **Top available names** with composite scores
- **Trademark risks** (any name with trademark conflicts)
- **Domain availability** per TLD (.com, .io, etc.)
- **Recommendation** with reasoning based on scores

### 5. Follow Up

Offer to:
- Run `namera rank --json --profile <profile> <names>` for deeper comparison
- Run `namera compose <keyword> --common-suffixes --check --json` for more variations
- Check specific TLDs: `namera domain <name> --tlds tech,ai,dev --json`

## Scoring Profiles

Use `--profile <name>` with `namera rank`:
- `default` -- balanced (domain 20%, trademark 20%, length 10%, pronounceability 10%)
- `startup-saas` -- prioritizes .com (25%), hard filter: .com must be available
- `fintech` -- heavy trademark weight (25%), hard filter: trademark must be clear
- `consumer` -- social handles (15%), pronounceability (15%)
- `developer-tools` -- weights .dev/.io, GitHub handle

## Output Parsing

JSON output from `namera find --json` returns:
```json
{
  "results": [
    {
      "check_type": "domain",
      "provider": "dns",
      "query": "name.com",
      "available": "available|taken|unknown",
      "details": {...}
    }
  ]
}
```

JSON output from `namera rank --json` returns:
```json
{
  "ranked": [
    {"name": "x", "score": 0.85, "signals": {"domain_com": 1.0, "trademark": 1.0}}
  ]
}
```
