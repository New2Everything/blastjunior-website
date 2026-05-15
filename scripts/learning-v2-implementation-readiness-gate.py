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

GATE_ID = "learning-v2-implementation-readiness-gate-v0"

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

def policy_value(payload, key):
    return (payload.get("policy") or {}).get(key)

def main():
    failures = []
    warnings = []

    outcome_path, outcome = latest_json("learning-v2-review-outcome-*.json")
    packet_path, packet = latest_json("learning-v2-human-design-review-packet-*.json")
    readiness_path, readiness = latest_json("learning-v2-design-review-implementation-readiness-*.json")

    if not outcome_path:
        failures.append("missing_review_outcome_report")
    if outcome.get("__load_error__"):
        failures.append(f"review_outcome_load_error:{outcome.get('__load_error__')}")
    if outcome.get("result") != "ok":
        failures.append(f"review_outcome_result_not_ok:{outcome.get('result')}")

    if not packet_path:
        failures.append("missing_human_design_review_packet")
    if packet.get("__load_error__"):
        failures.append(f"packet_load_error:{packet.get('__load_error__')}")
    if packet.get("result") != "ok":
        failures.append(f"packet_result_not_ok:{packet.get('result')}")

    if not readiness_path:
        failures.append("missing_design_review_readiness")
    if readiness.get("__load_error__"):
        failures.append(f"readiness_load_error:{readiness.get('__load_error__')}")
    if readiness.get("result") != "ok":
        failures.append(f"readiness_result_not_ok:{readiness.get('result')}")

    for name, payload in [
        ("outcome", outcome),
        ("packet", packet),
        ("readiness", readiness),
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

    decision = outcome.get("decision")
    source = outcome.get("source")

    if decision == "accept":
        readiness_decision = "implementation_planning_ready_source_change_closed"
        next_safe_action = "prepare_controlled_implementation_plan"
    elif decision == "pending":
        readiness_decision = "implementation_readiness_waiting_for_review_signal"
        next_safe_action = "await_more_review_signal"
    elif decision == "revise":
        readiness_decision = "implementation_readiness_blocked_revision_needed"
        next_safe_action = "prepare_design_revision_plan"
    elif decision == "reject":
        readiness_decision = "implementation_readiness_blocked_rejected"
        next_safe_action = "close_or_rework_design_proposal"
    else:
        readiness_decision = "implementation_readiness_blocked_unknown_decision"
        next_safe_action = "stop_and_fix_review_outcome"
        failures.append(f"unknown_review_decision:{decision}")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "gate_id": GATE_ID,
        "result": result,
        "target_family": outcome.get("target_family"),
        "proposal_id": outcome.get("proposal_id"),
        "preferred_option": outcome.get("preferred_option"),
        "review_outcome_report": str(outcome_path) if outcome_path else None,
        "packet_report": str(packet_path) if packet_path else None,
        "readiness_report": str(readiness_path) if readiness_path else None,
        "source": source,
        "decision": decision,
        "readiness_decision": readiness_decision,
        "next_safe_action": next_safe_action,
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

    out_json = REPORT_DIR / f"learning-v2-implementation-readiness-gate-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-implementation-readiness-gate-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Implementation Readiness Gate",
        "",
        f"- result: `{result}`",
        f"- target_family: `{payload['target_family']}`",
        f"- proposal_id: `{payload['proposal_id']}`",
        f"- source: `{source}`",
        f"- decision: `{decision}`",
        f"- readiness_decision: `{readiness_decision}`",
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

    print("implementation_readiness_gate =", result)
    print("target_family =", payload["target_family"])
    print("proposal_id =", payload["proposal_id"])
    print("source =", source)
    print("decision =", decision)
    print("readiness_decision =", readiness_decision)
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
