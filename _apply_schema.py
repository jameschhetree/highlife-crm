#!/usr/bin/env python3
"""Apply schema to Supabase via direct PG connection."""
import json
import os
import sys
import psycopg2
from urllib.parse import quote_plus

creds = json.load(open('/Users/james/.claude/highlife-crm-credentials.json'))
project_id = creds['project_id']
db_password = creds['db_password']

# Supabase direct connection (port 5432) - pooler is 6543, direct is 5432
# Supabase uses db.<project>.supabase.co for direct, aws-0-<region>.pooler.supabase.com for pooler
# Try the pooler first (better for one-off connections)
hosts_to_try = [
    f"aws-0-us-east-1.pooler.supabase.com",  # pooler us-east-1
    f"aws-0-us-east-2.pooler.supabase.com",  # pooler us-east-2
    f"aws-0-us-west-1.pooler.supabase.com",  # pooler us-west-1
    f"db.{project_id}.supabase.co",          # direct
]

schema = open('/Users/james/highlife-crm/_supabase_schema.sql').read()

last_err = None
for host in hosts_to_try:
    for port, user in [(6543, f"postgres.{project_id}"), (5432, "postgres")]:
        try:
            print(f"Trying {host}:{port} as {user}...")
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=db_password,
                dbname='postgres',
                connect_timeout=10,
                sslmode='require',
            )
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(schema)
            print(f"Schema applied via {host}:{port}")
            # Quick verify
            cur.execute("SELECT count(*) FROM prospects")
            print(f"prospects rows: {cur.fetchone()[0]}")
            cur.execute("SELECT count(*) FROM prospect_actions")
            print(f"prospect_actions rows: {cur.fetchone()[0]}")
            cur.close()
            conn.close()
            # Persist the working connection params for migration script
            with open('/Users/james/highlife-crm/.pgconn.json', 'w') as f:
                json.dump({'host': host, 'port': port, 'user': user}, f)
            os.chmod('/Users/james/highlife-crm/.pgconn.json', 0o600)
            sys.exit(0)
        except Exception as e:
            last_err = e
            err_str = str(e)[:200]
            print(f"  -> failed: {err_str}")
            continue

print(f"\nALL CONNECTIONS FAILED. Last error: {last_err}")
sys.exit(1)
