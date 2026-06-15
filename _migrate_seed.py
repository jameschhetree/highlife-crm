#!/usr/bin/env python3
"""
Seed Supabase from prospects.json (the canonical seed).

Per task spec: prospects.json becomes a SEED-only file. This script uploads
all 690 rows into the prospects table. localStorage extraction is attempted
in a separate script (_migrate_localstorage.py) and any deltas are merged
on top.
"""
import json
import psycopg2
import psycopg2.extras

creds = json.load(open('/Users/james/.claude/highlife-crm-credentials.json'))
pgconn = json.load(open('/Users/james/highlife-crm/.pgconn.json'))

conn = psycopg2.connect(
    host=pgconn['host'],
    port=pgconn['port'],
    user=pgconn['user'],
    password=creds['db_password'],
    dbname='postgres',
    sslmode='require',
)
conn.autocommit = False
cur = conn.cursor()

data = json.load(open('/Users/james/highlife-crm/prospects.json'))
print(f"Loaded {len(data)} prospects from prospects.json")

# Map JSON keys to DB columns
def row_for_db(p):
    return {
        'id':                p['id'],
        'name':              p.get('name'),
        'job_title':         p.get('jobTitle'),
        'company':           p.get('company'),
        'source':            p.get('source'),
        'email':             p.get('email'),
        'phone':             p.get('phone'),
        'linkedin':          p.get('linkedin'),
        'instagram':         p.get('instagram'),
        'youtube':           p.get('youtube'),
        'twitter':           p.get('twitter'),
        'website':           p.get('website'),
        'package':           p.get('package'),
        'status':            p.get('status') or 'prospect',
        'last_contact':      p.get('lastContact'),
        'notes':             p.get('notes'),
        'rating':            p.get('rating'),
        'feedback':          p.get('feedback'),
        'rated_at':          p.get('ratedAt'),
        'graveyard_reason':  p.get('graveyard_reason'),
        'pushed_to_clay':    bool(p.get('pushedToClay', False)),
        'linkedin_status':   p.get('linkedin_status'),
        'instagram_status':  p.get('instagram_status'),
        'youtube_status':    p.get('youtube_status'),
        'location':          p.get('location'),
        'seller':            p.get('seller'),
        'assigned_seller':   p.get('assigned_seller') or p.get('seller'),
        'is_in_crm':         p.get('status') == 'added_to_crm' or bool(p.get('is_in_crm', False)),
        'created_at':        p.get('createdAt'),
        'updated_at':        p.get('updatedAt') or p.get('createdAt'),
    }

cols = list(row_for_db(data[0]).keys())
placeholders = ','.join(['%s'] * len(cols))
update_assignments = ','.join(f'{c}=EXCLUDED.{c}' for c in cols if c != 'id')

upsert = f"""
INSERT INTO prospects ({','.join(cols)})
VALUES ({placeholders})
ON CONFLICT (id) DO UPDATE SET {update_assignments};
"""

rows = [tuple(row_for_db(p).get(c) for c in cols) for p in data]

psycopg2.extras.execute_batch(cur, upsert, rows, page_size=100)
conn.commit()

cur.execute("SELECT count(*) FROM prospects")
print(f"prospects in DB after seed: {cur.fetchone()[0]}")

cur.close()
conn.close()
