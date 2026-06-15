# HighLife Clay Enrichment — Resume Instructions

**Purpose:** This file tells the next Claude Code session (post-restart) how to pick up the HighLife prospect enrichment job using the newly-installed Clay MCP.

**Written:** 2026-05-11 by Jeremy session pre-restart
**Initiating chat:** "HL Prospect LI" (chat_id -5186707521)
**Reply to James in that chat when each milestone completes.**

---

## Current state

- **Clay MCP installed** in `~/.claude.json` under `mcpServers.clay`. Uses `npx @clayhq/clay-mcp@latest` with `CLAY_API_KEY` env var. Will auto-load on next session start.
- **Master prospect list:** `/Users/james/highlife-crm/prospects.json` — 200 records, all `status=prospect`, all missing email + phone.
- **Refined list (post too-big filter):** `/Users/james/highlife-crm/prospects-refined.json` — 133 records. National pundits (Saagar, Mercedes, Fox/CNN regulars, 50K+ follower accounts) dropped.
- **Dropped list (audit trail):** `/Users/james/highlife-crm/prospects-flagged-too-big.json` — 67 records with `_flagged_reason` field showing why each was cut.
- **Test input CSV:** `/Users/james/highlife-crm/clay-test-input-10.csv` — top 10 from refined list, all "CEO Brand Suite" tier:
  1. Theodora Lau (Unconventional Ventures)
  2. Thomas Sanchez (Social Driver)
  3. Sterling McKinley (McKinley Media / Google)
  4. Daryl Judy (Washington Fine Properties)
  5. Mia Horm (Creative Analytics / BRAND-E)
  6. Angel Livas (ALIVE Podcast Network)
  7. Mahan Tavakoli (Strategic Leadership Ventures)
  8. Kathy Hollinger (Greater Washington Partnership)
  9. Seema Alexander (Virgent AI)
  10. Casey Samson (The Casey Samson Team)

## On restart — verify Clay MCP loaded

```bash
# Check tools surfaced under deferred MCP list. Should see clay_* tools after restart.
# If using ToolSearch: query "clay"
```

If `clay_*` tools are not present after restart, troubleshoot:
- Inspect `~/.claude/logs/` for MCP startup errors
- `npx @clayhq/clay-mcp@latest` manually to see if the package works at all
- Check `CLAY_API_KEY` env reached the subprocess (`echo $CLAY_API_KEY` from a Bash tool call after start)

## Job sequence (next session)

**SCOPE UPDATE 2026-05-11 14:53 EDT:** James greenlit full bulk on the 133 refined. **Skip the test batch — go straight to all 133.** Estimated worst-case ~$100/150 burn; he's authorized.

1. **Verify Clay MCP loaded.** `clay_*` tools should appear via ToolSearch / deferred list. If not, troubleshoot before any spend.
2. **Run enrichment on all 133 refined records** at `/Users/james/highlife-crm/prospects-refined.json`. Target fields: work email, mobile/work phone. Process in batches of 25 to handle rate-limits gracefully.
3. **Write merged output** to `/Users/james/highlife-crm/prospects-enriched.json` — full record set with `email`, `phone`, `enrichment_source`, `confidence` merged in. Match by `id`.
4. **Merge back into prospects.json** — the CRM at `/Users/james/highlife-crm/index.html` reads `fetch('prospects.json')` directly. Update prospects.json so each refined record now has `email` + `phone` populated. PRESERVE the original 67 flagged-too-big records (they're still in prospects.json — just leave their email/phone empty unless the user later asks to enrich them too).
5. **Redeploy CRM to Vercel** so the deployed view reflects the new data:
   ```bash
   cd /Users/james/highlife-crm && vercel --prod
   ```
   Vercel CLI is at /opt/homebrew/bin/vercel, project already linked (.vercel/project.json exists).
6. **Report to James** via Telegram outbox (chat_id `-5186707521`):
   - Hit rate: emails found / 133, phones found / 133
   - Total Clay cost actual
   - Any prospects that came up totally empty (flag for manual research)
   - Deployed Vercel URL (he refreshes there to see results)

## Telegram outbox reminder

To send a message:
```sql
INSERT INTO outbox (chat_id, response_text) VALUES ('-5186707521', '<message>');
```
Database: `/Users/james/.claude/telegram-bot-v3/jeremy.db`

## Open threads at restart time (heads-up)

When the next session starts up, the bootstrap hook will arm the Telegram inbox monitor. These threads are pending and may have new replies waiting:

| Chat | What's pending |
|---|---|
| James DM (5343757735) | Three adoption blockers awaiting answer: (1) which "telegram MCP" alwaysLoad applies to, (2) repo paths for code review (sourceboard/kalshi/framer-MCP none are git repos), (3) what to upgrade/restart — answered the third partially. |
| Design (-4990293766) | v2 Kyron videos delivered at 14:01. Awaiting feedback or "send to Kyron" greenlight. Also Design inboxes 2737 ("okay yea tweak it a bit") and 2788 ("you said you fixed it before but didn't") still unprocessed — need context before responding. |
| Kyron (-5110825619) | v1 videos delivered earlier; holding v2 push until James says go. |
| Kalshi (-5022653279) | W/L delivered at 12:27 — all-time +$930.77, last 7d -$62.55. No followup yet. |

## Key files written this session

- `/Users/james/highlife-crm/prospects-refined.json` (133)
- `/Users/james/highlife-crm/prospects-flagged-too-big.json` (67)
- `/Users/james/highlife-crm/clay-test-input-10.csv`
- `/Users/james/highlife-crm/RESUME-AFTER-RESTART.md` (this file)
- `/Users/james/kyron-remotion/` (entire Remotion project + 2 rendered MP4s in `out/`)
- `~/.claude/settings.json` (added `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`)
- `~/.claude.json` (added `mcpServers.clay` + `mcpServers.qdrant.alwaysLoad=true`)

## Security note

Inbox row 2824 has been redacted — the Clay API key that came over Telegram is now stored only in `~/.claude.json` mcpServers.clay.env. James was advised to rotate the key post-batch since Telegram-side history may retain it.
