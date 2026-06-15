#!/usr/bin/env python3
"""
HighLife CRM - broken-link validator for prospects.json.

- Instagram: queries https://www.instagram.com/api/v1/users/web_profile_info/
  with the public web X-IG-App-ID header.
    * 404 OR (200 + data.user == null) => broken
    * 200 + data.user present          => valid
    * 401 (rate-limit) => exponential backoff, up to 5 retries; if still
      blocked, fall back to "valid" (graceful) and record in _ig_inconclusive.
  Plain GET of /username/ returns an identical login wall for valid and
  broken handles so it's unusable - the web_profile_info endpoint is the
  reliable signal but it's rate-limited aggressively, hence sequential
  pacing at ~1 req/sec.
- YouTube: HTTP GET, look for 404 or "page isn't available". (No YT urls
  in current dataset, but the field is emitted for every prospect per spec.)
- LinkedIn: syntactic check only - LI blocks all unauthed crawlers.

Augments each prospect with `instagram_status`, `linkedin_status`,
`youtube_status` of "valid" | "broken" | "missing".
"""
import json
import re
import time
import urllib.request
import urllib.error

DATA_PATH = "/Users/james/highlife-crm/prospects.json"
INCONCLUSIVE_PATH = "/Users/james/highlife-crm/_ig_inconclusive.json"
LI_SUSPICIOUS_PATH = "/Users/james/highlife-crm/_li_suspicious.json"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
IG_APP_ID = "936619743392459"  # public IG web app id

YT_DEAD_MARKERS = [
    "This page isn't available",
    "This page isn&#x27;t available",
    "404 Not Found",
    "This channel does not exist",
    "page you requested cannot be found",
]

LI_SLUG_RE = re.compile(r"^https://(www\.)?linkedin\.com/in/[A-Za-z0-9\-_%.]+/?$")
IG_HANDLE_RE = re.compile(r"^https?://(www\.)?instagram\.com/([A-Za-z0-9_.]+)/?")


# ----- low-level HTTP -----

def http_get(url, headers, timeout=8):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(400_000).decode("utf-8", errors="ignore")
            return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = e.read(200_000).decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        return e.code, body
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return None, None


def http_get_retry(url, headers, timeout=8):
    s, b = http_get(url, headers, timeout=timeout)
    if s is None:
        time.sleep(0.5)
        s, b = http_get(url, headers, timeout=timeout)
    return s, b


# ----- per-platform classifiers -----

def extract_ig_handle(url):
    if not url:
        return None
    m = IG_HANDLE_RE.match(url.strip())
    if not m:
        return None
    h = m.group(2).strip("/").lower()
    if h in {"p", "reel", "tv", "explore", "stories", "accounts", "directory"}:
        return None
    return h


class IGState:
    """Carries rate-limit state across calls so we can back off globally."""
    def __init__(self):
        self.consecutive_401s = 0
        self.total_401s = 0
        self.total_404s = 0
        self.total_valid = 0
        self.inconclusive = []  # urls we couldn't verify

    def note_ok(self):
        self.consecutive_401s = 0

    def note_401(self):
        self.consecutive_401s += 1
        self.total_401s += 1


def classify_ig(url, ig_state):
    if not url:
        return "missing"
    handle = extract_ig_handle(url)
    if not handle:
        return "broken"  # malformed
    api_url = (
        f"https://www.instagram.com/api/v1/users/web_profile_info/?username={handle}"
    )
    headers = {
        "User-Agent": UA,
        "X-IG-App-ID": IG_APP_ID,
        "Accept": "application/json",
    }

    # Up to 5 attempts with exponential backoff on 401.
    backoffs = [3, 8, 20, 45, 90]
    last_status = None
    for attempt, sleep_before in enumerate([0] + backoffs):
        if sleep_before:
            time.sleep(sleep_before)
        status, body = http_get(api_url, headers=headers, timeout=10)
        last_status = status
        if status == 404:
            ig_state.note_ok()
            ig_state.total_404s += 1
            return "broken"
        if status == 200 and body:
            try:
                j = json.loads(body)
                user = j.get("data", {}).get("user")
                ig_state.note_ok()
                if user is None:
                    ig_state.total_404s += 1
                    return "broken"
                ig_state.total_valid += 1
                return "valid"
            except Exception:
                # non-JSON 200 - rare; treat as inconclusive
                break
        if status == 401:
            ig_state.note_401()
            continue  # retry after backoff
        if status is None:
            # network failure - one retry then give up
            time.sleep(1)
            status, body = http_get(api_url, headers=headers, timeout=10)
            last_status = status
            if status == 404:
                ig_state.total_404s += 1
                return "broken"
            if status == 200 and body:
                try:
                    j = json.loads(body)
                    user = j.get("data", {}).get("user")
                    if user is None:
                        ig_state.total_404s += 1
                        return "broken"
                    ig_state.total_valid += 1
                    return "valid"
                except Exception:
                    break
            break
        # other 4xx/5xx - inconclusive
        break

    ig_state.inconclusive.append({"url": url, "handle": handle, "last_status": last_status})
    return "valid"  # graceful: never false-positive broken


