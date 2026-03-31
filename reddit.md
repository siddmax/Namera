# Namera Reddit Launch Strategy

---

## Optimal Posting Time

**Tuesday, Wednesday, or Thursday at 8:00 AM ET (5:00 AM PT / 1:00 PM UTC)**

Why this window:
- Tech subreddits peak 6-10 AM ET on weekdays (developers check Reddit at start of workday)
- Secondary peaks at 12-1 PM ET (lunch) and 8-11 PM ET (evening)
- Tuesday-Thursday consistently outperform Monday (slow start) and Friday (weekend mindset)
- Reddit's algorithm heavily weights **early engagement velocity** -- 15 upvotes in 30 minutes beats 100 spread over 12 hours
- This time catches East Coast devs at work, Europeans in their afternoon, and West Coast devs waking up

**Avoid**: Friday evenings, Saturday mornings, 1-5 AM ET

---

## Optimal Subreddits (Tiered Rollout)

Do NOT cross-post to all subreddits at once. Customize the angle per community and space posts 3-4 weeks apart.

### Tier 1 -- Launch Week

| Subreddit | ~Members | Angle | Flair |
|---|---|---|---|
| **r/SideProject** | 200K+ | "I built this" personal story | Project |
| **r/Python** | 2M+ | Python CLI, Click + Rich + httpx, async patterns | Showcase |
| **r/ClaudeAI** | Growing fast | Built for Claude Code tool-use, demo with `--json` | Tool |

### Tier 2 -- Weeks 2-3

| Subreddit | Angle |
|---|---|
| **r/commandline** | CLI UX, composability, pipe-friendly JSON output |
| **r/opensource** | Open-source, pluggable provider architecture |
| **r/ChatGPTCoding** | AI agent tooling, structured output for LLMs |
| **r/SaaS** | "Free tool for validating SaaS names before you commit" |

### Tier 3 -- Weeks 4+

| Subreddit | Angle |
|---|---|
| **r/coolgithubprojects** | GitHub link, short description |
| **r/alphaandbetausers** | "Looking for feedback on CLI naming tool" |
| **r/webdev** | "Tool for checking if your project name is available" (requires prior engagement history) |
| **r/startups** / **r/Entrepreneur** | Frame as "stop wasting time checking names manually" (outcomes, not tech) |

---

## The Post -- r/SideProject Version

### Title Options (pick one)

1. `I built a CLI that checks domains, WHOIS, and trademarks in one command` (73 chars -- safe)
2. `I got tired of checking 10 sites for name availability, so I built a CLI` (73 chars)
3. `I built Namera: name availability checker designed for AI agents` (64 chars)

**Recommended: Option 2** (pain-driven, specific, under 100 chars for mobile)

> Reddit truncates titles at ~100 characters on mobile. Keep it under 80 to be safe.

### Body

```
I kept running into the same problem: I'd come up with a project name, check the .com,
then the .io, then Google the trademark, then check WHOIS -- and 20 minutes later I'd
find out it was taken everywhere. Repeat for the next 5 names.

So I built **Namera**, an open-source CLI that checks domain availability, WHOIS records,
and trademark status in a single command.

**What it does:**

- `namera search coolname` -- runs domain + WHOIS + trademark checks at once
- `namera find` -- interactive wizard: tell it your niche, audience, and name candidates,
  and it checks everything with relevance scoring
- `namera find --json --context '{"name_candidates": ["neopay"], "niche": "fintech"}'`
  -- structured JSON output designed for AI agents (Claude Code, Codex, etc.)

**Key design decisions:**

- **DNS-direct lookups** -- queries DNS servers directly, no third-party API middlemen
  that could leak your name searches to domain squatters
- **Business context awareness** -- tell it your niche and it automatically picks relevant
  TLDs (fintech? checks .finance, .money, .io. Dev tools? checks .dev, .sh, .tools)
- **Relevance scoring** -- ranks results by availability + TLD preference + .com bonus
- **Pluggable providers** -- add new checks (social media handles, app stores) by
  subclassing one class. Auto-registers, no wiring needed
- **Agent-first design** -- structured JSON input/output so AI coding assistants can
  use it as a tool natively, not parse raw WHOIS text

**Tech stack:** Python, Click (CLI), Rich (terminal UI), httpx (HTTP), asyncio.
All providers are async. `pip install namera` and go.

**What I learned building it:**

Honestly, the hardest part wasn't the checking logic -- it was designing the BusinessContext
input format so an AI agent could express "I need a short fintech name for US millennials,
budget $50 for the domain" in a single JSON blob. Getting that interface right took more
iteration than all the DNS code combined.

GitHub: [link]

I'd love feedback. Specifically:
- **What other checks would be useful?** (social media handles? App Store names? npm/PyPI packages?)
- **Is the BusinessContext format intuitive, or does it need more/fewer fields?**

---
Built with Python. MIT licensed. No telemetry, no accounts, no API keys needed for basic checks.
```

