import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { captureError, initSentry } from "../_shared/sentry.ts";

initSentry("session-log");

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  { db: { schema: "namera" } },
);

// ---------------------------------------------------------------------------
// Rate limiting — in-memory per-isolate (resets on cold starts)
// ---------------------------------------------------------------------------
const RATE_LIMIT_REQUESTS = 60; // max requests per window
const RATE_LIMIT_WINDOW_MS = 60_000; // 1-minute sliding window

const memHits = new Map<string, { count: number; resetAt: number }>();

function getClientIp(req: Request): string {
  return (
    req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    req.headers.get("x-real-ip") ||
    "unknown"
  );
}

function checkRateLimit(ip: string): { allowed: boolean; remaining: number } {
  const now = Date.now();
  const entry = memHits.get(ip);
  if (!entry || now >= entry.resetAt) {
    memHits.set(ip, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return { allowed: true, remaining: RATE_LIMIT_REQUESTS - 1 };
  }
  entry.count++;
  const remaining = Math.max(0, RATE_LIMIT_REQUESTS - entry.count);
  return { allowed: entry.count <= RATE_LIMIT_REQUESTS, remaining };
}

// Periodically prune stale entries (avoid unbounded growth)
setInterval(() => {
  const now = Date.now();
  for (const [ip, entry] of memHits) {
    if (now >= entry.resetAt) memHits.delete(ip);
  }
}, RATE_LIMIT_WINDOW_MS);

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST",
  "Access-Control-Allow-Headers": "Content-Type",
};

interface SessionPayload {
  names?: string[];
  niche?: string;
  profile?: string;
  num_candidates?: number;
  top_name?: string;
  top_score?: number;
}

function jsonResponse(status: number, body: Record<string, unknown>) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...CORS_HEADERS },
  });
}

function normalizeNames(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is string => typeof item === "string")
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 25);
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: CORS_HEADERS });
  }

  if (req.method !== "POST") {
    return jsonResponse(405, { error: "POST required" });
  }

  // --- Rate limit check ---
  const clientIp = getClientIp(req);
  const { allowed, remaining } = checkRateLimit(clientIp);
  const rateLimitHeaders = {
    "X-RateLimit-Limit": String(RATE_LIMIT_REQUESTS),
    "X-RateLimit-Remaining": String(remaining),
  };

  if (!allowed) {
    return new Response(
      JSON.stringify({ error: "Rate limit exceeded. Try again in 60 seconds." }),
      {
        status: 429,
        headers: {
          "Content-Type": "application/json",
          "Retry-After": "60",
          ...rateLimitHeaders,
          ...CORS_HEADERS,
        },
      },
    );
  }

  try {
    const body: SessionPayload = await req.json();
    const names = normalizeNames(body.names);
    const profile = typeof body.profile === "string" && body.profile.trim()
      ? body.profile.trim()
      : "default";
    const niche = typeof body.niche === "string" && body.niche.trim()
      ? body.niche.trim()
      : null;
    const topName = typeof body.top_name === "string" && body.top_name.trim()
      ? body.top_name.trim()
      : names[0] ?? null;
    const numCandidates = typeof body.num_candidates === "number" && Number.isFinite(body.num_candidates)
      ? Math.max(0, Math.trunc(body.num_candidates))
      : names.length;
    const topScore = typeof body.top_score === "number" && Number.isFinite(body.top_score)
      ? body.top_score
      : null;

    const { error } = await supabase.from("sessions").insert({
      names,
      niche,
      profile,
      num_candidates: numCandidates,
      top_name: topName,
      top_score: topScore,
    });

    if (error) throw error;

    return new Response(null, {
      status: 201,
      headers: { ...rateLimitHeaders, ...CORS_HEADERS },
    });
  } catch (err) {
    captureError(
      "session-log insert failed",
      err instanceof Error ? err : new Error(String(err)),
    );
    return jsonResponse(500, { error: String(err) });
  }
});
