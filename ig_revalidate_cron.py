#!/usr/bin/env python3
"""
HighLife CRM - throttled Instagram re-validation cron ("make it not hot").

WHY: Running validate_links.py against all ~274 IG handles at ~1 req/sec got
us IP-blocked by Meta (HTTP 401 for every handle, including known-good
@zuck/@mercedesschlapp). This script spreads the same work across many hours
so we never present a burst Meta can fingerprint as a scraper.

RATE MATH (the hard constraint = never trip Meta's IP block):
  - IG handles in prospects.json: ~274 (status: instagram != "").
  - BATCH_SIZE = 12 handles per invocation.
  - Full sweep = ceil(274 / 12) = 23 invocations.
  - launchd interval = 1800s (30 min)  -> see com.claude.hl-ig-revalidate.plist
  - One full sweep   = 23 * 30 min     ~= 11.5 hours, then cursor loops to 0.
  - Average request rate = 12 req / 1800s = 1 request per 150 seconds.
  - Within a batch, sleep is randomized 8-25s between handles, so the 12
    requests are smeared over ~2-5 min, then the IP is silent for ~25+ min.
  This is two orders of magnitude gentler than the 1 req/sec that got blocked,
  and the burst window is short with long silence after -> not "hot".

  On HTTP 401/429 we abort the rest of the batch immediately and back off
  (BACKOFF_AFTER_BLOCK_RUNS skipped invocations). We do NOT mark the
  remaining handles broken - we reuse validate_links.classify_ig, whose
  documented graceful behaviour is "never false-positive broken": on
  inconclusive/blocked it returns "valid" and records it in _ig_inconclusive.
  This cron only WRITES BACK statuses that classify_ig actually resolved
  this run (it only ever calls classify_ig on handles it intends to keep),
  and on a detected block it stops calling classify_ig at all for the rest
  of the batch so blocked handles keep their prior status untouched.

Checkpoint: /Users/james/highlife-crm/_ig_revalidate_cursor.json
  { "cursor": <int>, "total": <int>, "last_run": <iso>,
    "blocked_until_run": <int>, "run_counter": <int> }
The cursor rotates: each run validates handles [cursor : cursor+BATCH_SIZE],
then advances; when it passes the end it wraps to 0 (continuous loop).

Backs up prospects.json (timestamped .bak) before every write.
Does NOT touch index.html.
"""
import json
import os
import random
import shutil
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "/Users/james/highlife-crm")
import validate_links as vl  # reuse classify_ig + IGState (no reimplementation)

DATA_PATH = "/Users/james/highlife-crm/prospects.json"
CURSOR_PATH = "/Users/james/highlife-crm/_ig_revalidate_cursor.json"
LOG_PATH = "/Users/james/highlife-crm/_ig_revalidate_log.txt"

BATCH_SIZE = 12
JITTER_MIN_S = 8
JITTER_MAX_S = 25
# When a block (401/429) is detected, skip this many *future* invocations
# before trying IG again (30 min/run -> 6 runs = ~3 h cool-down).
BACKOFF_AFTER_BLOCK_RUNS = 6


def log(msg):
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def load_cursor():
    if os.path.exists(CURSOR_PATH):
        try:
            with open(CURSOR_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "cursor": 0,
        "total": 0,
        "last_run": None,
        "blocked_until_run": 0,
        "run_counter": 0,
    }


def save_cursor(state):
    tmp = CURSOR_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
    os.replace(tmp, CURSOR_PATH)


def backup(path):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = f"{path}.bak.{ts}"
    shutil.copy2(path, dst)
    return dst


