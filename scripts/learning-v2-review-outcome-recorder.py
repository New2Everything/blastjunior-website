#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

RECORDER_ID = "learning-v2-review-outcome-recorder-v0"

VALID_SOURCES = {"human", "auto", "policy", "simulation"}
VALID_DECISIONS = {
    "pending": "await_more_review_signal",
    "accept": "prepare_implementation_readiness_gate_without_opening_source_change",
    "reject": "close_or_rework_design_proposal",
    "revise": "prepare_design_revision_plan",
}

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=sorted(VALID_SOURCES), default="simulation")
    parser.add_argument("--decision", choices=sorted(VALID_DECISIONS.keys()), default="pending")
    parser.add_argument("--reviewer", default="learning-v2")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    failures = []
    warnings = []

    packet_path, packet = latest_json("learning-v2-human-design-review-packet-*.json")
    readiness_path, readiness = latest_json("learning-v2-design-review-implementation-readiness-*.json")

    if not packet_path:
        failures.append("missing_design_review_packet")
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

    gates = packet.get("gates") or {}
    packet_policy = packet.get("policy") or {}
    readiness_policy = readiness.get("policy") or {}

    for key in ["implementation_gate_opened", "source_change_gate_opened"]:
        if gates.get(key) is not False:
            failures.append(f"packet_gate_{key}_not_false:{gates.get(key)}")
        if packet_policy.get(key) is not False:
            failures.append(f"packet_policy_{key}_not_false:{packet_policy.get(key)}")
        if readiness_policy.get(key) is not False:
            failures.append(f"readiness_policy_{key}_not_false:{readiness_policy.get(key)}")

    for name, policy in [("packet", packet_policy), ("readiness", readiness_policy)]:
        for key in ["website_files_changed", "git_commit", "git_push", "deploy"]:
            if policy.get(key) is not False:
                failures.append(f"{name}_policy_{key}_not_false:{policy.get(key)}")

    # Important: even decision=accept is only a learning/review outcome.
    # It must not open source-change, implementation, push, or deploy gates.
    next_safe_action = VALID_DECISIONS[args.decision]

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "recorder_id": RECORDER_ID,
        "result": result,
        "source": args.source,
        "decision": args.decision,
        "reviewer": args.reviewer,
        "note": args.note,
        "target_family": packet.get("target_family"),
        "proposal_id": (packet.get("proposal") or {}).get("proposal_id"),
        "preferred_option": (packet.get("proposal") or {}).get("preferred_option"),
        "packet_report": str(packet_path) if packet_path else None,
        "readiness_report": str(readiness_path) if readiness_path else None,
        "next_safe_action": next_safe_action,
        "learning_positioning": "review_outcome_is_feedback_signal_not_permanent_human_gate",
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

    out_json = REPORT_DIR / f"learning-v2-review-outcome-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-review-outcome-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Review Outcome",
        "",
        f"- result: `{result}`",
        f"- source: `{args.source}`",
        f"- decision: `{args.decision}`",
        f"- target_family: `{payload['target_family']}`",
        f"- proposal_id: `{payload['proposal_id']}`",
        f"- preferred_option: `{payload['preferred_option']}`",
        f"- next_safe_action: `{next_safe_action}`",
        f"- learning_positioning: `{payload['learning_positioning']}`",
        f"- implementation_gate_opened: `False`",
        f"- source_change_gate_opened: `False`",
        f"- deploy: `False`",
        f"- note: {args.note}",
        "",
        "## Failures",
    ]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    lines += ["", "## Warnings"]
    lines += [f"- {x}" for x in warnings] if warnings else ["- none"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("review_outcome_recorder =", result)
    print("source =", args.source)
    print("decision =", args.decision)
    print("target_family =", payload["target_family"])
    print("proposal_id =", payload["proposal_id"])
    print("preferred_option =", payload["preferred_option"])
    print("next_safe_action =", next_safe_action)
    print("learning_positioning =", payload["learning_positioning"])
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
