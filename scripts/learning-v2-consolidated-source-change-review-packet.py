#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
STATE = BASE / "state.json"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-consolidated-source-change-review-packet-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    if default is None:
        default = {}
    try:
        p = Path(path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_load_error": str(e), "_path": str(path)}
    return default

def latest_report(pattern):
    files = sorted(REPORT_DIR.glob(pattern))
    return files[-1] if files else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is report-only.")
    args = ap.parse_args()

    state = load_json(STATE, {})
    review_path = latest_report("learning-v2-proposal-review-packet-dry-run-*.json")
    if not review_path:
        raise SystemExit("no proposal review packet found")

    review = load_json(review_path, {})
    records = review.get("records") or []
    consolidated = review.get("consolidated_recommendation") or {}
    overlapping_surfaces = review.get("overlapping_surfaces") or {}

    approved_targets = state.get("approved_proposal_planning_targets") or []
    evidence_requested_targets = state.get("evidence_requested_targets") or []

    candidate_surfaces = sorted({
        s
        for r in records
        for s in (r.get("candidate_surfaces") or [])
    })

    high_priority_targets = [
        r.get("target_family")
        for r in records
        if r.get("review_priority") in ("high", "medium-high")
    ]

    proposed_review_scope = {
        "packet_type": "consolidated_source_change_review",
        "primary_goal": (
            "Review one combined proposal for homepage/community/event first-success clarity "
            "without opening source_change_gate yet."
        ),
        "included_targets": [r.get("target_family") for r in records],
        "included_surfaces": candidate_surfaces,
        "overlap_reason": (
            "The proposals overlap on public/index.html and related navigation/community surfaces, "
            "so they should be reviewed as one combined change instead of three separate patches."
        ),
        "excluded_or_deferred": [
            {
                "target_family": t,
                "reason": "Evidence was requested first; do not include in source-change review yet."
            }
            for t in evidence_requested_targets
        ],
        "human_review_questions": [
            "Is the homepage first-screen action unclear enough to justify a source-change proposal?",
            "Should community first-success and event first-success be solved together on the homepage?",
            "Should gallery/news/event surfaces be included now, or deferred to a later pass?",
            "What is the smallest acceptable change that improves clarity without disturbing current site stability?",
            "Is mobile evidence required before approving any source-change gate?"
        ],
        "minimum_safe_scope": [
            "No automatic website source edit",
            "No source_change_gate opening",
            "No deploy",
            "No change to business freeze",
            "Only prepare an auditable review packet"
        ],
    }

    risk_assessment = {
        "risk_level": "medium",
        "reason": (
            "The target surfaces include homepage and navigation-related files. Even small UX changes "
            "can affect first impression and mobile behavior, so source_change_gate must remain closed."
        ),
        "required_before_gate": [
            "human approval of consolidated scope",
            "specific file-level change plan",
            "pre-change screenshot/evidence snapshot",
            "rollback plan",
            "post-change validation checklist"
        ],
    }

    recommended_decision = {
        "recommended_next_action": "human_review_consolidated_packet_then_accept_reject_or_request_evidence",
        "allowed_now": [
            "human_review_packet",
            "request_more_evidence",
            "approve_source_change_plan_dry_run_only",
            "reject_or_archive_packet"
        ],
        "blocked_now": [
            "source_change_gate",
            "website_source_change",
            "git_commit_of_business_source",
            "git_push_for_business_source",
            "deploy"
        ],
        "source_change_gate_allowed_now": False,
    }

    by_priority = Counter(r.get("review_priority") for r in records)
    by_decision = Counter(r.get("recommended_decision") for r in records)

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "proposal_review_source": str(review_path),
        "decision": "consolidated_source_change_review_packet_ready",
        "recommended_next_action": recommended_decision["recommended_next_action"],
        "record_count": len(records),
        "approved_target_count": len(approved_targets),
        "evidence_requested_target_count": len(evidence_requested_targets),
        "by_priority": dict(by_priority),
        "by_decision": dict(by_decision),
        "overlapping_surfaces": overlapping_surfaces,
        "consolidated_recommendation": consolidated,
        "proposed_review_scope": proposed_review_scope,
        "risk_assessment": risk_assessment,
        "recommended_decision": recommended_decision,
        "records": records,
        "safety": {
            "state_written": False,
            "business_source_written": False,
            "website_source_written": False,
            "source_change_gate_opened": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
    }

    ts = stamp()
    json_path = REPORT_DIR / f"learning-v2-consolidated-source-change-review-packet-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-consolidated-source-change-review-packet-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Consolidated Source-Change Review Packet")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- decision: `{payload['decision']}`")
    md.append(f"- recommended_next_action: `{payload['recommended_next_action']}`")
    md.append(f"- record_count: `{len(records)}`")
    md.append(f"- source_change_gate_opened: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Proposed Review Scope")
    md.append("")
    md.append(f"- packet_type: `{proposed_review_scope['packet_type']}`")
    md.append(f"- primary_goal: {proposed_review_scope['primary_goal']}")
    md.append(f"- overlap_reason: {proposed_review_scope['overlap_reason']}")
    md.append("")
    md.append("### Included Targets")
    for t in proposed_review_scope["included_targets"]:
        md.append(f"- `{t}`")
    md.append("")
    md.append("### Included Surfaces")
    for s in proposed_review_scope["included_surfaces"]:
        md.append(f"- `{s}`")
    md.append("")
    md.append("### Deferred / Excluded")
    for x in proposed_review_scope["excluded_or_deferred"]:
        md.append(f"- `{x['target_family']}`: {x['reason']}")
    md.append("")
    md.append("## Human Review Questions")
    md.append("")
    for q in proposed_review_scope["human_review_questions"]:
        md.append(f"- {q}")
    md.append("")
    md.append("## Risk Assessment")
    md.append("")
    md.append(f"- risk_level: `{risk_assessment['risk_level']}`")
    md.append(f"- reason: {risk_assessment['reason']}")
    md.append("")
    md.append("### Required Before Gate")
    for x in risk_assessment["required_before_gate"]:
        md.append(f"- {x}")
    md.append("")
    md.append("## Allowed Now")
    for x in recommended_decision["allowed_now"]:
        md.append(f"- `{x}`")
    md.append("")
    md.append("## Blocked Now")
    for x in recommended_decision["blocked_now"]:
        md.append(f"- `{x}`")
    md.append("")
    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("consolidated_source_change_review_packet = ok")
    print("mode = dry_run")
    print("decision = consolidated_source_change_review_packet_ready")
    print("recommended_next_action =", recommended_decision["recommended_next_action"])
    print("proposal_review_source =", review_path)
    print("record_count =", len(records))
    print("approved_target_count =", len(approved_targets))
    print("evidence_requested_target_count =", len(evidence_requested_targets))
    print("included_surfaces =", json.dumps(candidate_surfaces, ensure_ascii=False))
    print("overlapping_surfaces =", json.dumps(overlapping_surfaces, ensure_ascii=False))
    print("risk_level =", risk_assessment["risk_level"])
    print("source_change_gate_opened = false")
    print("state_written = false")
    print("business_source_written = false")
    print("website_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("report_json =", json_path)
    print("report_md =", md_path)

if __name__ == "__main__":
    raise SystemExit(main())
