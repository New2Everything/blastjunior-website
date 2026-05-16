#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

AUDITOR_ID = "learning-v2-source-change-guard-chain-auditor-v0"

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

def policy(payload, key):
    return (payload.get("policy") or {}).get(key)

def require_false(name, payload, key, failures):
    if policy(payload, key) is not False:
        failures.append(f"{name}_policy_{key}_not_false:{policy(payload, key)}")

def parse_kv(text):
    out = {}
    for line in text.splitlines():
        if " = " in line:
            k, v = line.split(" = ", 1)
            out[k.strip()] = v.strip()
    return out

def run_fast_status():
    p = subprocess.run(
        ["python3", "scripts/learning-v2-fast-status.py"],
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "returncode": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
        "kv": parse_kv(p.stdout or ""),
    }

def main():
    failures = []
    warnings = []

    readiness_path, readiness = latest_json("learning-v2-implementation-readiness-gate-*.json")
    planner_path, planner = latest_json("learning-v2-controlled-implementation-planner-*.json")
    gate_path, gate = latest_json("learning-v2-source-change-gate-*.json")
    packet_path, packet = latest_json("learning-v2-source-change-review-packet-*.json")
    auditor_path, packet_auditor = latest_json("learning-v2-source-change-review-packet-auditor-*.json")

    reports = [
        ("readiness", readiness_path, readiness),
        ("planner", planner_path, planner),
        ("source_gate", gate_path, gate),
        ("review_packet", packet_path, packet),
        ("packet_auditor", auditor_path, packet_auditor),
    ]

    for name, path, payload in reports:
        if not path:
            failures.append(f"missing_{name}_report")
        if payload.get("__load_error__"):
            failures.append(f"{name}_load_error:{payload.get('__load_error__')}")
        if payload.get("result") != "ok":
            failures.append(f"{name}_result_not_ok:{payload.get('result')}")

    for name, _, payload in reports:
        for key in [
            "website_files_changed",
            "git_commit",
            "git_push",
            "deploy",
        ]:
            require_false(name, payload, key, failures)

        for key in [
            "implementation_gate_opened",
            "source_change_gate_opened",
            "deploy_gate_opened",
        ]:
            if key in (payload.get("policy") or {}):
                require_false(name, payload, key, failures)

    stable_outcome = gate.get("stable_outcome")
    target_family = gate.get("target_family")
    proposal_id = gate.get("proposal_id")

    comparable_keys = ["target_family", "proposal_id", "stable_outcome"]
    for key in comparable_keys:
        values = {
            "source_gate": gate.get(key),
            "review_packet": packet.get(key),
            "packet_auditor": packet_auditor.get(key),
        }
        if len(set(values.values())) != 1:
            failures.append(f"{key}_mismatch:{values}")

    readiness_decision = readiness.get("readiness_decision") or readiness.get("decision")
    planner_status = planner.get("planning_status")
    planner_plan_count = len(planner.get("plan_items") or [])

    source_change_decision = gate.get("source_change_decision")
    packet_status = packet.get("packet_status")
    audit_status = packet_auditor.get("audit_status")

    if stable_outcome != "accept":
        expected_chain_status = "consistent_pending_block"

        if source_change_decision != "blocked_waiting_for_accept_outcome":
            failures.append(f"pending_source_change_decision_invalid:{source_change_decision}")
        if packet_status != "not_ready":
            failures.append(f"pending_packet_status_invalid:{packet_status}")
        if audit_status != "consistent_pending_block":
            failures.append(f"pending_audit_status_invalid:{audit_status}")
        if planner_status != "not_ready_waiting_for_review_signal":
            failures.append(f"pending_planner_status_invalid:{planner_status}")
        if planner_plan_count != 0:
            failures.append(f"pending_planner_plan_count_not_zero:{planner_plan_count}")

    elif source_change_decision == "source_change_review_ready_but_gate_closed":
        expected_chain_status = "consistent_review_ready_gate_closed"

        if packet_status != "review_packet_ready":
            failures.append(f"accept_packet_status_invalid:{packet_status}")
        if audit_status != "consistent_review_ready_gate_closed":
            failures.append(f"accept_audit_status_invalid:{audit_status}")
    else:
        expected_chain_status = "consistent_accept_but_gate_not_ready"

        if packet_status != "not_ready":
            failures.append(f"accept_gate_not_ready_packet_status_invalid:{packet_status}")

    fast = run_fast_status()
    fast_kv = fast["kv"]

    if fast["returncode"] != 0:
        failures.append(f"fast_status_returncode_not_zero:{fast['returncode']}")

    expected_fast = {
        "learning_v2_fast_status": "ok",
        "source_change_gate": "ok",
        "source_change_review_packet": "ok",
        "source_change_review_packet_auditor": "ok",
        "source_change_packet_status": packet_status,
        "source_change_audit_status": audit_status,
        "source_change_auditor_gate_opened": "false",
        "deploy": "false",
        "failure_count": "0",
    }

    for key, expected in expected_fast.items():
        actual = fast_kv.get(key)
        if actual != expected:
            failures.append(f"fast_status_{key}_mismatch:{actual}!={expected}")

    result = "ok" if not failures else "blocked"
    chain_status = expected_chain_status if result == "ok" else "inconsistent"

    payload = {
        "generated_at": now_iso(),
        "auditor_id": AUDITOR_ID,
        "result": result,
        "chain_status": chain_status,
        "target_family": target_family,
        "proposal_id": proposal_id,
        "stable_outcome": stable_outcome,
        "readiness_decision": readiness_decision,
        "planner_status": planner_status,
        "planner_plan_count": planner_plan_count,
        "source_change_decision": source_change_decision,
        "packet_status": packet_status,
        "audit_status": audit_status,
        "fast_status_result": fast_kv.get("learning_v2_fast_status"),
        "fast_status_deploy": fast_kv.get("deploy"),
        "reports": {
            "readiness": str(readiness_path) if readiness_path else None,
            "planner": str(planner_path) if planner_path else None,
            "source_gate": str(gate_path) if gate_path else None,
            "review_packet": str(packet_path) if packet_path else None,
            "packet_auditor": str(auditor_path) if auditor_path else None,
        },
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

    out_json = REPORT_DIR / f"learning-v2-source-change-guard-chain-auditor-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-source-change-guard-chain-auditor-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Source Change Guard Chain Auditor",
        "",
        f"- result: `{result}`",
        f"- chain_status: `{chain_status}`",
        f"- target_family: `{target_family}`",
        f"- proposal_id: `{proposal_id}`",
        f"- stable_outcome: `{stable_outcome}`",
        f"- readiness_decision: `{readiness_decision}`",
        f"- planner_status: `{planner_status}`",
        f"- planner_plan_count: `{planner_plan_count}`",
        f"- source_change_decision: `{source_change_decision}`",
        f"- packet_status: `{packet_status}`",
        f"- audit_status: `{audit_status}`",
        f"- fast_status_result: `{fast_kv.get('learning_v2_fast_status')}`",
        f"- fast_status_deploy: `{fast_kv.get('deploy')}`",
        f"- deploy: `False`",
        "",
        "## Failures",
    ]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    lines += ["", "## Warnings"]
    lines += [f"- {x}" for x in warnings] if warnings else ["- none"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("source_change_guard_chain_auditor =", result)
    print("chain_status =", chain_status)
    print("target_family =", target_family)
    print("proposal_id =", proposal_id)
    print("stable_outcome =", stable_outcome)
    print("readiness_decision =", readiness_decision)
    print("planner_status =", planner_status)
    print("planner_plan_count =", planner_plan_count)
    print("source_change_decision =", source_change_decision)
    print("packet_status =", packet_status)
    print("audit_status =", audit_status)
    print("fast_status_result =", fast_kv.get("learning_v2_fast_status"))
    print("fast_status_deploy =", fast_kv.get("deploy"))
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
