# TODOS

## Social handle check robustness

**What:** Social provider uses direct HTTP HEAD requests with browser user-agent. Twitter/X and Instagram will block at any meaningful volume. Social batching also bypasses the concurrency semaphore (nested asyncio.gather without rate limiting).

**Why:** IP bans degrade the social availability signal for all users. Currently low urgency because social checks are opt-in (not included in default check types), but becomes critical if social checks become popular via MCP agents.

**Pros:** Fixing prevents IP bans, improves reliability, makes social checks production-grade.

**Cons:** Proper fix requires either a proxy service, official platform APIs (Twitter API, Instagram Graph API), or rate-limited queue. Significant rework.

**Context:** `src/namera/providers/social.py` — `batch_social_check()` uses `asyncio.gather()` without semaphore. Each name × platform = one HTTP request. 10 names × 3 platforms = 30 concurrent requests. 50 names = 150 requests.

**Depends on:** Nothing. Independent of MCP server work.

**Added:** 2026-03-31 (from /plan-eng-review)
