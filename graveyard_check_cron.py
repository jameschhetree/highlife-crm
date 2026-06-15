#!/usr/bin/env python3
"""
HighLife CRM - weekly graveyard re-validation cron.

The "graveyard" is prospects with status == "graveyard" (dead / dismissed).
NOTE: the brief described it as a top-level `graveyard` array, but ground
truth in prospects.json is a flat list where dead prospects carry
status:"graveyard" (3 at build time). We re-validate those prospects' links
weekly: if a previously-dead prospect's LinkedIn/Instagram is live again,
it's a resurrection candidate worth a human look.

Reuses validate_links.classify_li / classify_ig / classify_yt - no
reimplementation. IG is paced with jitter (graveyard is tiny so no block
risk, but we stay polite).

Posts a summary to the HL Prospect LI Telegram chat via parameterized
INSERT INTO outbox in /Users/james/.claude/telegram-bot-v3/jeremy.db.
chat_id = -5186707521 (exact, hard-coded - not bash-quoted anywhere).

Backs up prospects.json (timestamped .bak) before any write.
Does NOT touch index.html.
"""
import json
import os
import random
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "/Users/james/highlife-crm")
import validate_links as vl

DATA_PATH = "/Users/james/highlife-crm/prospects.json"
DB_PATH = "/Users/james/.claude/telegram-bot-v3/jeremy.db"
LOG_PATH = "/Users/james/highlife-crm/_graveyard_check_log.txt"
CHAT_ID = "-5186707521"  # HL Prospect LI - exact (outbox.chat_id is TEXT)


def log(msg):
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def backup(path):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = f"{path}.bak.{ts}"
    shutil.copy2(path, dst)
    return dst


def post_to_telegram(text):
    """Parameterized INSERT - never bash-quote $-prefixed text into sqlite."""
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute("PRAGMA table_info(outbox)")
        cols = {row[1] for row in cur.fetchall()}
        if "created_at" in cols:
            cur.execute(
                "INSERT INTO outbox (chat_id, response_text, created_at) "
                "VALUES (?, ?, ?)",
                (CHAT_ID, text, datetime.now(timezone.utc).isoformat()),
            )
        else:
            cur.execute(
                "INSERT INTO outbox (chat_id, response_text) VALUES (?, ?)",
                (CHAT_ID, text),
            )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def main():
    with open(DATA_PATH, "r", encoding="utf-8") as fh:
        prospects = json.load(fh)

    graveyard = [p for p in prospects if p.get("status") == "graveyard"]
    log(f"graveyard prospects: {len(graveyard)}")

    if not graveyard:
        post_to_telegram(
            "Graveyard weekly check: graveyard is empty - nothing to "
            "re-validate this week."
        )
        log("graveyard empty - posted note, done.")
        return

    ig_state = vl.IGState()
    resurrect = []   # at least one link came back live
    still_dead = []  # all links still dead/blocked

    for p in graveyard:
        name = p.get("name", "?")
        pid = p.get("id", "?")
        li = vl.classify_li(p.get("linkedin")) if p.get("linkedin") else "missing"
        yt = vl.classify_yt(p.get("youtube")) if p.get("youtube") else "missing"
        if p.get("instagram"):
            try:
                ig = vl.classify_ig(p.get("instagram"), ig_state)
            except Exception:
                ig = "valid"  # graceful, mirror validate_links
            time.sleep(random.uniform(8, 25))
        else:
            ig = "missing"

        live = [k for k, v in (("LI", li), ("IG", ig), ("YT", yt)) if v == "valid"]
        dead = [k for k, v in (("LI", li), ("IG", ig), ("YT", yt)) if v == "broken"]
        log(f"  {pid} {name}: li={li} ig={ig} yt={yt}")

        entry = f"{name} ({pid}) - live: {','.join(live) or 'none'}"
        if live:
            resurrect.append(entry)
        else:
            still_dead.append(entry)

    ts_h = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"Graveyard weekly check ({ts_h})",
        f"Re-validated {len(graveyard)} graveyard prospect(s).",
        "",
        f"Resurrect candidates (links live again): {len(resurrect)}",
    ]
    for e in resurrect:
        lines.append(f"  - {e}")
    lines.append("")
    lines.append(f"Still dead: {len(still_dead)}")
    for e in still_dead:
        lines.append(f"  - {e}")
    summary = "\n".join(lines)

    row_id = post_to_telegram(summary)
    log(f"posted summary to outbox row id={row_id} chat_id={CHAT_ID}")
    log(
        f"done. resurrect={len(resurrect)} still_dead={len(still_dead)} "
        f"ig_401s={ig_state.total_401s}"
    )


if __name__ == "__main__":
    main()