def main():
    batch_size = BATCH_SIZE
    for arg in sys.argv[1:]:
        if arg.startswith("--batch="):
            batch_size = int(arg.split("=", 1)[1])

    state = load_cursor()
    state["run_counter"] = int(state.get("run_counter", 0)) + 1
    run_no = state["run_counter"]

    if run_no < int(state.get("blocked_until_run", 0)):
        log(
            f"run {run_no}: in post-block cool-down until run "
            f"{state['blocked_until_run']} - skipping IG calls entirely."
        )
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        save_cursor(state)
        return

    with open(DATA_PATH, "r", encoding="utf-8") as fh:
        prospects = json.load(fh)

    ig_jobs = [p for p in prospects if p.get("instagram")]
    total = len(ig_jobs)
    state["total"] = total
    if total == 0:
        log("no instagram handles in dataset - nothing to do.")
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        save_cursor(state)
        return

    cursor = int(state.get("cursor", 0)) % total
    end = min(cursor + batch_size, total)
    batch = ig_jobs[cursor:end]
    log(
        f"run {run_no}: validating IG handles [{cursor}:{end}] of {total} "
        f"(batch_size={batch_size})"
    )

    ig_state = vl.IGState()
    processed = 0
    blocked = False

    for i, p in enumerate(batch):
        # Detect a block BEFORE issuing the next request: if classify_ig has
        # already eaten 401s and is consecutively blocked, stop the batch so
        # we never hammer and never overwrite remaining handles' statuses.
        if ig_state.consecutive_401s >= 2:
            blocked = True
            log(
                f"run {run_no}: detected IG block (consecutive_401s="
                f"{ig_state.consecutive_401s}) after {processed} handles - "
                f"aborting rest of batch, NOT marking remaining broken."
            )
            break

        url = p.get("instagram")
        prior = p.get("instagram_status")
        try:
            status = vl.classify_ig(url, ig_state)
        except Exception as e:  # graceful, mirror validate_links
            log(f"  {p.get('id')} {url} -> exception {e!r}; left as {prior}")
            continue

        # classify_ig returns "valid" both for genuinely valid AND for inconclusive/
        # blocked (graceful no-false-positive). If this call logged a fresh
        # 401, treat it as inconclusive -> do NOT overwrite prior status.
        was_inconclusive = any(
            ent.get("url") == url for ent in ig_state.inconclusive
        )
        if was_inconclusive:
            log(f"  {p.get('id')} {url} -> inconclusive (block/err); kept {prior}")
        else:
            p["instagram_status"] = status
            processed += 1
            log(f"  {p.get('id')} {url} -> {status} (was {prior})")

        if ig_state.total_401s > 0:
            blocked = True
            log(
                f"run {run_no}: saw {ig_state.total_401s} 401(s) - flagging "
                f"block, will finish loop guard then back off."
            )

        if i < len(batch) - 1:
            sleep_s = random.uniform(JITTER_MIN_S, JITTER_MAX_S)
            log(f"  jitter sleep {sleep_s:.1f}s")
            time.sleep(sleep_s)

    # Persist results (only handles we actually resolved were mutated).
    if processed > 0:
        bak = backup(DATA_PATH)
        tmp = DATA_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(prospects, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, DATA_PATH)
        log(f"wrote {processed} resolved IG statuses back; backup={bak}")
    else:
        log("no IG statuses resolved this run (nothing written).")

    # Advance / wrap cursor only by the count we actually attempted, so a
    # blocked batch is retried (not silently skipped) next sweep.
    advanced = len(batch) if not blocked else max(processed, 0)
    new_cursor = cursor + advanced
    if new_cursor >= total:
        new_cursor = 0
        log(f"run {run_no}: full sweep complete - cursor wraps to 0.")
    state["cursor"] = new_cursor

    if blocked:
        state["blocked_until_run"] = run_no + BACKOFF_AFTER_BLOCK_RUNS
        log(
            f"run {run_no}: BLOCK back-off engaged - skipping IG until run "
            f"{state['blocked_until_run']} (~{BACKOFF_AFTER_BLOCK_RUNS*30} min)."
        )

    state["last_run"] = datetime.now(timezone.utc).isoformat()
    save_cursor(state)
    log(
        f"run {run_no}: done. next cursor={state['cursor']} "
        f"valid={ig_state.total_valid} broken={ig_state.total_404s} "
        f"401s={ig_state.total_401s} inconclusive={len(ig_state.inconclusive)}"
    )


if __name__ == "__main__":
    main()
