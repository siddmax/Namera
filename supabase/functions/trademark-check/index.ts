import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const supabase = createClient(supabaseUrl, supabaseKey, {
  db: { schema: "namera" },
});

interface CheckRequest {
  // Single query mode (existing)
  query?: string;
  // Batch mode (new)
  queries?: string[];
  mode?: "exact" | "similarity" | "both";
  similarity_threshold?: number;
  nice_classes?: number[];
}

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST",
  "Access-Control-Allow-Headers": "Content-Type",
};

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
          { status: 400, headers: { "Content-Type": "application/json" } }
        );
      }
      if (queries.length > 100) {
        return new Response(
          JSON.stringify({ error: "Max 100 queries per batch" }),
          { status: 400, headers: { "Content-Type": "application/json" } }
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
          }
        );
        if (batchErr) throw batchErr;

        // Build lookup by query (RPC returns: query, is_trademarked, match_count, top_match_serial, top_match_owner)
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

      // Similarity: fan out concurrently (no batch RPC for similarity)
      if (mode === "similarity" || mode === "both") {
        const simPromises = queries.map(async (q) => {
          const { data: similar, error: simErr } = await supabase.rpc(
            "trademark_similarity_search",
            {
              query_text: q,
              similarity_threshold: body.similarity_threshold || 0.3,
              filter_nice_classes: body.nice_classes || null,
              result_limit: 10,
            }
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
        });

        const simResults = await Promise.all(simPromises);
        for (const sr of simResults) {
          results[sr.query].similarity = sr.similarity;
        }
      }

      return new Response(JSON.stringify({ results }), {
        headers: {
          "Content-Type": "application/json",
          ...CORS_HEADERS,
          "Cache-Control": "public, max-age=3600",
        },
      });
    }

    // Single query mode (existing behavior)
    const query = body.query?.trim();
    if (!query) {
      return new Response(
        JSON.stringify({ error: "'query' or 'queries' field required" }),
        { status: 400, headers: { "Content-Type": "application/json" } }
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
        }
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
        }
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
        ...CORS_HEADERS,
        "Cache-Control": "public, max-age=3600",
      },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: String(err) }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
});
