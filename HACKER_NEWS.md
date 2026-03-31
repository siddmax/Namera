# Hacker News Launch Plan for Namera

## Posting Strategy

### Optimal Time to Post

- **Best day:** Tuesday or Wednesday (weekdays get 2-3x more engagement than weekends on HN)
- **Best time:** **8:00-9:00 AM ET (5:00-6:00 AM PT)** — catches the US East Coast morning + EU afternoon overlap. HN's front page algorithm favors posts that accumulate upvotes quickly in the first 1-2 hours. Posting early morning ET gives you the longest runway of active readers.
- **Avoid:** Friday afternoon, weekends, US holidays
- **Backup slot:** 11:00 AM ET on a Monday or Thursday (still strong, slightly more competition)

### Title

Use the `Show HN` prefix — it routes the post to the dedicated Show HN section and signals "I made this, come try it."

**Recommended title (under 80 chars):**

```
Show HN: Namera – Check domain, WHOIS, and trademark availability from one CLI
```

(78 chars — safe on mobile)

**Alternate titles:**

```
Show HN: Namera – Name availability CLI built for AI agents and humans
Show HN: Namera – CLI for domain + trademark availability checks
```

Keep it factual. Avoid superlatives ("fast", "best", "powerful"). HN readers respond to specificity, not hype.

### Post URL

Link directly to the GitHub repo:

```
https://github.com/siddmax/Namera
```

HN strongly prefers GitHub links for Show HN posts — it lets people read the code immediately. Do NOT link to a landing page unless it has a live demo.

### Post Body (Show HN Text)

HN Show posts allow a text body in addition to the URL. Keep it **3-5 short paragraphs**, casual tone, first person. The tldx post that did well (90 points, 33 comments) was only 2-3 sentences. Slightly longer is fine if it adds substance.

---

**Draft post body:**

> I built Namera because I kept doing the same thing every time I started a new project — googling domain names one by one, running whois in the terminal, checking the USPTO site manually. It's a CLI that runs domain (DNS), WHOIS, and trademark checks from one command.
>
> The part I'm most interested in feedback on: there's a `find` command that takes business context as JSON — your name candidates, niche, target audience, preferred TLDs — and runs all checks at once, scoring results by relevance. The idea is that AI agents (Claude Code, Codex, etc.) can call `namera find --json --context '{...}'` as a tool.
>
> It auto-selects TLDs based on your niche (fintech gets .finance, .money; gaming gets .gg; AI gets .ai). No API keys needed — domain checks are DNS-based and WHOIS uses raw socket queries. Trademark is currently a stub (the USPTO API is painful to work with — would love suggestions here).
>
> Python, MIT licensed. Happy to hear what's missing or broken.

---

### Why This Draft Works

| HN principle | How the draft applies it |
|---|---|
| **Show the problem first** | Opens with the pain point (manual name checking) — readers relate before seeing the solution |
| **Be specific about features** | Names concrete capabilities (DNS, WHOIS, trademark, niche-aware TLDs, relevance scoring) |
| **Mention the novel angle** | AI-agent integration as a tool — this is the differentiator vs. tldx and other domain checkers |
| **End with an invitation** | "Happy to hear what's missing" — invites constructive comments, which drives engagement |
| **No API keys needed** | Removes friction — readers can actually try it |
| **Casual, not salesy** | First person, no buzzwords, no "we're thrilled to announce" |

### Post Length Guidelines

- **Title:** Under 80 characters. Factual. Include the core value prop.
- **Body:** 100-200 words. 3-5 short paragraphs. No bullet lists in the post itself (save those for comments).
- **Don't:** Paste your full README. Don't list every feature. Don't include install instructions in the post body — that's what the repo link is for.

## First Comment Strategy

Post a comment on your own submission immediately after posting. This seeds the discussion and gives you a place to add detail without bloating the main post.

**Draft first comment:**

