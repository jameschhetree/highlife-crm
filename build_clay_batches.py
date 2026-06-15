#!/usr/bin/env python3
"""Build Clay enrichment batch inputs from prospects.json.

Output: one JSON file per batch of 25, ready to submit to
mcp__claude_ai_Clay__find-and-enrich-list-of-contacts.

Scope:
- "refined": skip the 67 records in prospects-flagged-too-big.json
- "all": every prospect missing email

Each record gets a best-guess companyIdentifier from the company name.
Records with low-confidence guesses are flagged for manual review.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/james/highlife-crm")

# Manual domain overrides where the company name doesn't yield an obvious .com.
# Add to this map as misses surface.
DOMAIN_OVERRIDES = {
    "McKinley Media / Google": "mckinleymediagroup.com",
    "Creative Analytics / BRAND-E": "creativeanalytics.com",
    "Strategic Leadership Ventures": "sl-ventures.com",
    "Virgent AI": "virgentai.com",
    "CPAC / American Conservative Union": "cpac.org",
    "The Conservateur": "theconservateur.com",
    "Westwood One / The Daily Caller": "dailycaller.com",
    "Conservative Partnership Institute": "cpi.org",
    "Amtower & Company": "amtower.com",
    "US Global Leadership Coalition": "usglc.org",
    "Cavalry LLC": "cavalryllc.com",
    "Echelon Insights": "echeloninsights.com",
    "Breaking Points": "breakingpoints.com",
    "America First Policy Institute": "americafirstpolicy.com",
    "The Washington Times": "washingtontimes.com",
    "George Washington University GSPM": "gspm.gwu.edu",
    "Bracewell LLP": "bracewell.com",
    "Mehlman Consulting": "mehlmanconsulting.com",
    "Farmers Restaurant Group (Founding Farmers)": "wearefarmers.com",
    "Opus8 / CONNECTpreneur": "opus8.com",
    "Punchbowl News": "punchbowl.news",
    "Happy Black Woman": "happyblackwoman.com",
    "WMAL Radio / Newsmax TV": "wmal.com",
    "American Principles Project": "americanprinciplesproject.org",
    "Independent": None,  # No company; will skip
    "SEVI Properties": "seviproperties.com",
}


def slugify_domain(company: str) -> str | None:
    """Heuristic: 'Foo Bar Co.' -> 'foobar.com'. Returns None if low confidence."""
    if not company or company.lower() in ("independent", "self-employed", "freelance"):
        return None
    # Strip parenthetical asides and slash-separated alt names
    base = re.split(r"[/(]", company, maxsplit=1)[0].strip()
    # Remove common corporate suffixes
    base = re.sub(r"\b(LLC|Inc|Corp|Co|Ltd|LLP|Group|Partners|Holdings|Foundation)\b\.?",
                  "", base, flags=re.I).strip()
    # Lowercase, remove non-alphanumeric
    slug = re.sub(r"[^a-z0-9]", "", base.lower())
    if len(slug) < 3:
        return None
    return f"{slug}.com"


def build_batches(scope: str, batch_size: int = 25) -> list[list[dict]]:
    prospects = json.loads((ROOT / "prospects.json").read_text())
    if scope == "refined":
        refined = json.loads((ROOT / "prospects-refined.json").read_text())
        include_ids = {p["id"] for p in refined}
        needs_enrich = [p for p in prospects
                        if p["id"] in include_ids and not p.get("email")]
    else:
        needs_enrich = [p for p in prospects if not p.get("email")]
    print(f"Scope: {scope} | records to enrich: {len(needs_enrich)}", file=sys.stderr)

    batches = []
    skipped = []
    for chunk_start in range(0, len(needs_enrich), batch_size):
        chunk = needs_enrich[chunk_start:chunk_start + batch_size]
        batch_input = []
        for p in chunk:
            domain = DOMAIN_OVERRIDES.get(p["company"])
            if domain is None and p["company"] not in DOMAIN_OVERRIDES:
                domain = slugify_domain(p["company"])
            if not domain:
                skipped.append({"id": p["id"], "name": p["name"], "company": p["company"]})
                continue
            batch_input.append({
                "id": p["id"],
                "contactName": p["name"],
                "companyIdentifier": domain,
            })
        batches.append(batch_input)
    return batches, skipped


if __name__ == "__main__":
    scope = sys.argv[1] if len(sys.argv) > 1 else "refined"
    batches, skipped = build_batches(scope)
    out_dir = ROOT / "clay-batches"
    out_dir.mkdir(exist_ok=True)
    for i, b in enumerate(batches, 1):
        (out_dir / f"batch-{i:02d}.json").write_text(json.dumps(b, indent=2))
        print(f"batch-{i:02d}.json: {len(b)} records")
    if skipped:
        (out_dir / "skipped.json").write_text(json.dumps(skipped, indent=2))
        print(f"skipped (no company / unclear domain): {len(skipped)}")
    print(f"Total: {sum(len(b) for b in batches)} records in {len(batches)} batches")
