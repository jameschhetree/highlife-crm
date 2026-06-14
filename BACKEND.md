# Bright Entertainment CRM — Backend

## Architecture

Static HTML frontend + Vercel serverless API routes + Upstash Redis (KV) for shared lead storage.

Leads sync across all team members via a single Redis key (`bright_ent_leads_v1`). The full leads array is written on every change (dataset is small — ~50 records max). Each browser also keeps localStorage as an instant-read cache and offline fallback.

## API Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/leads` | GET | Returns all leads from KV |
| `/api/leads` | POST | Saves full leads array to KV |
| `/api/login` | POST | Authenticates user, sets auth cookie |

All API routes (except `/api/login`) are auth-gated by `middleware.js`.

## Environment Variables (Vercel)

Set these in the Vercel project dashboard under Settings > Environment Variables:

| Variable | Description |
|----------|-------------|
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST endpoint URL |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis REST auth token |

Same Upstash database used by highlife-calculator. Keys are namespaced (`bright_ent_leads_v1`) so there is no collision.

If these env vars are not set, the CRM falls back to localStorage-only mode (each browser has its own data, no cross-team sync). The UI shows a yellow "Local only" indicator in that case.

## Sync Behavior

1. On page load: GET `/api/leads` — if KV has data, use it (overwrite localStorage). If KV is empty but available, seed it from `leads.json`.
2. On every save: localStorage updates immediately, then async POST to `/api/leads`.
3. Polling: every 60 seconds, refetch from KV so team members see each other's changes.
4. If KV write fails, a toast notifies the user. Their change is still in localStorage.

## Redis Key

`bright_ent_leads_v1` — JSON array of lead objects.