def classify_yt(url):
    if not url:
        return "missing"
    status, body = http_get_retry(
        url, headers={"User-Agent": UA, "Accept": "text/html"}, timeout=8
    )
    if status == 404:
        return "broken"
    if status is None:
        return "valid"
    if body:
        snippet = body[:80_000]
        for m in YT_DEAD_MARKERS:
            if m in snippet:
                return "broken"
    if status and 200 <= status < 400:
        return "valid"
    return "valid"


def classify_li(url):
    if not url:
        return "missing"
    if LI_SLUG_RE.match(url.strip()):
        return "valid"
    return "broken"


# ----- driver -----

def main():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        prospects = json.load(f)
    total = len(prospects)
    print(f"loaded {total} prospects from {DATA_PATH}", flush=True)

    # LinkedIn: syntactic, sync.
    li_suspicious = []
    for p in prospects:
        url = p.get("linkedin")
        s = classify_li(url)
        p["linkedin_status"] = s
        if s == "broken" and url:
            li_suspicious.append({"id": p.get("id"), "name": p.get("name"), "url": url})

    # YouTube: not present in current data, but emit field.
    for p in prospects:
        p["youtube_status"] = classify_yt(p.get("youtube"))

    # Instagram: sequential, ~1 req/sec, with backoff on 401.
    for p in prospects:
        if not p.get("instagram"):
            p["instagram_status"] = "missing"

    ig_jobs = [p for p in prospects if p.get("instagram")]
    print(f"validating {len(ig_jobs)} instagram urls sequentially "
          f"(~1 req/sec, backoff on 401)...", flush=True)

    ig_state = IGState()
    started = time.time()
    for idx, p in enumerate(ig_jobs, 1):
        try:
            p["instagram_status"] = classify_ig(p["instagram"], ig_state)
        except Exception:
            p["instagram_status"] = "valid"
            ig_state.inconclusive.append(
                {"url": p["instagram"], "handle": None, "last_status": "exception"}
            )
        if idx % 25 == 0 or idx == len(ig_jobs):
            elapsed = time.time() - started
            print(
                f"progress: {idx}/{len(ig_jobs)} instagram validated "
                f"| valid={ig_state.total_valid} broken={ig_state.total_404s} "
                f"401s={ig_state.total_401s} inconclusive={len(ig_state.inconclusive)} "
                f"| elapsed={elapsed:.0f}s",
                flush=True,
            )
        time.sleep(1.0)

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(prospects, f, indent=2, ensure_ascii=False)
    print(f"wrote augmented data back to {DATA_PATH}", flush=True)

    with open(LI_SUSPICIOUS_PATH, "w", encoding="utf-8") as f:
        json.dump(li_suspicious, f, indent=2, ensure_ascii=False)
    with open(INCONCLUSIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(ig_state.inconclusive, f, indent=2, ensure_ascii=False)

    print(
        f"summary: ig_valid={ig_state.total_valid} ig_broken={ig_state.total_404s} "
        f"ig_inconclusive={len(ig_state.inconclusive)} total_401_responses={ig_state.total_401s}",
        flush=True,
    )
    print(f"li_suspicious={len(li_suspicious)} flagged", flush=True)


if __name__ == "__main__":
    main()
