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

SIMULATOR_ID = "learning-v2-accept-transition-simulator-v0"

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

def policy(payload, key):
    return (payload.get("policy") or {}).get(key)

def require_false(name, payload, key, failures):
    if policy(payload, key) is not False:
        failures.append(f"{name}_policy_{key}_not_false:{policy(payload, key)}")

def main():
    failures = []
    warnings = []

    agg_path, agg = latest_json("learning-v2-review-outcome-aggregator-*.json")
    readiness_path, readiness = latest_json("learning-v2-implementation-readiness-gate-*.json")
    planner_path, planner = latest_json("learning-v2-controlled-implementation-planner-*.json")
    gate_path, gate = latest_json("learning-v2-source-change-gate-*.json")
    packet_path, packet = latest_json("learning-v2-source-change-review-packet-*.json")
    packet_auditor_path, packet_auditor = latest_json("learning-v2-source-change-review-packet-auditor-*.json")
    chain_path, chain = latest_json("learning-v2-source-change-guard-chain-auditor-*.json")

    reports = [
        ("aggregator", agg_path, agg),
        ("readiness", readiness_path, readiness),
        ("planner", planner_path, planner),
        ("source_gate", gate_path, gate),
        ("review_packet", packet_path, packet),
        ("packet_auditor", packet_auditor_path, packet_auditor),
        ("guard_chain", chain_path, chain),
    ]

    for name, path, payload in reports:
        if not path:
            failures.append(f"missing_{name}_report")
        if payload.get("__load_error__"):
            failures.append(f"{name}_load_error:{payload.get('__load_error__')}")
        if payload.get("result") != "ok":
            failures.append(f"{name}_result_not_ok:{payload.get('result')}")

    for name, _, payload in reports:
        for key in ["website_files_changed", "git_commit", "git_push", "deploy"]:
            if key in (payload.get("policy") or {}):
                require_false(name, payload, key, failures)

    fast = run_fast_status()
    fast_kv = fast["kv"]

    if fast["returncode"] != 0:
        failures.append(f"fast_status_returncode_not_zero:{fast['returncode']}")

    current = {
        "stable_outcome": gate.get("stable_outcome"),
        "readiness_decision": readiness.get("readiness_decision") or readiness.get("decision"),
        "planner_status": planner.get("planning_status"),
        "planner_plan_count": len(planner.get("plan_items") or []),
        "source_change_decision": gate.get("source_change_decision"),
        "packet_status": packet.get("packet_status"),
        "packet_audit_status": packet_auditor.get("audit_status"),
        "chain_status": chain.get("chain_status"),
        "fast_status_result": fast_kv.get("learning_v2_fast_status"),
        "fast_status_deploy": fast_kv.get("deploy"),
    }

    if current["stable_outcome"] != "pending":
        warnings.append(f"current_stable_outcome_not_pending:{current['stable_outcome']}")

    expected_pending = {
        "planner_status": "not_ready_waiting_for_review_signal",
        "source_change_decision": "blocked_waiting_for_accept_outcome",
        "packet_status": "not_ready",
        "packet_audit_status": "consistent_pending_block",
        "chain_status": "consistent_pending_block",
        "fast_status_result": "ok",
        "fast_status_deploy": "false",
    }

    for key, expected in expected_pending.items():
        actual = current.get(key)
        if actual != expected:
            failures.append(f"current_pending_{key}_mismatch:{actual}!={expected}")

    simulated_accept = {
        "simulated_stable_outcome": "accept",
        "simulated_confidence": "sufficient_signal",
        "simulated_readiness_decision": "implementation_readiness_ready_for_planning",
        "simulated_planner_status": "controlled_implementation_planning_ready",
        "simulated_source_change_decision": "source_change_review_ready_but_gate_closed",
        "simulated_packet_status": "review_packet_ready",
        "simulated_chain_status": "consistent_review_ready_gate_closed",
        "simulated_source_change_gate_opened": False,
        "simulated_deploy": False,
        "simulated_website_files_changed": False,
    }

    acceptance_contract = [
        "accept signal may open implementation planning readiness",
        "accept signal must not directly edit website files",
        "accept signal must not directly open source-change gate",
        "accept signal must not deploy",
        "source-change still requires controlled plan and later gate",
        "fast-status must continue to report deploy=false",
    ]

    result = "ok" if not failures else "blocked"
    simulator_status = "accept_transition_contract_ready" if result == "ok" else "accept_transition_contract_blocked"

    payload = {
        "generated_at": now_iso(),
        "simulator_id": SIMULATOR_ID,
        "result": result,
        "simulator_status": simulator_status,
        "target_family": gate.get("target_family"),
        "proposal_id": gate.get("proposal_id"),
        "current": current,
        "simulated_accept": simulated_accept,
        "acceptance_contract": acceptance_contract,
        "reports": {
            "aggregator": str(agg_path) if agg_path else None,
            "readiness": str(readiness_path) if readiness_path else None,
            "planner": str(planner_path) if planner_path else None,
            "source_gate": str(gate_path) if gate_path else None,
            "review_packet": str(packet_path) if packet_path else None,
            "packet_auditor": str(packet_auditor_path) if packet_auditor_path else None,
            "guard_chain": str(chain_path) if chain_path else None,
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

    out_json = REPORT_DIR / f"learning-v2-accept-transition-simulator-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-accept-transition-simulator-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Accept Transition Simulator",
        "",
        f"- result: `{result}`",
        f"- simulator_status: `{simulator_status}`",
        f"- target_family: `{payload['target_family']}`",
        f"- proposal_id: `{payload['proposal_id']}`",
        f"- current_stable_outcome: `{current['stable_outcome']}`",
        f"- current_chain_status: `{current['chain_status']}`",
        f"- simulated_stable_outcome: `accept`",
        f"- simulated_readiness_decision: `{simulated_accept['simulated_readiness_decision']}`",
        f"- simulated_planner_status: `{simulated_accept['simulated_planner_status']}`",
        f"- simulated_source_change_decision: `{simulated_accept['simulated_source_change_decision']}`",
        f"- simulated_packet_status: `{simulated_accept['simulated_packet_status']}`",
        f"- simulated_chain_status: `{simulated_accept['simulated_chain_status']}`",
        f"- simulated_source_change_gate_opened: `False`",
        f"- simulated_deploy: `False`",
        "",
        "## Acceptance Contract",
    ]
    lines += [f"- {x}" for x in acceptance_contract]
    lines += ["", "## Failures"]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    lines += ["", "## Warnings"]
    lines += [f"- {x}" for x in warnings] if warnings else ["- none"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("accept_transition_simulator =", result)
    print("simulator_status =", simulator_status)
    print("target_family =", payload["target_family"])
    print("proposal_id =", payload["proposal_id"])
    print("current_stable_outcome =", current["stable_outcome"])
    print("current_chain_status =", current["chain_status"])
    print("simulated_stable_outcome = accept")
    print("simulated_readiness_decision =", simulated_accept["simulated_readiness_decision"])
    print("simulated_planner_status =", simulated_accept["simulated_planner_status"])
    print("simulated_source_change_decision =", simulated_accept["simulated_source_change_decision"])
    print("simulated_packet_status =", simulated_accept["simulated_packet_status"])
    print("simulated_chain_status =", simulated_accept["simulated_chain_status"])
    print("simulated_source_change_gate_opened = false")
    print("simulated_deploy = false")
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
