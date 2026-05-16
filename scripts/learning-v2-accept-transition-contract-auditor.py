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

AUDITOR_ID = "learning-v2-accept-transition-contract-auditor-v0"

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
    value = policy(payload, key)
    if value is not False:
        failures.append(f"{name}_policy_{key}_not_false:{value}")

def main():
    failures = []
    warnings = []

    sim_path, sim = latest_json("learning-v2-accept-transition-simulator-*.json")
    chain_path, chain = latest_json("learning-v2-source-change-guard-chain-auditor-*.json")
    gate_path, gate = latest_json("learning-v2-source-change-gate-*.json")

    reports = [
        ("accept_simulator", sim_path, sim),
        ("guard_chain", chain_path, chain),
        ("source_gate", gate_path, gate),
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
            "source_change_gate_opened",
            "deploy_gate_opened",
        ]:
            if key in (payload.get("policy") or {}):
                require_false(name, payload, key, failures)

    current = sim.get("current") or {}
    simulated = sim.get("simulated_accept") or {}

    current_stable_outcome = current.get("stable_outcome")
    current_chain_status = current.get("chain_status")
    simulator_status = sim.get("simulator_status")

    simulated_stable_outcome = simulated.get("simulated_stable_outcome")
    simulated_readiness_decision = simulated.get("simulated_readiness_decision")
    simulated_planner_status = simulated.get("simulated_planner_status")
    simulated_source_change_decision = simulated.get("simulated_source_change_decision")
    simulated_packet_status = simulated.get("simulated_packet_status")
    simulated_chain_status = simulated.get("simulated_chain_status")
    simulated_source_change_gate_opened = simulated.get("simulated_source_change_gate_opened")
    simulated_deploy = simulated.get("simulated_deploy")
    simulated_website_files_changed = simulated.get("simulated_website_files_changed")

    expected = {
        "simulator_status": "accept_transition_contract_ready",
        "current_stable_outcome": "pending",
        "current_chain_status": "consistent_pending_block",
        "simulated_stable_outcome": "accept",
        "simulated_readiness_decision": "implementation_readiness_ready_for_planning",
        "simulated_planner_status": "controlled_implementation_planning_ready",
        "simulated_source_change_decision": "source_change_review_ready_but_gate_closed",
        "simulated_packet_status": "review_packet_ready",
        "simulated_chain_status": "consistent_review_ready_gate_closed",
    }

    actual = {
        "simulator_status": simulator_status,
        "current_stable_outcome": current_stable_outcome,
        "current_chain_status": current_chain_status,
        "simulated_stable_outcome": simulated_stable_outcome,
        "simulated_readiness_decision": simulated_readiness_decision,
        "simulated_planner_status": simulated_planner_status,
        "simulated_source_change_decision": simulated_source_change_decision,
        "simulated_packet_status": simulated_packet_status,
        "simulated_chain_status": simulated_chain_status,
    }

    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if actual_value != expected_value:
            failures.append(f"{key}_mismatch:{actual_value}!={expected_value}")

    if simulated_source_change_gate_opened is not False:
        failures.append(f"simulated_source_change_gate_opened_not_false:{simulated_source_change_gate_opened}")
    if simulated_deploy is not False:
        failures.append(f"simulated_deploy_not_false:{simulated_deploy}")
    if simulated_website_files_changed is not False:
        failures.append(f"simulated_website_files_changed_not_false:{simulated_website_files_changed}")

    if chain.get("chain_status") != "consistent_pending_block":
        failures.append(f"current_guard_chain_status_invalid:{chain.get('chain_status')}")
    if gate.get("source_change_decision") != "blocked_waiting_for_accept_outcome":
        failures.append(f"current_source_change_decision_invalid:{gate.get('source_change_decision')}")

    fast = run_fast_status()
    fast_kv = fast["kv"]

    if fast["returncode"] != 0:
        failures.append(f"fast_status_returncode_not_zero:{fast['returncode']}")

    fast_expected = {
        "learning_v2_fast_status": "ok",
        "accept_transition_simulator": "ok",
        "accept_transition_simulator_status": "accept_transition_contract_ready",
        "accept_simulated_source_change_gate_opened": "false",
        "accept_simulated_deploy": "false",
        "source_change_chain_status": "consistent_pending_block",
        "deploy": "false",
        "failure_count": "0",
    }

    for key, expected_value in fast_expected.items():
        actual_value = fast_kv.get(key)
        if actual_value != expected_value:
            failures.append(f"fast_status_{key}_mismatch:{actual_value}!={expected_value}")

    result = "ok" if not failures else "blocked"
    audit_status = "accept_transition_contract_consistent" if result == "ok" else "accept_transition_contract_inconsistent"

    payload = {
        "generated_at": now_iso(),
        "auditor_id": AUDITOR_ID,
        "result": result,
        "audit_status": audit_status,
        "target_family": sim.get("target_family"),
        "proposal_id": sim.get("proposal_id"),
        "current_stable_outcome": current_stable_outcome,
        "current_chain_status": current_chain_status,
        "simulator_status": simulator_status,
        "simulated_stable_outcome": simulated_stable_outcome,
        "simulated_planner_status": simulated_planner_status,
        "simulated_source_change_gate_opened": simulated_source_change_gate_opened,
        "simulated_deploy": simulated_deploy,
        "fast_status_result": fast_kv.get("learning_v2_fast_status"),
        "fast_status_deploy": fast_kv.get("deploy"),
        "reports": {
            "accept_simulator": str(sim_path) if sim_path else None,
            "guard_chain": str(chain_path) if chain_path else None,
            "source_gate": str(gate_path) if gate_path else None,
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

    out_json = REPORT_DIR / f"learning-v2-accept-transition-contract-auditor-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-accept-transition-contract-auditor-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Accept Transition Contract Auditor",
        "",
        f"- result: `{result}`",
        f"- audit_status: `{audit_status}`",
        f"- target_family: `{payload['target_family']}`",
        f"- proposal_id: `{payload['proposal_id']}`",
        f"- current_stable_outcome: `{current_stable_outcome}`",
        f"- current_chain_status: `{current_chain_status}`",
        f"- simulator_status: `{simulator_status}`",
        f"- simulated_stable_outcome: `{simulated_stable_outcome}`",
        f"- simulated_planner_status: `{simulated_planner_status}`",
        f"- simulated_source_change_gate_opened: `{simulated_source_change_gate_opened}`",
        f"- simulated_deploy: `{simulated_deploy}`",
        f"- fast_status_result: `{fast_kv.get('learning_v2_fast_status')}`",
        f"- fast_status_deploy: `{fast_kv.get('deploy')}`",
        "",
        "## Failures",
    ]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    lines += ["", "## Warnings"]
    lines += [f"- {x}" for x in warnings] if warnings else ["- none"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("accept_transition_contract_auditor =", result)
    print("audit_status =", audit_status)
    print("target_family =", payload["target_family"])
    print("proposal_id =", payload["proposal_id"])
    print("current_stable_outcome =", current_stable_outcome)
    print("current_chain_status =", current_chain_status)
    print("simulator_status =", simulator_status)
    print("simulated_stable_outcome =", simulated_stable_outcome)
    print("simulated_planner_status =", simulated_planner_status)
    print("simulated_source_change_gate_opened =", str(simulated_source_change_gate_opened).lower())
    print("simulated_deploy =", str(simulated_deploy).lower())
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
