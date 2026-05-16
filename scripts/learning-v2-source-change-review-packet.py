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

PACKET_ID = "learning-v2-source-change-review-packet-v0"

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

def policy_false(payload, key):
    return (payload.get("policy") or {}).get(key) is False

def main():
    failures = []
    warnings = []

    source_path, source_gate = latest_json("learning-v2-source-change-gate-*.json")
    planner_path, planner = latest_json("learning-v2-controlled-implementation-planner-*.json")
    agg_path, agg = latest_json("learning-v2-review-outcome-aggregator-*.json")

    if not source_path:
        failures.append("missing_source_change_gate_report")
    if source_gate.get("__load_error__"):
        failures.append(f"source_change_gate_load_error:{source_gate.get('__load_error__')}")
    if source_gate.get("result") != "ok":
        failures.append(f"source_change_gate_result_not_ok:{source_gate.get('result')}")

    if not planner_path:
        failures.append("missing_controlled_implementation_planner_report")
    if planner.get("__load_error__"):
        failures.append(f"planner_load_error:{planner.get('__load_error__')}")

    if not agg_path:
        failures.append("missing_review_outcome_aggregator_report")
    if agg.get("__load_error__"):
        failures.append(f"aggregator_load_error:{agg.get('__load_error__')}")

    for name, payload in [
        ("source_gate", source_gate),
        ("planner", planner),
        ("aggregator", agg),
    ]:
        for key in ["website_files_changed", "git_commit", "git_push", "deploy", "source_change_gate_opened"]:
            if (payload.get("policy") or {}).get(key) is not False:
                failures.append(f"{name}_policy_{key}_not_false:{(payload.get('policy') or {}).get(key)}")

    source_change_decision = source_gate.get("source_change_decision")
    stable_outcome = source_gate.get("stable_outcome")
    planning_status = source_gate.get("planning_status")
    plan_items = planner.get("plan_items") or []

    if source_change_decision != "source_change_review_ready_but_gate_closed":
        packet_status = "not_ready"
        next_safe_action = source_gate.get("next_safe_action") or "await_more_review_signal"
        review_items = []
    else:
        packet_status = "review_packet_ready"
        next_safe_action = "review_source_change_packet"
        review_items = [
            "Confirm stable_outcome is accept-derived.",
            "Review target files and intended diff scope.",
            "Review validation commands before any apply step.",
            "Confirm no deploy gate is opened.",
        ]

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "packet_id": PACKET_ID,
        "result": result,
        "target_family": source_gate.get("target_family"),
        "proposal_id": source_gate.get("proposal_id"),
        "stable_outcome": stable_outcome,
        "source_change_decision": source_change_decision,
        "planning_status": planning_status,
        "plan_item_count": len(plan_items),
        "packet_status": packet_status,
        "next_safe_action": next_safe_action,
        "review_items": review_items,
        "source_gate_report": str(source_path) if source_path else None,
        "planner_report": str(planner_path) if planner_path else None,
        "aggregator_report": str(agg_path) if agg_path else None,
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

    out_json = REPORT_DIR / f"learning-v2-source-change-review-packet-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-source-change-review-packet-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Source Change Review Packet",
        "",
        f"- result: `{result}`",
        f"- target_family: `{payload['target_family']}`",
        f"- proposal_id: `{payload['proposal_id']}`",
        f"- stable_outcome: `{stable_outcome}`",
        f"- source_change_decision: `{source_change_decision}`",
        f"- planning_status: `{planning_status}`",
        f"- plan_item_count: `{len(plan_items)}`",
        f"- packet_status: `{packet_status}`",
        f"- next_safe_action: `{next_safe_action}`",
        f"- source_change_gate_opened: `False`",
        f"- deploy: `False`",
        "",
        "## Review Items",
    ]
    lines += [f"- {x}" for x in review_items] if review_items else ["- none"]
    lines += ["", "## Failures"]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    lines += ["", "## Warnings"]
    lines += [f"- {x}" for x in warnings] if warnings else ["- none"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("source_change_review_packet =", result)
    print("target_family =", payload["target_family"])
    print("proposal_id =", payload["proposal_id"])
    print("stable_outcome =", stable_outcome)
    print("source_change_decision =", source_change_decision)
    print("planning_status =", planning_status)
    print("plan_item_count =", len(plan_items))
    print("packet_status =", packet_status)
    print("next_safe_action =", next_safe_action)
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
