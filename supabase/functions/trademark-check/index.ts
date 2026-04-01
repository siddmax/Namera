import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

// ---------------------------------------------------------------------------
// Supabase client
// ---------------------------------------------------------------------------
const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const supabase = createClient(supabaseUrl, supabaseKey, {
  db: { schema: "namera" },
});

// ---------------------------------------------------------------------------
// Rate limiting — in-memory per-isolate (resets on cold starts)
// ---------------------------------------------------------------------------
const RATE_LIMIT_REQUESTS = 30; // max requests per window
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

// ---------------------------------------------------------------------------
// Similarity fan-out concurrency — cap concurrent DB queries
// ---------------------------------------------------------------------------
const SIM_CONCURRENCY = 10;

async function runSimilarityBatch(
  queries: string[],
  threshold: number,
  niceClasses: number[] | null,
): Promise<{ query: string; similarity: Record<string, unknown> }[]> {
  const results: { query: string; similarity: Record<string, unknown> }[] = [];
  for (let i = 0; i < queries.length; i += SIM_CONCURRENCY) {
    const chunk = queries.slice(i, i + SIM_CONCURRENCY);
    const chunkResults = await Promise.all(
      chunk.map(async (q) => {
        const { data: similar, error: simErr } = await supabase.rpc(
          "trademark_similarity_search",
          {
            query_text: q,
            similarity_threshold: threshold,
            filter_nice_classes: niceClasses,
            result_limit: 10,
          },
        );
        if (simErr) throw simErr;
        const maxScore = similar?.length
          ? Math.max(...similar.map((s: any) => s.similarity_score))
          : 0;
        return {
          query: q,
          similarity: {
            matches: similar || [],
            count: similar?.length || 0,
            max_score: Math.round(maxScore * 1000) / 1000,
          },
        };
      }),
    );
    results.push(...chunkResults);
  }
  return results;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface CheckRequest {
  query?: string;
  queries?: string[];
  mode?: "exact" | "similarity" | "both";
  similarity_threshold?: number;
  nice_classes?: number[];
}

const MAX_BATCH_SIZE = 50;

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST",
  "Access-Control-Allow-Headers": "Content-Type",
};

// ---------------------------------------------------------------------------
// Handler
// ---------------------------------------------------------------------------
Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: CORS_HEADERS });
  }

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "POST required" }), {
      status: 405,
      headers: { "Content-Type": "application/json" },
    });
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
    const body: CheckRequest = await req.json();

    // Batch mode: queries array
    if (body.queries && Array.isArray(body.queries)) {
      const queries = body.queries
        .map((q) => (typeof q === "string" ? q.trim() : ""))
        .filter(Boolean);
      if (queries.length === 0) {
        return new Response(
          JSON.stringify({ error: "'queries' must be a non-empty array of strings" }),
          { status: 400, headers: { "Content-Type": "application/json" } },
        );
      }
      if (queries.length > MAX_BATCH_SIZE) {
        return new Response(
          JSON.stringify({ error: `Max ${MAX_BATCH_SIZE} queries per batch` }),
          { status: 400, headers: { "Content-Type": "application/json" } },
        );
      }

      const mode = body.mode || "both";
      const results: Record<string, Record<string, unknown>> = {};

      // Initialize results
      for (const q of queries) {
        results[q] = {};
      }

      // Batch exact check via trademark_batch_check RPC
      if (mode === "exact" || mode === "both") {
        const { data: batchData, error: batchErr } = await supabase.rpc(
          "trademark_batch_check",
          {
            query_names: queries,
            filter_nice_classes: body.nice_classes || null,
          },
        );
        if (batchErr) throw batchErr;

        // Build lookup by query
        const byQuery: Record<string, any> = {};
        for (const row of batchData || []) {
          byQuery[(row.query || "").toUpperCase()] = row;
        }

        for (const q of queries) {
          const row = byQuery[q.toUpperCase()];
          if (row) {
            const matches = row.is_trademarked
              ? [{ serial_number: row.top_match_serial, owner_name: row.top_match_owner }]
              : [];
            results[q].exact = {
              matches,
              count: Number(row.match_count) || 0,
              trademarked: row.is_trademarked,
            };
          } else {
            results[q].exact = { matches: [], count: 0, trademarked: false };
          }
        }
      }

      // Similarity: chunked fan-out (max SIM_CONCURRENCY concurrent DB queries)
      if (mode === "similarity" || mode === "both") {
        const simResults = await runSimilarityBatch(
          queries,
          body.similarity_threshold || 0.3,
          body.nice_classes || null,
        );
        for (const sr of simResults) {
          results[sr.query].similarity = sr.similarity;
        }
      }

      return new Response(JSON.stringify({ results }), {
        headers: {
          "Content-Type": "application/json",
          ...rateLimitHeaders,
          ...CORS_HEADERS,
          "Cache-Control": "public, max-age=3600",
        },
      });
    }

    // Single query mode
    const query = body.query?.trim();
    if (!query) {
      return new Response(
        JSON.stringify({ error: "'query' or 'queries' field required" }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      );
    }

    const mode = body.mode || "both";
    const result: Record<string, unknown> = { query };

    // Exact match
    if (mode === "exact" || mode === "both") {
      const { data: exactMatches, error: exactErr } = await supabase.rpc(
        "trademark_check",
        {
          query_text: query,
          filter_nice_classes: body.nice_classes || null,
          result_limit: 20,
        },
      );
      if (exactErr) throw exactErr;
      result.exact = {
        matches: exactMatches || [],
        count: exactMatches?.length || 0,
        trademarked: (exactMatches?.length || 0) > 0,
      };
    }

    // Similarity search
    if (mode === "similarity" || mode === "both") {
      const { data: similar, error: simErr } = await supabase.rpc(
        "trademark_similarity_search",
        {
          query_text: query,
          similarity_threshold: body.similarity_threshold || 0.3,
          filter_nice_classes: body.nice_classes || null,
          result_limit: 10,
        },
      );
      if (simErr) throw simErr;
      const maxScore = similar?.length
        ? Math.max(...similar.map((s: any) => s.similarity_score))
        : 0;
      result.similarity = {
        matches: similar || [],
        count: similar?.length || 0,
        max_score: Math.round(maxScore * 1000) / 1000,
      };
    }

    return new Response(JSON.stringify(result), {
      headers: {
        "Content-Type": "application/json",
        ...rateLimitHeaders,
        ...CORS_HEADERS,
        "Cache-Control": "public, max-age=3600",
      },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: String(err) }),
      { status: 500, headers: { "Content-Type": "application/json", ...CORS_HEADERS } },
    );
  }
});
