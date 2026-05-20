#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

PROBE_ID = "learning-v2-research-derived-observe-only-probe-v0"
CANDIDATE = json.loads('{\n  "candidate_id": "candidate-event-experience.keep-visual-design-energetic-but-structu-20260520-103803",\n  "target_family": "event-experience.keep-visual-design-energetic-but-structu",\n  "topic": "research-derived",\n  "risk": "low",\n  "pattern_count": 3,\n  "activation_allowed_now": true,\n  "activation_status": "candidate_ready_for_observe_only_probe_design",\n  "observe_only_first": true,\n  "recommended_stage": "event-experience_keep-visual-design-energetic-but-structu_probe",\n  "recommended_probe_script": "learning-v2-event-experience-keep-visual-design-energetic-but-structu-probe.py",\n  "recommended_probe_script_exists": false,\n  "principles": [\n    "Keep visual design energetic but structured, with responsive sections that remain readable on mobile.",\n    "Keep visual design energetic but structured, with responsive sections that remain readable on mobile.",\n    "Keep visual design energetic but structured, with responsive sections that remain readable on mobile."\n  ],\n  "source_titles": [\n    "FOX Sports Sporting Events UI UX Design | Sports & Media",\n    "Sports Technology UX Design: Enhancing User Experience in Sports ...",\n    "UX for Event Websites: Registration, Schedules, and Engagement"\n  ],\n  "score": 210,\n  "selector_ready": false,\n  "blockers": [\n    "recommended_probe_script_missing:learning-v2-event-experience-keep-visual-design-energetic-but-structu-probe.py"\n  ],\n  "jsonl_line": 16\n}')

SCAN_FILES = [
    "public/index.html",
    "index.html",
    "public/gallery.html",
    "public/news.html",
    "public/campaigns.html",
    "public/profile.html",
    "components/nav.html",
    "public/styles.css",
]

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "before",
    "after", "should", "clearly", "communities", "community", "users",
    "visitors", "members", "action", "good", "looks", "what", "how",
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def clean_text(s):
    return re.sub(r"\s+", " ", s or "").strip()

def read_site_files():
    rows = []
    for rel in SCAN_FILES:
        p = WORKSPACE / rel
        if not p.exists() or not p.is_file():
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        rows.append({
            "path": rel,
            "text": txt,
            "text_lower": txt.lower(),
            "length": len(txt),
        })
    return rows

def keywords_for(principle):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+", (principle or "").lower())
    out = []
    for w in words:
        w = w.strip("-_")
        if len(w) < 4:
            continue
        if w in STOPWORDS:
            continue
        if w not in out:
            out.append(w)
    return out[:14]

def score_principle(principle, files):
    kws = keywords_for(principle)
    file_hits = []
    total_hits = 0

    for f in files:
        matched = []
        for kw in kws:
            n = f["text_lower"].count(kw)
            if n:
                matched.append({"keyword": kw, "count": n})
                total_hits += n
        if matched:
            file_hits.append({
                "path": f["path"],
                "matched_keywords": matched[:12],
            })

    status = "signal_present" if total_hits >= 3 else "review_recommended"
    return {
        "principle": principle,
        "keywords": kws,
        "total_keyword_hits": total_hits,
        "file_hits": file_hits,
        "status": status,
        "reason": (
            "existing_site_has_some_matching_language"
            if status == "signal_present"
            else "observe_only_probe_found_low_matching_signal_in_site_files"
        ),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="reserved; this probe never modifies website source")
    args = ap.parse_args()

    files = read_site_files()
    principles = CANDIDATE.get("principles") or []
    findings = [score_principle(p, files) for p in principles]

    review_findings = [x for x in findings if x.get("status") == "review_recommended"]
    signal_findings = [x for x in findings if x.get("status") == "signal_present"]

    target_family = CANDIDATE.get("target_family")
    safe_family = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(target_family or "unknown")).strip("-")[:90] or "unknown"

    payload = {
        "generated_at": now_iso(),
        "probe_id": PROBE_ID,
        "result": "ok",
        "target_family": target_family,
        "candidate_id": CANDIDATE.get("candidate_id"),
        "topic": CANDIDATE.get("topic"),
        "recommended_stage": CANDIDATE.get("recommended_stage"),
        "pattern_count": CANDIDATE.get("pattern_count"),
        "source_titles": CANDIDATE.get("source_titles") or [],
        "scanned_file_count": len(files),
        "finding_count": len(findings),
        "review_recommended_count": len(review_findings),
        "signal_present_count": len(signal_findings),
        "findings": findings,
        "policy": {
            "observe_only": True,
            "state_written": False,
            "business_source_written": False,
            "website_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "source_change_gate_opened": False,
        },
    }

    out_json = REPORT_DIR / f"research-derived-probe-{safe_family}-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"research-derived-probe-{safe_family}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Research-Derived Observe-Only Probe",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- target_family: `{target_family}`",
        f"- candidate_id: `{payload['candidate_id']}`",
        f"- result: `{payload['result']}`",
        f"- scanned_file_count: `{payload['scanned_file_count']}`",
        f"- finding_count: `{payload['finding_count']}`",
        f"- review_recommended_count: `{payload['review_recommended_count']}`",
        f"- signal_present_count: `{payload['signal_present_count']}`",
        "- state_written: `false`",
        "- business_source_written: `false`",
        "- website_source_written: `false`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
        "",
        "## Findings",
        "",
    ]

    for item in findings:
        lines += [
            f"### {item.get('status')}",
            "",
            f"- principle: {item.get('principle')}",
            f"- total_keyword_hits: `{item.get('total_keyword_hits')}`",
            f"- reason: `{item.get('reason')}`",
            "",
        ]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("research_derived_observe_only_probe = ok")
    print("target_family =", target_family)
    print("candidate_id =", payload["candidate_id"])
    print("scanned_file_count =", len(files))
    print("finding_count =", len(findings))
    print("review_recommended_count =", len(review_findings))
    print("signal_present_count =", len(signal_findings))
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("state_written = false")
    print("business_source_written = false")
    print("website_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
