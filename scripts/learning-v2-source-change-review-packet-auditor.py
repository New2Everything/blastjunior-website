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

AUDITOR_ID = "learning-v2-source-change-review-packet-auditor-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def latest_json(pattern):
    files = sorted(REPORT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)

    if pattern == "learning-v2-source-change-review-packet-*.json":
        files = [
            p for p in files
            if not p.name.startswith("learning-v2-source-change-review-packet-auditor-")
        ]

    if not files:
        return None, {}

    p = files[0]
    try:
        return p, json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return p, {"__load_error__": str(e)}

def policy_value(payload, key):
    return (payload.get("policy") or {}).get(key)

def require_false(name, payload, key, failures):
    if policy_value(payload, key) is not False:
        failures.append(f"{name}_policy_{key}_not_false:{policy_value(payload, key)}")

def main():
    failures = []
    warnings = []

    gate_path, gate = latest_json("learning-v2-source-change-gate-*.json")
    packet_path, packet = latest_json("learning-v2-source-change-review-packet-*.json")

    if not gate_path:
        failures.append("missing_source_change_gate_report")
    if not packet_path:
        failures.append("missing_source_change_review_packet_report")

    if gate.get("__load_error__"):
        failures.append(f"source_change_gate_load_error:{gate.get('__load_error__')}")
    if packet.get("__load_error__"):
        failures.append(f"source_change_review_packet_load_error:{packet.get('__load_error__')}")

    if gate.get("result") != "ok":
        failures.append(f"source_change_gate_result_not_ok:{gate.get('result')}")
    if packet.get("result") != "ok":
        failures.append(f"source_change_review_packet_result_not_ok:{packet.get('result')}")

    comparable_keys = [
        "target_family",
        "proposal_id",
        "stable_outcome",
        "source_change_decision",
        "planning_status",
        "plan_item_count",
    ]

    for key in comparable_keys:
        if gate.get(key) != packet.get(key):
            failures.append(f"gate_packet_{key}_mismatch:{gate.get(key)}!={packet.get(key)}")

    for name, payload in [
        ("gate", gate),
        ("packet", packet),
    ]:
        for key in [
            "website_files_changed",
            "git_commit",
            "git_push",
            "deploy",
            "source_change_gate_opened",
        ]:
            require_false(name, payload, key, failures)

    stable_outcome = gate.get("stable_outcome")
    source_change_decision = gate.get("source_change_decision")
    gate_next_safe_action = gate.get("next_safe_action")
    packet_status = packet.get("packet_status")
    packet_next_safe_action = packet.get("next_safe_action")

    if stable_outcome != "accept":
        expected_packet_status = "not_ready"
        expected_audit_status = "consistent_pending_block"
        if packet_status != expected_packet_status:
            failures.append(f"pending_packet_status_not_not_ready:{packet_status}")
        if packet_next_safe_action != gate_next_safe_action:
            failures.append(f"packet_next_safe_action_mismatch:{packet_next_safe_action}!={gate_next_safe_action}")
    elif source_change_decision == "source_change_review_ready_but_gate_closed":
        expected_packet_status = "review_packet_ready"
        expected_audit_status = "consistent_review_ready_gate_closed"
        if packet_status != expected_packet_status:
            failures.append(f"accept_packet_status_not_review_ready:{packet_status}")
        if policy_value(packet, "source_change_gate_opened") is not False:
            failures.append("packet_implies_source_change_gate_opened")
    else:
        expected_packet_status = "not_ready"
        expected_audit_status = "consistent_accept_but_gate_not_ready"
        if packet_status != expected_packet_status:
            failures.append(f"gate_not_ready_packet_status_invalid:{packet_status}")

    if packet_status == "review_packet_ready" and stable_outcome != "accept":
        failures.append("review_packet_ready_without_accept_outcome")

    result = "ok" if not failures else "blocked"
    audit_status = expected_audit_status if result == "ok" else "inconsistent"

    payload = {
        "generated_at": now_iso(),
        "auditor_id": AUDITOR_ID,
        "result": result,
        "audit_status": audit_status,
        "target_family": gate.get("target_family"),
        "proposal_id": gate.get("proposal_id"),
        "stable_outcome": stable_outcome,
        "source_change_decision": source_change_decision,
        "packet_status": packet_status,
        "gate_next_safe_action": gate_next_safe_action,
        "packet_next_safe_action": packet_next_safe_action,
        "source_change_gate_opened": policy_value(packet, "source_change_gate_opened"),
        "gate_report": str(gate_path) if gate_path else None,
        "packet_report": str(packet_path) if packet_path else None,
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

    out_json = REPORT_DIR / f"learning-v2-source-change-review-packet-auditor-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-source-change-review-packet-auditor-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Source Change Review Packet Auditor",
        "",
        f"- result: `{result}`",
        f"- audit_status: `{audit_status}`",
        f"- target_family: `{payload['target_family']}`",
        f"- proposal_id: `{payload['proposal_id']}`",
        f"- stable_outcome: `{stable_outcome}`",
        f"- source_change_decision: `{source_change_decision}`",
        f"- packet_status: `{packet_status}`",
        f"- gate_next_safe_action: `{gate_next_safe_action}`",
        f"- packet_next_safe_action: `{packet_next_safe_action}`",
        f"- source_change_gate_opened: `{policy_value(packet, 'source_change_gate_opened')}`",
        f"- deploy: `False`",
        "",
        "## Failures",
    ]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    lines += ["", "## Warnings"]
    lines += [f"- {x}" for x in warnings] if warnings else ["- none"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("source_change_review_packet_auditor =", result)
    print("audit_status =", audit_status)
    print("target_family =", payload["target_family"])
    print("proposal_id =", payload["proposal_id"])
    print("stable_outcome =", stable_outcome)
    print("source_change_decision =", source_change_decision)
    print("packet_status =", packet_status)
    print("gate_next_safe_action =", gate_next_safe_action)
    print("packet_next_safe_action =", packet_next_safe_action)
    print("source_change_gate_opened =", str(policy_value(packet, "source_change_gate_opened")).lower())
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