> Some things I'm thinking about adding next and would love input on:
>
> - RDAP support (WHOIS is being deprecated by many registrars)
> - Social handle availability (Twitter/X, GitHub, npm)
> - Actual trademark API integration (currently a stub — the USPTO API is... not great)
> - Domain price estimation
>
> If you're building agent tooling or naming workflows, I'm curious what checks you'd want exposed as a CLI tool. Right now the provider system is pluggable — you subclass `Provider`, set a name, and it auto-registers.

This comment:
1. Shows you have a roadmap (project is active, not abandonware)
2. Invites specific feedback (not just "what do you think?")
3. Highlights the plugin architecture (appeals to HN's builder audience)
4. Mentions RDAP — the tldx thread showed this is a hot topic on HN

## Repost Strategy

If the post dies in /new (under ~5 points in 30 min), you can repost with the same or tweaked title after **~2 days**. HN explicitly allows this. Many successful Show HN posts succeeded on the 2nd or 3rd try. Vary the posting time — if Tuesday 8 AM ET didn't work, try Wednesday 11 AM ET.

## Anticipated Objections & Prepared Responses

**"Why not just use `whois` and `dig`?"**
> That's exactly what I was doing before. Namera wraps the same underlying checks but runs them in parallel across multiple TLDs and name candidates, adds relevance scoring, and outputs structured JSON so agents can consume it. If you're checking one domain, `dig` is fine. If you're evaluating 5 name candidates across 6 TLDs with trademark checks, that's 30+ manual commands.

**"The trademark check is a stub?"**
> Yeah, currently it's a placeholder. The USPTO API requires XML/SOAP and doesn't have a clean REST endpoint. I'm looking at alternatives (Trademarkia API, EUIPO). PRs welcome if anyone has experience here.

**"How is this different from tldx?"**
> tldx is focused on domain TLD enumeration. Namera is broader — it checks domains + WHOIS + trademarks in one shot, scores by business context (niche, audience), and is designed as a tool for AI agents via `--json` output. Think of it as tldx + whois + trademark + business logic.

**"DNS resolution isn't a reliable way to check domain availability"**
> Fair point — a domain can be registered but not resolve (parked, no DNS records). DNS is a fast first pass; the WHOIS check catches the rest. Planning to add RDAP as a more authoritative source.

## Engagement Tips

- **Respond to every comment** in the first 2-3 hours. HN's algorithm weighs comment activity.
- **Be receptive to criticism.** "Good point, I'll look into that" beats "actually, here's why you're wrong."
- **If someone asks for a feature, ship it fast.** The tldx author added RDAP support during the HN discussion and it drove more upvotes.
- **Don't ask friends to upvote.** HN detects vote rings and will kill your post. Sharing the link is fine; coordinated upvoting is not.
- **Don't edit the title** after posting unless there's a factual error. Edits can reset ranking.

## Pre-Launch Checklist

Before posting, make sure the repo is ready for traffic:

### Blockers (must-have before posting)

- [ ] **LICENSE file at repo root** — currently missing. Add `LICENSE` (MIT text) to the repo root
- [ ] **README overhaul** — current README is 19 lines with no mention of `find`. Needs:
  - One-paragraph description
  - Install instructions (`pip install namera`)
  - Quick usage examples for `search`, `domain`, and `find --context`
  - A terminal recording (GIF or asciinema link) — see below
  - The `find` command with context JSON example — this is the differentiator
- [ ] **Terminal recording** — use [vhs](https://github.com/charmbracelet/vhs) or [asciinema](https://asciinema.org/) to record a demo. Show: `namera search coolname` (basic), then `namera find --context '{"name_candidates": ["neopay"], "niche": "fintech"}'` (the wow moment). Embed the GIF in the README.
- [ ] All tests pass (`pytest`)
- [ ] No secrets or personal paths in the code

### Nice-to-have

- [ ] Publish to PyPI so `pip install namera` works without cloning
- [ ] GitHub repo description and topics set (e.g., "cli", "domain", "naming", "developer-tools")
- [ ] GitHub Actions CI (pytest + ruff) — green badge builds trust
- [ ] `.gitignore` covers `.venv/`, `__pycache__/`, `*.egg-info/`
