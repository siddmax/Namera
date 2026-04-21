// Sentry SDK for Namera Edge Functions (Deno runtime)
// Namera shares the Yurivan Supabase project + Sentry DSN, so all events
// must carry `project: namera` to be filtered apart from Yurivan events.

import * as Sentry from "npm:@sentry/deno";

let initialized = false;

/**
 * Initialize Sentry for an Edge Function.
 * Call once at module level, before serve().
 * No-ops if SENTRY_DSN is not set or already initialized.
 */
export function initSentry(functionName: string) {
  if (initialized) return;

  const dsn = Deno.env.get("SENTRY_DSN");
  if (!dsn) return;

  Sentry.init({
    dsn,
    defaultIntegrations: false,
    tracesSampleRate: 0.1,
    environment: Deno.env.get("ENVIRONMENT") || "production",
  });

  Sentry.setTag("project", "namera");
  Sentry.setTag("runtime", "deno");
  Sentry.setTag("function", functionName);
  Sentry.setTag("region", Deno.env.get("SB_REGION") || "unknown");
  Sentry.setTag("execution_id", Deno.env.get("SB_EXECUTION_ID") || "unknown");
  initialized = true;
}

/**
 * Capture an error-level event.
 * If data is an Error, captures as exception; otherwise as message.
 */
export function captureError(message: string, data?: unknown) {
  if (data instanceof Error) {
    Sentry.withScope((scope) => {
      scope.setExtra("context", message);
      Sentry.captureException(data);
    });
  } else {
    Sentry.captureMessage(message, {
      level: "error",
      extra: data !== undefined ? { data } : undefined,
    });
  }
}

export { Sentry };
