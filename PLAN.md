# Namera Claude Code Command — Plan

## Goal

Make Namera available as a single `/namera` slash command in Claude Code that handles the full naming flow: context gathering, name generation, availability checks, trademark screening, ranking, and iteration.

## Structure

```
Namera/
├── .claude/
│   └── commands/
│       └── namera.md           # /namera — full naming flow
└── ... (existing code)
```

## How It Works

The `/namera` command is a single Claude Code custom slash command that orchestrates the entire naming workflow:

1. Gathers business context conversationally
2. Generates name candidates if the user needs help
3. Runs `namera find --json --context '...'` to check everything
4. Presents ranked results with domain, trademark, and scoring info
5. Offers iteration — variations via `compose`, deep checks via `search`, re-ranking via `rank`

## How Users Install

```bash
git clone https://github.com/siddmax/Namera.git
ln -s /path/to/Namera/.claude/commands/namera.md ~/.claude/commands/namera.md
```

Then invoke: `/namera`

## Steps

1. ~~Create fake plugin structure~~ (removed — not a real Claude Code feature)
2. [x] Create single `.claude/commands/namera.md` slash command
3. [x] Update README with real install instructions
4. [ ] Test locally
5. [ ] Push to GitHub
