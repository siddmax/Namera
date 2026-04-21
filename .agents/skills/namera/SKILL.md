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
- Industry/niche if not obvious (becomes `niche`)
- Any name candidates they already have in mind (optional — you'll generate more)

### 2. Generate Name Candidates

**This is your job as the agent.** Don't just ask the user for names — generate 10-15 candidates yourself based on the business context. Include any names the user already suggested.

**What research says works:**
- **4-8 chars, 1-2 syllables** — 37% higher recall vs longer names (HBR). Apple(5), Uber(4), Zoom(4), Stripe(6).
- **CVCV patterns** — alternating consonant-vowel ("Nura", "Voxly", "Zesti") maximizes pronounceability. Zero-shot test: if you hesitate saying it, customers will too.
- **Sound symbolism matters** — soft sounds (b, g, l, m, o) → friendly/reliable (bouba). Hard sounds (k, t, z) → precise/modern (kiki). Match the brand personality.
- **Portmanteaus trending** — word blends pack double meaning: "Splitly" (split+ly), "Groupon" (group+coupon). Works because they're novel yet parseable.
- **Coined words find domains** — invented names are far more likely to have .com available than real words.

**Generation mix (aim for 10-15):**
- ~5 coined CVCV words matching the brand's sound personality
- ~3 relevant word blends/portmanteaus from the business description
- ~3 evocative real words repurposed ("Harbor", "Canopy", "Forge")
- ~2 keyword + suffix ("PayHQ", "BudgetApp") as practical fallbacks
- Include any names the user already suggested

### 3. Build BusinessContext JSON and Run Check

```json
{
  "description": "What the business does",
  "name_candidates": ["generated1", "generated2", "userSuggested1"],
  "niche": "fintech",
  "checks": ["domain", "trademark"],
  "scoring_profile": "default"
}
```

See [reference.md](reference.md) for all fields and scoring profiles.

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
- Generate another batch of candidates if nothing resonates
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
    {"name": "x", "score": 87.0, "signals": {"domain_com": 100.0, "trademark": 100.0}}
  ]
}
```

Scores are 0-100 scale (100 = best).