### Immediate Top-Level Comment (post right after submitting)

```
Some technical context for anyone curious about the architecture:

The provider system uses __init_subclass__ for auto-registration -- you create a new
provider file, subclass Provider, and it's available immediately. No import wiring or
plugin config.

The `find` command accepts input three ways: --context flag (for agents), stdin pipe
(for shell scripts), or interactive wizard (for humans). It auto-detects which one you're using.

Happy to go deeper on any of this. The codebase is small enough to read in one sitting.
```

---

## The Post -- r/Python Version

### Title

`Namera: async CLI for checking name availability (domain + WHOIS + trademark) -- built with Click, Rich, and httpx`

### Body (different angle -- emphasize Python patterns)

> Note: Reddit markdown doesn't support nested code fences. Use inline `code` for
> commands inside the post body, and only use fenced blocks for standalone examples.

```
I just open-sourced Namera, a CLI tool for checking name availability across multiple
providers simultaneously.

**Why I'm sharing it here:** The architecture might be interesting even if you don't need
a naming tool. A few patterns I'm happy with:

1. **Auto-registering provider plugins** via `__init_subclass__`. Subclass `Provider`, set
   `name` and `check_type`, implement `async def check()` -- done. No registry boilerplate.

2. **Triple input resolution**: CLI flag > stdin pipe > interactive wizard, auto-detected
   in `_resolve_context()`. Makes the same command work for agents, scripts, and humans.

3. **asyncio.gather for parallel checks**: All providers run concurrently. Adding a new
   provider doesn't increase wall-clock time.

4. **Rich + Click integration**: Rich handles the pretty terminal tables, Click handles
   the CLI structure. They compose cleanly.

Quick usage:

    pip install namera
    namera search coolname --json
    namera find --json --context '{"name_candidates": ["neopay", "zestfi"], "niche": "fintech"}'

GitHub: [link]

What patterns do you use for plugin architectures in CLI tools? I went with
`__init_subclass__` over entry_points or importlib -- curious if others have opinions.
```

---

## The Post -- r/ClaudeAI Version

### Title

`I built a CLI tool that Claude Code can use as a tool to check if names are available (domains, trademarks, WHOIS)`

### Body

```
If you use Claude Code for building projects, one annoying step is figuring out if your
project/company name is actually available. You end up going back and forth between the
terminal and a browser.

I built Namera so Claude Code (or any AI agent) can check name availability directly:

```bash
namera find --json --context '{"name_candidates": ["neopay", "zestmoney"], "niche": "fintech", "target_audience": "millennials", "location": "US"}'
```

Returns structured JSON with:
- Domain availability across relevant TLDs (auto-selected by niche)
- WHOIS data
- Trademark status
- Relevance scoring (ranks results by availability + TLD preference)

The key insight: AI agents are terrible at parsing raw WHOIS text. Namera gives them
clean JSON with normalized fields. The BusinessContext input lets the agent express
the full naming brief in one call instead of running 15 separate whois commands.

Works with Claude Code, Codex, OpenClaw, or any agent that can invoke CLI tools.

`pip install namera` -- MIT licensed, no API keys needed for basic checks, DNS-direct
lookups (no third-party services seeing your name searches).

GitHub: [link]
```

---

## Devil's Advocate: Expected Criticisms & Responses

### 1. "Why not just use whois / dig / nslookup?"

**The attack:** "This is a wrapper around whois with extra steps."

**Response strategy:** Don't be defensive. Acknowledge it, then pivot:

> "You're right that `whois example.com` works fine for a single check. Namera exists
> because (a) it aggregates domain + WHOIS + trademark in one call across multiple names
> and TLDs, (b) it returns structured JSON instead of raw text, and (c) it does
> niche-aware TLD selection and relevance scoring. If you're checking one .com, whois
> is faster. If you're evaluating 5 name candidates across 8 TLDs with trademark checks,
> Namera saves you 40 manual lookups."

### 2. "Nobody uses CLI for this / just make a web app"

**The attack:** "Developers already know how to check domains. Non-developers won't touch a CLI."

**Response strategy:**

> "The primary user isn't a human in a terminal -- it's an AI agent. Claude Code, Codex,
> and similar tools need CLI interfaces with structured JSON output. The interactive wizard
> is a bonus, not the main interface. Think of it less as 'a CLI tool' and more as
> 'an API endpoint that happens to live in your terminal.'"

### 3. "AI agent tooling is a solution looking for a problem"

