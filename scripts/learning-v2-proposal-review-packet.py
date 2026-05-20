#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter, defaultdict

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
STATE = BASE / "state.json"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-proposal-review-packet-v0"

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

def review_recommendation(proposal):
    target = proposal.get("target_family") or ""
    ptype = proposal.get("proposal_type") or ""
    surfaces = proposal.get("candidate_surfaces") or []

    if "homepage_primary_cta" in target or ptype == "homepage_primary_action_clarity":
        return {
            "recommended_decision": "include_in_consolidated_source_change_review",
            "review_priority": "high",
            "reason": "Homepage primary action clarity is central and overlaps with first-success path improvements.",
            "source_change_gate_allowed_now": False,
        }

    if "community_first_success_path" == ptype:
        return {
            "recommended_decision": "merge_into_consolidated_homepage_first_success_review",
            "review_priority": "high",
            "reason": "Community first-success path overlaps with homepage CTA and should not become a separate isolated patch.",
            "source_change_gate_allowed_now": False,
        }

    if "event_first_success_path" == ptype:
        return {
            "recommended_decision": "merge_into_consolidated_event_entry_review",
            "review_priority": "medium-high",
            "reason": "Event first-success path is valuable, but should be reviewed together with homepage/community entry paths.",
            "source_change_gate_allowed_now": False,
        }

    return {
        "recommended_decision": "keep_pending_for_human_review",
        "review_priority": "medium",
        "reason": "Proposal needs human review before any source-change gate decision.",
        "source_change_gate_allowed_now": False,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 only writes reports.")
    args = ap.parse_args()

    state = load_json(STATE, {})
    plan_path = latest_report("learning-v2-proposal-planning-dry-run-*.json")
    if not plan_path:
        raise SystemExit("no proposal planning report found")

    plan = load_json(plan_path, {})
    proposals = plan.get("proposals") or []

    records = []
    surface_to_targets = defaultdict(list)

    for p in proposals:
        rec = review_recommendation(p)
        surfaces = p.get("candidate_surfaces") or []
        for s in surfaces:
            surface_to_targets[s].append(p.get("target_family"))

        records.append({
            "target_family": p.get("target_family"),
            "proposal_type": p.get("proposal_type"),
            "planning_priority": p.get("planning_priority"),
            "planning_goal": p.get("planning_goal"),
            "candidate_surfaces": surfaces,
            "safe_plan_steps": p.get("safe_plan_steps") or [],
            "recommended_probe_followup": p.get("recommended_probe_followup") or [],
            "recommended_decision": rec["recommended_decision"],
            "review_priority": rec["review_priority"],
            "decision_reason": rec["reason"],
            "source_change_gate_allowed_now": False,
            "business_source_written": False,
            "website_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        })

    overlapping_surfaces = {
        surface: targets
        for surface, targets in surface_to_targets.items()
        if len(set(targets)) > 1
    }

    by_decision = Counter(r["recommended_decision"] for r in records)
    by_priority = Counter(r["review_priority"] for r in records)

    consolidated_recommendation = {
        "recommended_decision": "prepare_one_consolidated_source_change_review_packet",
        "reason": (
            "The three proposals overlap around homepage, community entry, and event entry. "
            "They should be reviewed as one consolidated human proposal before any source_change_gate opens."
        ),
        "suggested_scope": [
            "homepage first-screen action clarity",
            "community first-success path",
            "event participation entry path",
            "mobile/visual evidence remains separate because mobile_first.nav_density requested evidence, not planning",
        ],
        "source_change_gate_allowed_now": False,
    }

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "planning_source": str(plan_path),
        "decision": "proposal_review_packet_ready",
        "recommended_next_action": "human_review_consolidated_proposal_before_any_source_change_gate",
        "proposal_count": len(records),
        "by_decision": dict(by_decision),
        "by_priority": dict(by_priority),
        "overlapping_surfaces": overlapping_surfaces,
        "consolidated_recommendation": consolidated_recommendation,
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
    json_path = REPORT_DIR / f"learning-v2-proposal-review-packet-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-proposal-review-packet-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Proposal Review Packet")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- decision: `{payload['decision']}`")
    md.append(f"- recommended_next_action: `{payload['recommended_next_action']}`")
    md.append(f"- proposal_count: `{len(records)}`")
    md.append(f"- source_change_gate_opened: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Consolidated Recommendation")
    md.append("")
    md.append(f"- recommended_decision: `{consolidated_recommendation['recommended_decision']}`")
    md.append(f"- reason: {consolidated_recommendation['reason']}")
    md.append("- suggested_scope:")
    for x in consolidated_recommendation["suggested_scope"]:
        md.append(f"  - {x}")
    md.append("")
    md.append("## Overlapping Surfaces")
    md.append("")
    if overlapping_surfaces:
        for surface, targets in overlapping_surfaces.items():
            md.append(f"- `{surface}`: `{', '.join(targets)}`")
    else:
        md.append("- none")
    md.append("")
    md.append("## Proposal Records")
    md.append("")

    for r in records:
        md.append(f"### {r['target_family']}")
        md.append("")
        md.append(f"- proposal_type: `{r['proposal_type']}`")
        md.append(f"- review_priority: `{r['review_priority']}`")
        md.append(f"- recommended_decision: `{r['recommended_decision']}`")
        md.append(f"- decision_reason: {r['decision_reason']}")
        md.append(f"- candidate_surfaces: `{', '.join(r['candidate_surfaces'])}`")
        md.append(f"- source_change_gate_allowed_now: `false`")
        md.append("")

    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("proposal_review_packet = ok")
    print("mode = dry_run")
    print("decision = proposal_review_packet_ready")
    print("recommended_next_action = human_review_consolidated_proposal_before_any_source_change_gate")
    print("planning_source =", plan_path)
    print("proposal_count =", len(records))
    print("by_decision =", json.dumps(dict(by_decision), ensure_ascii=False))
    print("by_priority =", json.dumps(dict(by_priority), ensure_ascii=False))
    print("overlapping_surfaces =", json.dumps(overlapping_surfaces, ensure_ascii=False))
    print("consolidated_recommendation =", consolidated_recommendation["recommended_decision"])
    print("report_json =", json_path)
    print("report_md =", md_path)
    print("state_written = false")
    print("business_source_written = false")
    print("website_source_written = false")
    print("source_change_gate_opened = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print()
    for r in records:
        print({
            "target_family": r["target_family"],
            "proposal_type": r["proposal_type"],
            "review_priority": r["review_priority"],
            "recommended_decision": r["recommended_decision"],
        })

if __name__ == "__main__":
    raise SystemExit(main())
