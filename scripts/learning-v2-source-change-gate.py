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

GATE_ID = "learning-v2-source-change-gate-v0"

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

def require_policy_false(name, payload, failures):
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

def main():
    failures = []
    warnings = []

    agg_path, agg = latest_json("learning-v2-review-outcome-aggregator-*.json")
    ready_path, ready = latest_json("learning-v2-implementation-readiness-gate-*.json")
    planner_path, planner = latest_json("learning-v2-controlled-implementation-planner-*.json")

    if not agg_path:
        failures.append("missing_review_outcome_aggregator")
    if agg.get("__load_error__"):
        failures.append(f"aggregator_load_error:{agg.get('__load_error__')}")
    if agg.get("result") != "ok":
        failures.append(f"aggregator_result_not_ok:{agg.get('result')}")

    if not ready_path:
        failures.append("missing_implementation_readiness_gate")
    if ready.get("__load_error__"):
        failures.append(f"readiness_load_error:{ready.get('__load_error__')}")
    if ready.get("result") != "ok":
        failures.append(f"readiness_result_not_ok:{ready.get('result')}")

    if not planner_path:
        failures.append("missing_controlled_implementation_planner")
    if planner.get("__load_error__"):
        failures.append(f"planner_load_error:{planner.get('__load_error__')}")
    if planner.get("result") != "ok":
        failures.append(f"planner_result_not_ok:{planner.get('result')}")

    for name, payload in [
        ("aggregator", agg),
        ("readiness", ready),
        ("planner", planner),
    ]:
        require_policy_false(name, payload, failures)

    stable_outcome = agg.get("stable_outcome")
    confidence = agg.get("confidence")
    readiness_decision = ready.get("readiness_decision")
    planning_status = planner.get("planning_status")
    plan_items = planner.get("plan_items") or []

    if stable_outcome != "accept":
        source_change_decision = "blocked_waiting_for_accept_outcome"
        next_safe_action = "await_more_review_signal"
    elif readiness_decision != "implementation_planning_ready_source_change_closed":
        source_change_decision = "blocked_implementation_readiness_not_ready"
        next_safe_action = "fix_or_rerun_implementation_readiness"
    elif planning_status != "implementation_plan_ready_dry_run_only":
        source_change_decision = "blocked_controlled_implementation_plan_not_ready"
        next_safe_action = "prepare_controlled_implementation_plan"
    elif not plan_items:
        source_change_decision = "blocked_missing_plan_items"
        next_safe_action = "prepare_controlled_implementation_plan"
    else:
        source_change_decision = "source_change_review_ready_but_gate_closed"
        next_safe_action = "prepare_source_change_review_packet"

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "gate_id": GATE_ID,
        "result": result,
        "target_family": agg.get("target_family") or ready.get("target_family") or planner.get("target_family"),
        "proposal_id": agg.get("proposal_id") or ready.get("proposal_id") or planner.get("proposal_id"),
        "stable_outcome": stable_outcome,
        "confidence": confidence,
        "readiness_decision": readiness_decision,
        "planning_status": planning_status,
        "plan_item_count": len(plan_items),
        "source_change_decision": source_change_decision,
        "next_safe_action": next_safe_action,
        "aggregator_report": str(agg_path) if agg_path else None,
        "readiness_report": str(ready_path) if ready_path else None,
        "planner_report": str(planner_path) if planner_path else None,
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

    out_json = REPORT_DIR / f"learning-v2-source-change-gate-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-source-change-gate-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Source Change Gate",
        "",
        f"- result: `{result}`",
        f"- target_family: `{payload['target_family']}`",
        f"- proposal_id: `{payload['proposal_id']}`",
        f"- stable_outcome: `{stable_outcome}`",
        f"- confidence: `{confidence}`",
        f"- readiness_decision: `{readiness_decision}`",
        f"- planning_status: `{planning_status}`",
        f"- plan_item_count: `{len(plan_items)}`",
        f"- source_change_decision: `{source_change_decision}`",
        f"- next_safe_action: `{next_safe_action}`",
        f"- implementation_gate_opened: `False`",
        f"- source_change_gate_opened: `False`",
        f"- deploy: `False`",
        "",
        "## Failures",
    ]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    lines += ["", "## Warnings"]
    lines += [f"- {x}" for x in warnings] if warnings else ["- none"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("source_change_gate =", result)
    print("target_family =", payload["target_family"])
    print("proposal_id =", payload["proposal_id"])
    print("stable_outcome =", stable_outcome)
    print("confidence =", confidence)
    print("readiness_decision =", readiness_decision)
    print("planning_status =", planning_status)
    print("plan_item_count =", len(plan_items))
    print("source_change_decision =", source_change_decision)
    print("next_safe_action =", next_safe_action)
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