**The attack:** "Agents can already run whois. Why do they need a special tool?"

**Response strategy:**

> "Agents *can* run raw whois, but they get unstructured text that varies by TLD, requires
> ad-hoc parsing, and errors silently. Namera returns normalized JSON with consistent
> fields regardless of provider. It's the difference between giving an agent `curl` vs
> giving it a typed SDK. Plus the BusinessContext input lets the agent express the full
> naming brief ('fintech, US, millennials, budget $50') in one call instead of orchestrating
> 15 separate shell commands."

### 4. "Domain squatters will front-run your searches"

**The attack:** "Any domain checker leaks your queries to squatters."

**Response strategy (this is actually a strength):**

> "Good concern. Namera does DNS lookups directly against authoritative nameservers -- no
> third-party API, no registrar search, no middlemen. Your queries stay between your
> machine and DNS. This is actually safer than using a registrar's search bar."

### 5. "The trademark check is a stub"

**The attack:** "Your trademark provider is fake. This is vaporware."

**This is a real vulnerability.** Mitigations:
- **Option A (best):** Integrate USPTO TSDR API (free) before posting. Even a basic implementation beats a stub.
- **Option B:** Remove the trademark command entirely. Better to have 2 working providers than 3 where one is fake.
- **Option C:** Be upfront in the post: "Trademark checking currently returns unknown -- the provider interface is there but needs a real API integration. PRs welcome." Honesty disarms the criticism.

### 6. "There are 500 of these already"

**The attack:** Namechk, Namecheckr, Instant Domain Search, Domainr, etc.

**Response strategy:**

> "Those are web apps for humans. Namera is a CLI tool for AI agents. Different interface,
> different user, different use case. If you want to manually check a name in a browser,
> use those. If you want Claude Code to evaluate 5 name candidates as part of a larger
> project scaffolding workflow, use this."

### 7. "Did you build this with AI?"

**The attack:** Code style / commit patterns suggest AI generation.

**Response strategy:** Don't deny it, don't dwell on it.

> "I used AI tools during development, yeah. The architecture decisions and provider
> design are mine. The code is MIT licensed and fully readable -- judge it on its merits."

---

## Self-Promotion Rules Checklist

- [ ] Reddit account has 50+ karma and 4+ weeks of history before posting
- [ ] Using personal account, not a brand account
- [ ] 80%+ of recent Reddit activity is genuine community participation (not self-promo)
- [ ] "Full disclosure: I built this" appears in the post
- [ ] NOT cross-posting identical content to multiple subreddits
- [ ] Each subreddit gets a customized angle
- [ ] Posts spaced 3-4 weeks apart across subreddits
- [ ] Will reply to every comment within 2 hours of posting
- [ ] No unsolicited DMs to commenters
- [ ] Will acknowledge valid criticism, not argue

---

## Pre-Launch Checklist

- [ ] Trademark provider: integrate real API or remove stub
- [ ] GitHub repo has a clear README with install command and usage examples
- [ ] Add an asciinema GIF or screenshot to README (visual proof it works)
- [ ] `pip install namera` works cleanly
- [ ] At least 1-2 GitHub stars (ask friends) -- zero stars = instant dismissal
- [ ] Tests pass: `pytest` green
- [ ] Linting clean: `ruff check src/ tests/`
- [ ] Write a "first comment" to post immediately after submitting (boosts algorithm)

---

## 90-Day Rollout Calendar

