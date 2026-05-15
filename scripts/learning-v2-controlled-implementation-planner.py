#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

PLANNER_ID = "learning-v2-controlled-implementation-planner-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def latest_json(pattern):
    files = sorted(REPORT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None, {}
    p = files[0]
    try:
        return p, json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return p, {"__load_error__": str(e)}

def main():
    failures = []
    warnings = []

    impl_path, impl = latest_json("learning-v2-implementation-readiness-gate-*.json")
    outcome_path, outcome = latest_json("learning-v2-review-outcome-*.json")
    packet_path, packet = latest_json("learning-v2-human-design-review-packet-*.json")

    if not impl_path:
        failures.append("missing_implementation_readiness_gate_report")
    if impl.get("__load_error__"):
        failures.append(f"implementation_readiness_load_error:{impl.get('__load_error__')}")
    if impl.get("result") != "ok":
        failures.append(f"implementation_readiness_result_not_ok:{impl.get('result')}")

    if not outcome_path:
        failures.append("missing_review_outcome_report")
    if outcome.get("__load_error__"):
        failures.append(f"review_outcome_load_error:{outcome.get('__load_error__')}")
    if outcome.get("result") != "ok":
        failures.append(f"review_outcome_result_not_ok:{outcome.get('result')}")

    if not packet_path:
        failures.append("missing_design_review_packet")
    if packet.get("__load_error__"):
        failures.append(f"packet_load_error:{packet.get('__load_error__')}")
    if packet.get("result") != "ok":
        failures.append(f"packet_result_not_ok:{packet.get('result')}")

    for name, payload in [
        ("implementation_readiness", impl),
        ("review_outcome", outcome),
        ("packet", packet),
    ]:
        policy = payload.get("policy") or {}
        for key in [
            "website_files_changed",
            "git_commit",
            "git_push",
            "deploy",
            "implementation_gate_opened",
            "source_change_gate_opened",
        ]:
            if policy.get(key) is not False:
                failures.append(f"{name}_policy_{key}_not_false:{policy.get(key)}")

    decision = impl.get("decision")
    readiness_decision = impl.get("readiness_decision")

    if readiness_decision == "implementation_planning_ready_source_change_closed" and decision == "accept":
        planning_status = "implementation_plan_ready_dry_run_only"
        next_safe_action = "prepare_source_change_gate_review"
        plan_items = [
            "Identify exact target files for event.storytelling_path implementation.",
            "Prepare isolated dry-run diff plan.",
            "Define post-apply validation checks.",
            "Require separate source-change gate before any file edit.",
        ]
    elif readiness_decision == "implementation_readiness_waiting_for_review_signal":
        planning_status = "not_ready_waiting_for_review_signal"
        next_safe_action = "await_more_review_signal"
        plan_items = []
    elif readiness_decision in [
        "implementation_readiness_blocked_revision_needed",
        "implementation_readiness_blocked_rejected",
    ]:
        planning_status = "blocked_by_review_outcome"
        next_safe_action = impl.get("next_safe_action") or "stop"
        plan_items = []
    else:
        planning_status = "blocked_unknown_readiness_state"
        next_safe_action = "stop_and_fix_implementation_readiness"
        failures.append(f"unknown_readiness_decision:{readiness_decision}")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "planner_id": PLANNER_ID,
        "result": result,
        "target_family": impl.get("target_family"),
        "proposal_id": impl.get("proposal_id"),
        "source": impl.get("source"),
        "decision": decision,
        "readiness_decision": readiness_decision,
        "planning_status": planning_status,
        "next_safe_action": next_safe_action,
        "implementation_readiness_report": str(impl_path) if impl_path else None,
        "review_outcome_report": str(outcome_path) if outcome_path else None,
        "packet_report": str(packet_path) if packet_path else None,
        "plan_items": plan_items,
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "dry_run_only": True,
            "website_files_changed": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
            "implementation_gate_opened": False,
            "source_change_gate_opened": False,
            "deploy_gate_opened": False
        },
    }

    out_json = REPORT_DIR / f"learning-v2-controlled-implementation-planner-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-controlled-implementation-planner-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Controlled Implementation Planner",
        "",
        f"- result: `{result}`",
        f"- target_family: `{payload['target_family']}`",
        f"- proposal_id: `{payload['proposal_id']}`",
        f"- source: `{payload['source']}`",
        f"- decision: `{decision}`",
        f"- readiness_decision: `{readiness_decision}`",
        f"- planning_status: `{planning_status}`",
        f"- next_safe_action: `{next_safe_action}`",
        f"- implementation_gate_opened: `False`",
        f"- source_change_gate_opened: `False`",
        f"- deploy: `False`",
        "",
        "## Plan Items",
    ]
    lines += [f"- {x}" for x in plan_items] if plan_items else ["- none"]
    lines += ["", "## Failures"]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    lines += ["", "## Warnings"]
    lines += [f"- {x}" for x in warnings] if warnings else ["- none"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("controlled_implementation_planner =", result)
    print("target_family =", payload["target_family"])
    print("proposal_id =", payload["proposal_id"])
    print("source =", payload["source"])
    print("decision =", decision)
    print("readiness_decision =", readiness_decision)
    print("planning_status =", planning_status)
    print("next_safe_action =", next_safe_action)
    print("plan_item_count =", len(plan_items))
    print("implementation_gate_opened = false")
    print("source_change_gate_opened = false")
    print("failure_count =", len(failures))
    print("warning_count =", len(warnings))
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("website_files_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if failures:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
