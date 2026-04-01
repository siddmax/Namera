import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  { db: { schema: "namera" } },
);

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
  num_viable?: number;
  top_name?: string;
  top_score?: number;
  input_flags?: Record<string, unknown>;
  outcome?: Record<string, unknown>;
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

    const numViable = typeof body.num_viable === "number" && Number.isFinite(body.num_viable)
      ? Math.max(0, Math.trunc(body.num_viable))
      : null;

    const { error } = await supabase.from("sessions").insert({
      names,
      niche,
      profile,
      num_candidates: numCandidates,
      num_viable: numViable,
      top_name: topName,
      top_score: topScore,
      input_flags: body.input_flags || null,
      outcome: body.outcome || null,
    });

    if (error) throw error;

    return new Response(null, {
      status: 201,
      headers: CORS_HEADERS,
    });
  } catch (err) {
    return jsonResponse(500, { error: String(err) });
  }
});