| Week | Action |
|---|---|
| **Week 0** | Fix trademark stub. Polish README. Record demo GIF. |
| **Week 1** | Post to **r/SideProject** (Tue/Wed 8 AM ET). Engage all comments. |
| **Week 1-2** | Post to **r/Python** (different day, Python angle). |
| **Week 2** | Post to **r/ClaudeAI** and **r/ChatGPTCoding** (agent angle). |
| **Week 3** | Post to **r/commandline** and **r/opensource**. |
| **Week 4** | Post to **r/coolgithubprojects** and **r/alphaandbetausers**. |
| **Week 5-8** | Comment helpfully in naming/domain threads across r/startups, r/Entrepreneur. Mention Namera only when directly relevant. |
| **Week 8-12** | Post to **r/webdev** (only if you've built comment history there). Consider **Hacker News** "Show HN" post. |

---

## Key Metrics to Track

- **Comment-to-upvote ratio** -- high ratio = genuine discussion (good)
- **GitHub stars** gained per post
- **pip install** count (if published to PyPI)
- **GitHub issues/PRs** from Reddit users
- **Saves/bookmarks** on the Reddit post (high-intent signal)

---

*Note: Reddit threads also appear in ~40% of AI-generated responses for product recommendations, giving posts long-tail discoverability far beyond the initial launch window.*

---

## Show HN Post Draft

HN often drives more developer-tool traffic than Reddit. Post after initial Reddit traction (week 8-12) so you have GitHub stars and user feedback to reference.

### Title

`Show HN: Namera -- CLI for checking name availability, designed for AI agents`

### Body

```
Namera is an open-source CLI that checks domain availability, WHOIS records,
and trademark status across multiple name candidates at once.

The primary use case is AI agent tool-use: an LLM coding assistant calls
`namera find --json --context '{"name_candidates":["neopay"],"niche":"fintech"}'`
and gets structured JSON back -- no WHOIS text parsing required.

Key decisions:
- DNS-direct lookups (no third-party API middlemen)
- Niche-aware TLD selection (fintech -> .finance, .money, .io; gaming -> .gg, .dev)
- Pluggable provider architecture (__init_subclass__ auto-registration)
- Three input modes: --context flag, stdin pipe, interactive wizard

Python, Click, Rich, httpx, asyncio. MIT licensed.

GitHub: [link]
```

> HN rules: no "I built" framing. Describe the thing, not yourself. Keep it under 80 words.

---

## Competitor Positioning Table

Use this to quickly articulate differences when someone says "this already exists."

| Tool | Interface | Audience | Aggregation | Structured Output | Business Context | Privacy |
|---|---|---|---|---|---|---|
| **Namechk** | Web | Humans | Social + domains | No (HTML) | No | Queries go through their servers |
| **Instant Domain Search** | Web | Humans | Domains only | No | No | Queries go through their servers |
| **Domainr** | Web + API | Humans/devs | Domains only | JSON (paid API) | No | API key required |
| **whois CLI** | CLI | Devs | Single domain | Raw text | No | Direct lookup |
| **Namera** | CLI | AI agents + devs | Domain + WHOIS + trademark | JSON (free) | Yes (BusinessContext) | DNS-direct, no middlemen |

The differentiator isn't any single feature -- it's the combination: CLI + JSON + multi-provider + business context + no API key.

---

## Demo Script (for asciinema/GIF recording)

Record this as a ~20 second terminal GIF for the README and Reddit posts. Visual proof dramatically increases engagement.

```bash
# 1. Quick single-name check (3 seconds)
namera search coolname

# 2. Pause to show the Rich table output (2 seconds)

# 3. Agent-style JSON check with business context (5 seconds)
namera find --json --context '{"name_candidates": ["neopay", "zestfi"], "niche": "fintech", "preferred_tlds": ["com", "io"]}'

# 4. Pause to show structured JSON output (3 seconds)

# 5. Interactive wizard (optional, adds 10 seconds)
# namera find
```

Recording command: `asciinema rec demo.cast -t "Namera Demo" --idle-time-limit 2`

Convert to GIF: `agg demo.cast demo.gif --theme monokai`

> Keep the terminal width at 100 cols, font size readable. No typos -- script it with
> `asciinema rec --command "bash demo-script.sh"` for a clean take.

---

## PyPI Readiness Check

**Every post says `pip install namera`.** If this 404s, credibility is destroyed instantly.

- [ ] Package is published to PyPI (`pip install namera` works from a clean venv)
- [ ] `namera --version` shows a real version number
- [ ] `namera --help` shows clean output
- [ ] Entry point is configured in `pyproject.toml` so the `namera` command exists after install
- [ ] Test the full install flow: `python3 -m venv /tmp/test-env && source /tmp/test-env/bin/activate && pip install namera && namera search testname`

If not ready for PyPI yet, change all posts to use `pip install git+https://github.com/...` instead.

---

## Missing Subreddit: r/SaaS

| Subreddit | ~Members | Angle |
|---|---|---|
| **r/SaaS** | 100K+ | "Free tool for validating SaaS name availability before you commit" -- outcomes-focused, not tech |

Good fit because SaaS founders are the exact people who need to check name availability repeatedly. Post in week 3-4 alongside the Tier 2 rollout.

---

## Complementary Channels (Beyond Reddit)

Reddit is one channel. For a holistic launch:

| Channel | When | Format |
|---|---|---|
| **Hacker News** (Show HN) | Week 8-12 | Terse description, link to repo |
| **Dev.to** | Week 2 | "Building a CLI for AI agents" tutorial-style article |
| **Twitter/X** | Same day as Reddit posts | Short thread: problem > solution > demo GIF > link |
| **Product Hunt** | After 50+ GitHub stars | Only if you have a web demo or very polished CLI |
| **r/SaaS, r/startups** | Week 4+ | Outcomes-focused, not tech-focused |
| **Relevant Discord servers** | Ongoing | Claude Code Discord, Python Discord, Indie Hackers |
