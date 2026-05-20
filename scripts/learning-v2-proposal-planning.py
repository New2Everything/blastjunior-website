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

SCRIPT_ID = "learning-v2-proposal-planning-v0"

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

def plan_for_target(target, item):
    if "content_hierarchy.homepage_primary_cta" in target:
        return {
            "proposal_type": "homepage_primary_action_clarity",
            "planning_priority": "high",
            "planning_goal": "Clarify the homepage primary action path without changing visual identity first.",
            "candidate_surfaces": ["public/index.html", "public/styles.css", "components/nav.html"],
            "recommended_probe_followup": [
                "identify current first-screen CTA text",
                "verify whether parent/student visitor can immediately choose next action",
                "check mobile first-screen CTA visibility",
            ],
            "safe_plan_steps": [
                "draft a no-code content hierarchy proposal",
                "compare existing homepage first-screen copy and CTA hierarchy",
                "prepare a source-change proposal packet only after human approval",
            ],
        }

    if "community-experience.make-the-first-successful-action-obvious" in target:
        return {
            "proposal_type": "community_first_success_path",
            "planning_priority": "high",
            "planning_goal": "Make the first successful action for new community visitors explicit.",
            "candidate_surfaces": ["public/index.html", "gallery.html", "profile.html", "components/nav.html"],
            "recommended_probe_followup": [
                "define the first successful action for a new parent/student",
                "check whether community proof appears before asking for action",
                "map current entry points to signup / viewing / participation",
            ],
            "safe_plan_steps": [
                "draft user-path options",
                "separate content proposal from code proposal",
                "do not open source_change_gate until a plan is reviewed",
            ],
        }

    if "event-experience.make-the-first-successful-action-obvious" in target:
        return {
            "proposal_type": "event_first_success_path",
            "planning_priority": "high",
            "planning_goal": "Clarify the first successful action around event participation.",
            "candidate_surfaces": ["public/index.html", "news.html", "gallery.html", "campaigns/events pages if present"],
            "recommended_probe_followup": [
                "identify where event participation is currently explained",
                "check whether schedule / registration / viewing path is obvious",
                "distinguish event viewing, joining, and post-event proof",
            ],
            "safe_plan_steps": [
                "draft event user journey proposal",
                "identify missing evidence before source-change planning",
                "keep proposal planning separate from website edits",
            ],
        }

    return {
        "proposal_type": "generic_research_gap_plan",
        "planning_priority": "medium",
        "planning_goal": "Prepare a proposal planning packet for this approved target.",
        "candidate_surfaces": [],
        "recommended_probe_followup": [],
        "safe_plan_steps": [
            "summarize evidence",
            "draft non-code proposal",
            "wait for human approval before source change",
        ],
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is dry-run/report-only.")
    args = ap.parse_args()

    state = load_json(STATE, {})
    approved_targets = state.get("approved_proposal_planning_targets") or []
    manual_items = state.get("manual_review_items") or []

    item_by_target = {x.get("target_family"): x for x in manual_items if x.get("target_family")}

    proposals = []
    for target in approved_targets:
        item = item_by_target.get(target, {})
        plan = plan_for_target(target, item)
        proposals.append({
            "target_family": target,
            "source_manual_review_item_id": item.get("item_id"),
            "manual_review_status": item.get("status"),
            "review_recommended_count": item.get("review_recommended_count"),
            "signal_present_count": item.get("signal_present_count"),
            "proposal_type": plan["proposal_type"],
            "planning_priority": plan["planning_priority"],
            "planning_goal": plan["planning_goal"],
            "candidate_surfaces": plan["candidate_surfaces"],
            "recommended_probe_followup": plan["recommended_probe_followup"],
            "safe_plan_steps": plan["safe_plan_steps"],
            "proposal_planning_allowed": True,
            "source_change_gate_allowed": False,
            "source_change_allowed_now": False,
            "business_source_written": False,
            "website_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        })

    by_priority = Counter(x["planning_priority"] for x in proposals)
    by_type = Counter(x["proposal_type"] for x in proposals)

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "decision": "proposal_planning_packets_ready",
        "recommended_next_action": "human_review_proposal_plans_before_source_change_gate",
        "approved_target_count": len(approved_targets),
        "proposal_count": len(proposals),
        "by_priority": dict(by_priority),
        "by_type": dict(by_type),
        "proposals": proposals,
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
    json_path = REPORT_DIR / f"learning-v2-proposal-planning-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-proposal-planning-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Proposal Planning Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- decision: `{payload['decision']}`")
    md.append(f"- recommended_next_action: `{payload['recommended_next_action']}`")
    md.append(f"- approved_target_count: `{len(approved_targets)}`")
    md.append(f"- proposal_count: `{len(proposals)}`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Proposals")
    md.append("")

    for p in proposals:
        md.append(f"### {p['target_family']}")
        md.append("")
        md.append(f"- proposal_type: `{p['proposal_type']}`")
        md.append(f"- planning_priority: `{p['planning_priority']}`")
        md.append(f"- planning_goal: {p['planning_goal']}")
        md.append(f"- candidate_surfaces: `{', '.join(p['candidate_surfaces'])}`")
        md.append("- safe_plan_steps:")
        for step in p["safe_plan_steps"]:
            md.append(f"  - {step}")
        md.append("- recommended_probe_followup:")
        for step in p["recommended_probe_followup"]:
            md.append(f"  - {step}")
        md.append(f"- source_change_gate_allowed: `false`")
        md.append("")

    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("proposal_planning = ok")
    print("mode = dry_run")
    print("decision = proposal_planning_packets_ready")
    print("recommended_next_action = human_review_proposal_plans_before_source_change_gate")
    print("approved_target_count =", len(approved_targets))
    print("proposal_count =", len(proposals))
    print("by_priority =", json.dumps(dict(by_priority), ensure_ascii=False))
    print("by_type =", json.dumps(dict(by_type), ensure_ascii=False))
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
    for p in proposals:
        print({
            "target_family": p["target_family"],
            "proposal_type": p["proposal_type"],
            "planning_priority": p["planning_priority"],
            "source_change_gate_allowed": p["source_change_gate_allowed"],
        })

if __name__ == "__main__":
    raise SystemExit(main())
