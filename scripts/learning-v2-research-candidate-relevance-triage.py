#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
RESEARCH = BASE / "research"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

CANDIDATES = RESEARCH / "web-source-candidates.jsonl"
TRIAGE = RESEARCH / "web-source-candidate-relevance-triage.jsonl"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
RESEARCH.mkdir(parents=True, exist_ok=True)

TRIAGE_ID = "learning-v2-research-candidate-relevance-triage-v0"

REJECT_TITLE_PATTERNS = [
    r"\bchiles\b",
    r"\bsalazar\b",
    r"supreme court",
    r"the trevor project",
    r"what you need to know about",
    r"free and customizable sign up sheet",
]

REJECT_DOMAINS = {
    "thetrevorproject.org",
}

MANUAL_REVIEW_TITLE_PATTERNS = [
    r"\bcanva\b",
    r"\bsign up sheet\b",
    r"\btemplates?\b",
    r"\bbehance\b",
    r"\blogos?\b",
]

KEEP_KEYWORDS = [
    "ux", "ui", "case study", "case studies", "sports", "event", "events",
    "landing page", "conversion", "trust", "credibility", "homepage",
    "registration", "schedule", "schedules", "engagement", "community",
    "website", "design", "user experience", "information architecture",
    "content hierarchy", "parent", "membership", "participation",
]

TOPIC_ALLOW_HINTS = {
    "community-experience": ["community", "sports", "case", "membership", "participation"],
    "content-hierarchy": ["content", "hierarchy", "homepage", "information", "architecture", "website"],
    "conversion-design": ["conversion", "landing", "trust", "credibility", "case", "parent", "signup", "sports"],
    "event-experience": ["event", "registration", "schedule", "engagement", "sports", "ux", "ui"],
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]

def append_jsonl(path, rows):
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

def domain_of(url):
    try:
        host = urlparse(url or "").netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""

def match_any(patterns, text):
    return [p for p in patterns if re.search(p, text, flags=re.I)]

def decide(candidate):
    title = candidate.get("title") or ""
    url = candidate.get("url") or candidate.get("url_or_reference") or ""
    topic = candidate.get("topic") or ""
    query_id = candidate.get("query_id") or ""
    confidence = candidate.get("candidate_confidence") or candidate.get("confidence") or ""
    domain = domain_of(url)
    hay = f"{title} {url} {topic} {query_id}".lower()

    reject_matches = match_any(REJECT_TITLE_PATTERNS, hay)
    if domain in REJECT_DOMAINS or reject_matches:
        return {
            "decision": "reject",
            "reason": "obvious_off_topic_or_policy_news_source",
            "matched": reject_matches or [f"domain:{domain}"],
            "confidence": "high",
        }

    manual_matches = match_any(MANUAL_REVIEW_TITLE_PATTERNS, hay)
    if manual_matches:
        return {
            "decision": "needs_manual_review",
            "reason": "possibly_useful_but_too_template_or_portfolio_like",
            "matched": manual_matches,
            "confidence": "medium",
        }

    keep_hits = [kw for kw in KEEP_KEYWORDS if kw in hay]
    topic_hits = [kw for kw in TOPIC_ALLOW_HINTS.get(topic, []) if kw in hay]

    if len(topic_hits) >= 1 and len(keep_hits) >= 2:
        return {
            "decision": "keep",
            "reason": "topic_and_design_keywords_match",
            "matched": sorted(set(topic_hits + keep_hits))[:12],
            "confidence": "medium-high" if confidence in ("medium", "medium-high", "high") else "medium",
        }

    if len(keep_hits) >= 3:
        return {
            "decision": "keep",
            "reason": "sufficient_design_relevance_keywords",
            "matched": sorted(set(keep_hits))[:12],
            "confidence": "medium",
        }

    return {
        "decision": "needs_manual_review",
        "reason": "weak_or_ambiguous_relevance_signal",
        "matched": sorted(set(keep_hits))[:12],
        "confidence": "low",
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    candidates = load_jsonl(CANDIDATES)
    existing = load_jsonl(TRIAGE)
    existing_ids = {x.get("candidate_id") for x in existing if x.get("candidate_id")}

    pending = [c for c in candidates if c.get("candidate_id") not in existing_ids]
    pending = pending[-args.limit:]

    rows = []
    for c in pending:
        d = decide(c)
        rows.append({
            "at": now_iso(),
            "triage_id": TRIAGE_ID,
            "candidate_id": c.get("candidate_id"),
            "query_id": c.get("query_id"),
            "topic": c.get("topic"),
            "title": c.get("title"),
            "url": c.get("url") or c.get("url_or_reference"),
            "candidate_confidence": c.get("candidate_confidence") or c.get("confidence"),
            "decision": d["decision"],
            "reason": d["reason"],
            "matched": d["matched"],
            "triage_confidence": d["confidence"],
            "source_change_allowed_now": False,
            "business_source_written": False,
            "website_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        })

    counts = {}
    for r in rows:
        counts[r["decision"]] = counts.get(r["decision"], 0) + 1

    payload = {
        "generated_at": now_iso(),
        "triage_id": TRIAGE_ID,
        "result": "ok",
        "apply": args.apply,
        "candidate_count": len(candidates),
        "existing_triage_count": len(existing),
        "pending_count": len(pending),
        "triage_count": len(rows),
        "decision_counts": counts,
        "triage_records_written": bool(args.apply and rows),
        "business_source_written": False,
        "website_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "records_preview": rows[:20],
    }

    suffix = "apply" if args.apply else "dry-run"
    out_json = REPORT_DIR / f"research-candidate-relevance-triage-{suffix}-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"research-candidate-relevance-triage-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Candidate Relevance Triage",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- result: `{payload['result']}`",
        f"- apply: `{str(args.apply).lower()}`",
        f"- candidate_count: `{payload['candidate_count']}`",
        f"- existing_triage_count: `{payload['existing_triage_count']}`",
        f"- pending_count: `{payload['pending_count']}`",
        f"- triage_count: `{payload['triage_count']}`",
        f"- decision_counts: `{json.dumps(counts, ensure_ascii=False)}`",
        "- business_source_written: `false`",
        "- website_source_written: `false`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
        "",
        "## Preview",
        "",
    ]

    for r in rows:
        lines.append(f"- `{r['decision']}` | {r['query_id']} | {r['title']} | {r['reason']}")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if args.apply and rows:
        append_jsonl(TRIAGE, rows)

    print("research_candidate_relevance_triage = ok")
    print("mode =", "apply" if args.apply else "dry_run")
    print("candidate_count =", len(candidates))
    print("existing_triage_count =", len(existing))
    print("pending_count =", len(pending))
    print("triage_count =", len(rows))
    print("decision_counts =", json.dumps(counts, ensure_ascii=False))
    print("triage_records_written =", "true" if args.apply and rows else "false")
    print("triage_path =", TRIAGE)
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("business_source_written = false")
    print("website_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print()
    print("records_preview:")
    for r in rows[:20]:
        print({
            "candidate_id": r["candidate_id"],
            "query_id": r["query_id"],
            "topic": r["topic"],
            "title": r["title"],
            "decision": r["decision"],
            "reason": r["reason"],
            "matched": r["matched"],
        })

if __name__ == "__main__":
    raise SystemExit(main())
