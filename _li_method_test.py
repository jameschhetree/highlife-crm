#!/usr/bin/env python3
"""METHOD TEST on 5 prospects: SearXNG (priv.au) real-browser search,
name-matched linkedin.com/in extraction. Proves the method returns real,
person-correct LI profile slugs before the full 620 run."""
import json, re, time, random, urllib.parse, unicodedata
from playwright.sync_api import sync_playwright

LI_IN_RE = re.compile(r"linkedin\.com/in/([A-Za-z0-9\-_%.]+)", re.I)

SEARX = [
    "https://priv.au/search?q=",
    "https://search.inetol.net/search?q=",
    "https://opnxng.com/search?q=",
]

def deaccent(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                    if not unicodedata.combining(c))

def norm_slug(s):
    if not s:
        return None
    s = s.strip().lower()
    m = LI_IN_RE.search(s)
    if m:
        s = m.group(1)
    s = s.split("?")[0].split("#")[0].rstrip("/")
    try:
        s = urllib.parse.unquote(s)
    except Exception:
        pass
    return s or None

def name_tokens(name):
    n = deaccent(name).lower()
    n = re.sub(r"[^a-z\s\-]", " ", n)
    return [t for t in re.split(r"[\s\-]+", n) if len(t) > 1]

def title_matches_person(title, name):
    """LI result titles look like 'First Last - Job | LinkedIn'.
    Require first AND last name token present in title."""
    t = deaccent(title).lower()
    toks = name_tokens(name)
    if len(toks) < 2:
        return toks and toks[0] in t
    return toks[0] in t and toks[-1] in t

def search_person(pg, name, company):
    """Return list of (slug, title) for name-matched linkedin.com/in results."""
    queries = [
        f'"{name}" {company.split("/")[0].strip()} linkedin'.strip(),
        f'"{name}" linkedin.com/in',
    ]
    results = []
    used_q = None
    for q in queries:
        used_q = q
        got_any = False
        for base in SEARX:
            url = base + urllib.parse.quote(q)
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=22000)
            except Exception:
                continue
            time.sleep(random.uniform(2.0, 3.0))
            html = pg.content()
            low = html.lower()
            if any(k in low for k in ("just a moment", "captcha",
                                      "too many request", "rate limit")):
                continue
            try:
                rows = pg.eval_on_selector_all(
                    "article.result, .result",
                    "els => els.map(x => ({h:x.innerHTML, t:(x.innerText||'')}))")
            except Exception:
                rows = []
            for r in rows:
                for m in LI_IN_RE.finditer(r["h"]):
                    slug = norm_slug(m.group(1))
                    if not slug or slug == "in":
                        continue
                    if title_matches_person(r["t"], name):
                        results.append((slug, r["t"].split("\n")[0][:80]))
            got_any = bool(rows)
            if results or got_any:
                break  # this instance worked; don't hit others
        if results:
            break  # query produced matches; stop
    # dedupe slugs preserve order
    seen, out = set(), []
    for sl, ti in results:
        if sl not in seen:
            seen.add(sl)
            out.append((sl, ti))
    return out, used_q

if __name__ == "__main__":
    p = json.load(open("/Users/james/highlife-crm/prospects.json"))
    sample = [x for x in p if x.get("linkedin_status") == "valid"][:5]
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True)
        ctx = br.new_context(
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"),
            viewport={"width": 1366, "height": 900}, locale="en-US")
        pg = ctx.new_page()
        for x in sample:
            stored = norm_slug(x["linkedin"])
            found, q = search_person(pg, x["name"], x.get("company", ""))
            fslugs = [s for s, _ in found]
            verdict = ("valid" if stored in fslugs else
                       "broken-mismatch" if fslugs else "broken-no-result")
            print(f"[{x['id']}] {x['name']}  ({x.get('company','')})")
            print(f"   query     : {q}")
            print(f"   stored    : {stored}")
            print(f"   found     : {found[:6]}")
            print(f"   VERDICT   : {verdict}")
            print("---")
            time.sleep(random.uniform(4, 8))
        br.close()
