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

SCRIPT_ID = "learning-v2-human-review-decision-applier-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    if default is None:
        default = {}
    try:
        if Path(path).exists():
            return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        return {"_load_error": str(e), "_path": str(path)}
    return default

def latest_report(pattern):
    files = sorted(REPORT_DIR.glob(pattern))
    return files[-1] if files else None

def build_action(record):
    decision = record.get("proposed_decision")
    target = record.get("target_family")

    if decision == "archive_as_superseded":
        return {
            "target_family": target,
            "action": "archive_manual_review_item",
            "status_after": "archived_superseded",
            "proposal_planning_allowed": False,
            "source_change_gate_allowed": False,
            "requires_more_evidence": False,
            "reason": record.get("decision_reason"),
        }

    if decision == "approve_proposal_planning_only":
        return {
            "target_family": target,
            "action": "mark_proposal_planning_approved",
            "status_after": "proposal_planning_approved",
            "proposal_planning_allowed": True,
            "source_change_gate_allowed": False,
            "requires_more_evidence": False,
            "reason": record.get("decision_reason"),
        }

    if decision == "request_mobile_screenshot_evidence":
        return {
            "target_family": target,
            "action": "mark_evidence_requested",
            "status_after": "evidence_requested",
            "proposal_planning_allowed": False,
            "source_change_gate_allowed": False,
            "requires_more_evidence": True,
            "reason": record.get("decision_reason"),
        }

    return {
        "target_family": target,
        "action": "keep_pending",
        "status_after": "pending_manual_review",
        "proposal_planning_allowed": False,
        "source_change_gate_allowed": False,
        "requires_more_evidence": False,
        "reason": "unrecognized or intentionally deferred proposed decision",
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Actually update state.json. Do not use until human approves.")
    args = ap.parse_args()

    state = load_json(STATE, {})
    manual_items = state.get("manual_review_items") or []

    proposal_path = latest_report("learning-v2-human-review-proposed-decisions-dry-run-*.json")
    if not proposal_path:
        raise SystemExit("no proposed decisions report found")

    proposal = load_json(proposal_path, {})
    records = proposal.get("records") or []

    actions = [build_action(r) for r in records]
    action_by_target = {a["target_family"]: a for a in actions}

    existing_targets = {x.get("target_family") for x in manual_items}
    proposal_targets = {x.get("target_family") for x in records}

    missing_in_state = sorted(t for t in proposal_targets if t not in existing_targets)
    missing_in_proposal = sorted(t for t in existing_targets if t not in proposal_targets)

    if missing_in_state:
        result = "blocked"
        failure_reason = "proposed decision references target not present in state manual_review_items"
    else:
        result = "ok"
        failure_reason = None

    updated_preview = []
    archived_preview = []
    proposal_planning_preview = []
    evidence_requested_preview = []
    still_pending_preview = []

    for item in manual_items:
        target = item.get("target_family")
        action = action_by_target.get(target)

        if not action:
            next_item = dict(item)
            next_item["status_after_decision"] = item.get("status")
            next_item["human_review_decision_action"] = "keep_pending_unmapped"
            still_pending_preview.append(target)
            updated_preview.append(next_item)
            continue

        next_item = dict(item)
        next_item["human_review_decision_at"] = now_iso()
        next_item["human_review_decision_action"] = action["action"]
        next_item["human_review_decision_reason"] = action["reason"]
        next_item["status_before_decision"] = item.get("status")
        next_item["status_after_decision"] = action["status_after"]
        next_item["status"] = action["status_after"]
        next_item["proposal_planning_allowed"] = action["proposal_planning_allowed"]
        next_item["source_change_gate_allowed"] = action["source_change_gate_allowed"]
        next_item["requires_more_evidence"] = action["requires_more_evidence"]

        updated_preview.append(next_item)

        if action["action"] == "archive_manual_review_item":
            archived_preview.append(target)
        elif action["action"] == "mark_proposal_planning_approved":
            proposal_planning_preview.append(target)
        elif action["action"] == "mark_evidence_requested":
            evidence_requested_preview.append(target)
        else:
            still_pending_preview.append(target)

    by_action = Counter(a["action"] for a in actions)

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": result,
        "mode": "apply" if args.apply else "dry_run",
        "apply": bool(args.apply),
        "proposal_source": str(proposal_path),
        "manual_review_count_before": len(manual_items),
        "proposed_action_count": len(actions),
        "by_action": dict(by_action),
        "missing_in_state": missing_in_state,
        "missing_in_proposal": missing_in_proposal,
        "failure_reason": failure_reason,
        "archived_preview": archived_preview,
        "proposal_planning_preview": proposal_planning_preview,
        "evidence_requested_preview": evidence_requested_preview,
        "still_pending_preview": still_pending_preview,
        "state_patch_preview": {
            "manual_review_items_after_preview": updated_preview,
            "approved_proposal_planning_targets": proposal_planning_preview,
            "evidence_requested_targets": evidence_requested_preview,
            "archived_manual_review_targets": archived_preview,
            "source_change_gate_opened": False,
            "allow_source_changes": False,
            "allow_git_commit": False,
            "allow_deploy": False,
        },
        "safety": {
            "business_source_written": False,
            "website_source_written": False,
            "source_change_gate_opened": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
    }

    if args.apply:
        # Intentionally conservative. Apply only updates state metadata;
        # it does not open source_change_gate and does not write website source.
        if result != "ok":
            payload["state_written"] = False
        else:
            new_state = dict(state)
            new_state["manual_review_items"] = updated_preview
            new_state["approved_proposal_planning_targets"] = sorted(set(
                (state.get("approved_proposal_planning_targets") or []) + proposal_planning_preview
            ))
            new_state["evidence_requested_targets"] = sorted(set(
                (state.get("evidence_requested_targets") or []) + evidence_requested_preview
            ))
            new_state["archived_manual_review_targets"] = sorted(set(
                (state.get("archived_manual_review_targets") or []) + archived_preview
            ))
            new_state["allow_source_changes"] = False
            new_state["allow_git_commit"] = False
            new_state["allow_deploy"] = False
            STATE.write_text(json.dumps(new_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            payload["state_written"] = True
    else:
        payload["state_written"] = False

    ts = stamp()
    suffix = "apply" if args.apply else "dry-run"
    json_path = REPORT_DIR / f"learning-v2-human-review-decision-applier-{suffix}-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-human-review-decision-applier-{suffix}-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Human Review Decision Applier")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- mode: `{payload['mode']}`")
    md.append(f"- proposal_source: `{payload['proposal_source']}`")
    md.append(f"- manual_review_count_before: `{payload['manual_review_count_before']}`")
    md.append(f"- state_written: `{str(payload['state_written']).lower()}`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Action Summary")
    md.append("")
    for k, v in payload["by_action"].items():
        md.append(f"- {k}: `{v}`")
    md.append("")
    md.append("## Preview")
    md.append("")
    md.append(f"- archived: `{archived_preview}`")
    md.append(f"- proposal_planning_approved: `{proposal_planning_preview}`")
    md.append(f"- evidence_requested: `{evidence_requested_preview}`")
    md.append(f"- still_pending: `{still_pending_preview}`")
    md.append("")
    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("human_review_decision_applier =", result)
    print("mode =", payload["mode"])
    print("proposal_source =", proposal_path)
    print("manual_review_count_before =", len(manual_items))
    print("proposed_action_count =", len(actions))
    print("by_action =", json.dumps(dict(by_action), ensure_ascii=False))
    print("archived_preview =", archived_preview)
    print("proposal_planning_preview =", proposal_planning_preview)
    print("evidence_requested_preview =", evidence_requested_preview)
    print("still_pending_preview =", still_pending_preview)
    print("state_written =", str(payload["state_written"]).lower())
    print("source_change_gate_opened = false")
    print("business_source_written = false")
    print("website_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("report_json =", json_path)
    print("report_md =", md_path)

if __name__ == "__main__":
    raise SystemExit(main())
