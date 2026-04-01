# Namera Reference

## BusinessContext JSON Schema

```json
{
  "description": "string - What the business does (recommended)",
  "name_candidates": ["string[] - Names to check (required)"],
  "niche": "string - Industry keyword: fintech, health, tech, gaming, etc. (recommended)",
  "target_audience": "string - Who it's for (optional)",
  "location": "string - Country/region (optional)",
  "preferred_tlds": ["string[] - Override auto-detected TLDs (optional)"],
  "max_domain_price": 50.0,
  "name_style": "string - short, descriptive, etc. (optional)",
  "checks": ["domain", "whois", "trademark", "social"],
  "scoring_profile": "default|startup-saas|fintech|consumer|developer-tools",
  "weight_overrides": {"trademark": 0.3},
  "industry": "string - Additional industry context (optional)"
}
```

**Required:** `name_candidates`
**Recommended:** `description`, `niche`

## All CLI Commands

| Command | Purpose |
|---------|---------|
| `namera find --json --context '<json>'` | Full pipeline: check + rank multiple names |
| `namera rank --json [--profile X] name1 name2` | Score and rank names |
| `namera search <name> --json` | All checks for single name |
| `namera domain <name> --json --tlds com,io` | Domain availability only |
| `namera trademark <name> --json` | USPTO trademark check only |
| `namera whois <name> --json` | WHOIS lookup only |
| `namera compose <kw> --common-suffixes --check --json` | Generate + check domains |
| `namera presets` | Show TLD presets |

All commands support `--format table|json|ndjson|csv` and `--json` shorthand.

## Providers

| Provider | Check Type | Source |
|----------|-----------|--------|
| `dns` | domain | DNS socket, no API key |
| `rdap` | domain | RDAP with cascading fallbacks |
| `whois` | whois | Raw socket WHOIS (port 43) |
| `social` | social | HTTP checks (GitHub, Twitter/X, Instagram) |
| `uspto` | trademark | Supabase Edge Function (exact) |
| `trademark-similarity` | trademark | Supabase Edge Function (fuzzy) |

## Scoring Profile Weights

| Signal | default | startup-saas | fintech | consumer | dev-tools |
|--------|---------|-------------|---------|----------|-----------|
| domain_com | 0.20 | 0.25 | 0.20 | 0.15 | 0.10 |
| trademark | 0.20 | 0.15 | 0.25 | 0.15 | 0.15 |
| length | 0.10 | 0.10 | 0.10 | 0.10 | 0.10 |
| pronounceability | 0.10 | 0.10 | 0.10 | 0.15 | 0.05 |
| string_features | 0.10 | 0.10 | 0.10 | 0.10 | 0.10 |
| social_availability | 0.10 | 0.10 | 0.05 | 0.15 | 0.05 |

**Hard filters:**
- `startup-saas`: domain_com >= 0.5
- `fintech`: trademark >= 0.5

## TLD Auto-Detection (via niche)

| Niche | Auto TLDs |
|-------|-----------|
| fintech | com, io, finance, money, co |
| tech/saas | com, io, dev, app, tech |
| health | com, health, care, io |
| gaming | com, gg, io, game, play |
| education | com, edu, io, academy |

Or use `--tlds <preset>` with preset names: `popular`, `tech`, `startup`, `fintech`, `gaming`, `geo-us`, etc.
