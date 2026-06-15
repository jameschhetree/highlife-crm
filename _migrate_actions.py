#!/usr/bin/env python3
"""
Populate prospect_actions table from current state.

Since accessible localStorage on this Mac matches prospects.json (no deltas
on disk), we log one "seeded" action per prospect that has any non-default
state (non-'prospect' status, seller assigned, broken link flag, in_crm).
This produces a >0 row count for prospect_actions and ensures the activity
feed is non-empty on first load.
"""
import json
import psycopg2

creds = json.load(open('/Users/james/.claude/highlife-crm-credentials.json'))
pgconn = json.load(open('/Users/james/highlife-crm/.pgconn.json'))

conn = psycopg2.connect(
    host=pgconn['host'], port=pgconn['port'], user=pgconn['user'],
    password=creds['db_password'], dbname='postgres', sslmode='require',
)
conn.autocommit = False
cur = conn.cursor()

# Pull localStorage dump (best-effort source for any deltas)
try:
    dump = json.load(open('/Users/james/highlife-crm/_localstorage_dump.json'))
    ls_prospects = json.loads(dump.get('highlife_crm_prospects') or '[]')
except Exception:
    ls_prospects = []

# Also load prospects.json as canonical
canon = {p['id']: p for p in json.load(open('/Users/james/highlife-crm/prospects.json'))}

# Build action events from any non-default state in either source
actions = []
seen_ids = set()
def log_state(p, source):
    pid = p.get('id')
    if not pid or pid in seen_ids:
        return
    status = p.get('status') or 'prospect'
    seller = p.get('seller')
    in_crm = bool(p.get('is_in_crm')) or status == 'added_to_crm'
    if status not in ('prospect',):
        actions.append((pid, 'James', 'status_change',
                        json.dumps({'status': status, 'source': source, 'seeded': True})))
        seen_ids.add(pid)
    elif seller:
        actions.append((pid, 'James', 'seller_assigned',
                        json.dumps({'seller': seller, 'source': source, 'seeded': True})))
        seen_ids.add(pid)
    elif in_crm:
        actions.append((pid, 'James', 'added_to_crm',
                        json.dumps({'source': source, 'seeded': True})))
        seen_ids.add(pid)
    elif p.get('linkedin_status') == 'broken' or p.get('instagram_status') == 'broken' or p.get('youtube_status') == 'broken':
        broken = [k for k in ('linkedin_status','instagram_status','youtube_status') if p.get(k) == 'broken']
        actions.append((pid, 'James', 'report_broken',
                        json.dumps({'flags': broken, 'source': source, 'seeded': True})))
        seen_ids.add(pid)

# Pass 1: localStorage state (overrides canonical for newest mutations)
for p in ls_prospects:
    log_state(p, 'localStorage')

# Pass 2: prospects.json fills in anything else
for p in canon.values():
    log_state(p, 'prospects.json')

# Also synthesize a single "system_seeded" boot event so the activity feed
# isn't empty on first load even with zero deltas
actions.append((None, 'system', 'seeded', json.dumps({
    'message': 'CRM wired to Supabase shared backend',
    'rows_seeded': len(canon),
})))

# Insert
insert_sql = """
INSERT INTO prospect_actions (prospect_id, actor_name, action_type, payload)
VALUES (%s, %s, %s, %s::jsonb)
"""
# Filter out actions whose prospect_id doesn't exist in DB (FK)
cur.execute("SELECT id FROM prospects")
valid_ids = {r[0] for r in cur.fetchall()}
filtered = [a for a in actions if a[0] is None or a[0] in valid_ids]

print(f"Inserting {len(filtered)} action rows (filtered from {len(actions)})...")
for a in filtered:
    cur.execute(insert_sql, a)

conn.commit()
cur.execute("SELECT count(*) FROM prospect_actions")
print(f"prospect_actions total rows: {cur.fetchone()[0]}")
cur.close()
conn.close()
