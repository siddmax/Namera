# Namera Claude Code Plugin — Plan

## Goal

Convert Namera CLI into a Claude Code plugin so anyone can install it and use `/namera:find`, `/namera:rank`, etc. directly in Claude Code.

## Structure

```
Namera/
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest (name, version, description)
├── skills/
│   ├── find/
│   │   └── SKILL.md             # /namera:find — full discovery flow
│   ├── compose/
│   │   └── SKILL.md             # /namera:compose — name permutations
│   ├── rank/
│   │   └── SKILL.md             # /namera:rank — score & rank names
│   └── search/
│       └── SKILL.md             # /namera:search — check a single name
├── marketplace.json             # So anyone can install via marketplace URL
└── ... (existing code)
```

## Skills

### /namera:find
Full discovery flow — takes business context as natural language, converts to JSON, runs `namera find --context '...'`, returns ranked available names.

### /namera:compose
Name permutations — takes keywords, runs `namera compose` with prefixes/suffixes, optionally checks availability.

### /namera:rank
Score & rank — takes name candidates, runs `namera rank`, returns scored results.

### /namera:search
Single name check — runs `namera search` for domain, WHOIS, and trademark on one name.

## Each SKILL.md Will

1. Have YAML frontmatter (name, description, allowed-tools)
2. Instruct Claude to use `namera` CLI commands via Bash
3. Handle the case where Namera isn't installed (auto-install via `pip install`)
4. Format results nicely for the user

## How Users Install

```bash
claude /marketplace add-url https://raw.githubusercontent.com/siddmax/Namera/master/marketplace.json
claude /plugin install namera
```

Then invoke: `/namera:find`, `/namera:rank`, `/namera:compose`, `/namera:search`

## Steps

1. Create `.claude-plugin/plugin.json` manifest
2. Create 4 skill files (find, compose, rank, search)
3. Create `marketplace.json` at repo root
4. Update README with install instructions
5. Push to GitHub
