# HighLife CRM

Live: https://highlife-crm.vercel.app

## Architecture (since 2026-05-20)

The CRM is wired to **Supabase** as a shared backend so the sales team (James,
Jaco, Liam, Hayden) sees the same prospects, statuses, and seller assignments
from any device.

- **DB:** Supabase Postgres at `https://bccwauzfxxolgpdefdqy.supabase.co`
- **Tables:** `prospects` (single source of truth) and `prospect_actions`
  (audit / activity feed)
- **Auth:** None — site is publicly open per James 2026-05-20. RLS policies
  are permissive (publishable key has full CRUD).

## prospects.json is SEED-ONLY

After the 2026-05-20 wire-up, `prospects.json` is **not** the live source.
The Supabase `prospects` table is. The file is preserved because other
scripts still read it:

- `ig_revalidate_cron.py`
- `validate_links.py`
- `graveyard_check_cron.py`

If those crons start writing to Supabase too, `prospects.json` can be
deprecated entirely.

## Files

| File | Purpose |
|------|---------|
| `index.html` | Single-page CRM UI. Loads Supabase via CDN. |
| `supabase-config.js` | Public URL + publishable key (safe to expose). |
| `supabase-client.js` | HLDB API layer: cached reads, debounced writes, 30s peer poll, action logging. |
| `prospects.json` | Seed file (read by crons). Not live data. |
| `vercel.json` | Static rewrites, no middleware. |
| `_apply_schema.py` | One-shot schema migration (already run). |
| `_migrate_seed.py` | Seeds `prospects.json` → `prospects` table. |
| `_migrate_actions.py` | Backfills `prospect_actions` from current state. |
| `_supabase_schema.sql` | The schema, for reference / re-apply. |

The `_*` migration files are excluded from Vercel via `.vercelignore`.

## Security note

The original publishable + secret keys were leaked to chat during wire-up
on 2026-05-20. After the team has confirmed the site works end-to-end,
**rotate both** in the Supabase dashboard:

1. Project settings → API → Reset publishable key, reset service role key.
2. Update `/Users/james/.claude/highlife-crm-credentials.json`.
3. Run: `python3 -c "import json; ..."` to push new values to `supabase-config.js`.
4. `vercel env rm` + `vercel env add` for `NEXT_PUBLIC_SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY`.
5. Redeploy: `vercel --prod --yes`.

Also rotate the DB password.
