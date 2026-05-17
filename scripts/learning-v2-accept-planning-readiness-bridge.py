#!/usr/bin/env python3
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

BRIDGE_ID = "learning-v2-accept-planning-readiness-bridge-v0"

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
    value = policy(payload, key)
    if value is not False:
        failures.append(f"{name}_policy_{key}_not_false:{value}")

def first_value(payload, *keys):
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None

def main():
    failures = []
    warnings = []

    agg_path, agg = latest_json("learning-v2-review-outcome-aggregator-*.json")
    readiness_path, readiness = latest_json("learning-v2-implementation-readiness-gate-*.json")
    planner_path, planner = latest_json("learning-v2-controlled-implementation-planner-*.json")
    source_gate_path, source_gate = latest_json("learning-v2-source-change-gate-*.json")
    accept_contract_path, accept_contract = latest_json("learning-v2-accept-transition-contract-auditor-*.json")
    chain_path, chain = latest_json("learning-v2-source-change-guard-chain-auditor-*.json")

    reports = [
        ("aggregator", agg_path, agg),
        ("readiness", readiness_path, readiness),
        ("planner", planner_path, planner),
        ("source_gate", source_gate_path, source_gate),
        ("accept_contract", accept_contract_path, accept_contract),
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

    stable_outcome = first_value(
        agg,
        "stable_outcome",
        "aggregated_outcome",
        "outcome",
    )
    if stable_outcome is None:
        stable_outcome = source_gate.get("stable_outcome")

    confidence = first_value(agg, "confidence", "stable_confidence")
    if confidence is None:
        confidence = source_gate.get("confidence")

    readiness_decision = first_value(
        readiness,
        "readiness_decision",
        "decision",
    )

    planner_status = planner.get("planning_status")
    planner_plan_count = len(planner.get("plan_items") or [])

    source_change_decision = source_gate.get("source_change_decision")
    source_change_gate_opened = (
        source_gate.get("source_change_gate_opened")
        if "source_change_gate_opened" in source_gate
        else (source_gate.get("policy") or {}).get("source_change_gate_opened")
    )

    accept_contract_status = accept_contract.get("audit_status")
    chain_status = chain.get("chain_status")

    fast_status_dependency_mode = os.environ.get("LEARNING_V2_BRIDGE_FAST_STATUS_MODE", "skip").strip().lower()

    if fast_status_dependency_mode == "call":
        fast = run_fast_status()
        fast_kv = fast["kv"]

        if fast["returncode"] != 0:
            failures.append(f"fast_status_returncode_not_zero:{fast['returncode']}")

        if fast_kv.get("learning_v2_fast_status") != "ok":
            failures.append(f"fast_status_not_ok:{fast_kv.get('learning_v2_fast_status')}")
        if fast_kv.get("deploy") != "false":
            failures.append(f"fast_status_deploy_not_false:{fast_kv.get('deploy')}")
    else:
        # Default is deliberately decoupled.
        # This prevents a report cycle:
        # fast-status -> bridge report -> bridge -> fast-status.
        fast = {"returncode": None, "stdout": "", "stderr": "", "kv": {}}
        fast_kv = {
            "learning_v2_fast_status": "not_called_by_bridge",
            "deploy": "not_called_by_bridge",
        }
        fast_status_dependency_mode = "skip"

    transition_contract = {
        "accept_may_open_planning_readiness": True,
        "accept_must_not_edit_website_files": True,
        "accept_must_not_open_source_change_gate_directly": True,
        "accept_must_not_deploy": True,
        "source_change_requires_controlled_plan_after_planning": True,
    }

    if stable_outcome == "accept":
        expected_bridge_status = "accept_planning_readiness_ready"
        planning_readiness_opened = True
        expected_readiness_decision = "implementation_readiness_ready_for_planning"
        expected_planner_status = "controlled_implementation_planning_ready"
        next_safe_action = "create_controlled_implementation_plan_without_source_change"

        if readiness_decision != expected_readiness_decision:
            failures.append(f"accept_readiness_decision_invalid:{readiness_decision}")
        if planner_status != expected_planner_status:
            failures.append(f"accept_planner_status_invalid:{planner_status}")
        if source_change_decision != "source_change_review_ready_but_gate_closed":
            failures.append(f"accept_source_change_decision_invalid:{source_change_decision}")
        if source_change_gate_opened is not False:
            failures.append(f"accept_source_change_gate_opened_not_false:{source_change_gate_opened}")

    else:
        expected_bridge_status = "pending_bridge_closed"
        planning_readiness_opened = False
        expected_readiness_decision = "implementation_readiness_waiting_for_review_signal"
        expected_planner_status = "not_ready_waiting_for_review_signal"
        next_safe_action = "await_accept_outcome"

        if stable_outcome != "pending":
            warnings.append(f"stable_outcome_not_pending_or_accept:{stable_outcome}")
        if planner_status != expected_planner_status:
            failures.append(f"pending_planner_status_invalid:{planner_status}")
        if planner_plan_count != 0:
            failures.append(f"pending_planner_plan_count_not_zero:{planner_plan_count}")
        if source_change_decision != "blocked_waiting_for_accept_outcome":
            failures.append(f"pending_source_change_decision_invalid:{source_change_decision}")
        if source_change_gate_opened is not False:
            failures.append(f"pending_source_change_gate_opened_not_false:{source_change_gate_opened}")
        if chain_status != "consistent_pending_block":
            failures.append(f"pending_chain_status_invalid:{chain_status}")

    if accept_contract_status != "accept_transition_contract_consistent":
        failures.append(f"accept_contract_status_invalid:{accept_contract_status}")

    result = "ok" if not failures else "blocked"
    bridge_status = expected_bridge_status if result == "ok" else "accept_planning_readiness_bridge_inconsistent"

    payload = {
        "generated_at": now_iso(),
        "bridge_id": BRIDGE_ID,
        "result": result,
        "bridge_status": bridge_status,
        "target_family": source_gate.get("target_family") or accept_contract.get("target_family"),
        "proposal_id": source_gate.get("proposal_id") or accept_contract.get("proposal_id"),
        "stable_outcome": stable_outcome,
        "confidence": confidence,
        "readiness_decision": readiness_decision,
        "planner_status": planner_status,
        "planner_plan_count": planner_plan_count,
        "planning_readiness_opened": planning_readiness_opened,
        "source_change_decision": source_change_decision,
        "source_change_gate_opened": False,
        "deploy": False,
        "next_safe_action": next_safe_action,
        "accept_contract_status": accept_contract_status,
        "chain_status": chain_status,
        "fast_status_dependency_mode": fast_status_dependency_mode,
        "fast_status_result": fast_kv.get("learning_v2_fast_status"),
        "fast_status_deploy": fast_kv.get("deploy"),
        "transition_contract": transition_contract,
        "reports": {
            "aggregator": str(agg_path) if agg_path else None,
            "readiness": str(readiness_path) if readiness_path else None,
            "planner": str(planner_path) if planner_path else None,
            "source_gate": str(source_gate_path) if source_gate_path else None,
            "accept_contract": str(accept_contract_path) if accept_contract_path else None,
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
            "implementation_gate_opened": planning_readiness_opened,
            "source_change_gate_opened": False,
            "deploy_gate_opened": False,
        },
    }

    out_json = REPORT_DIR / f"learning-v2-accept-planning-readiness-bridge-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-accept-planning-readiness-bridge-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Accept Planning Readiness Bridge",
        "",
        f"- result: `{result}`",
        f"- bridge_status: `{bridge_status}`",
        f"- target_family: `{payload['target_family']}`",
        f"- proposal_id: `{payload['proposal_id']}`",
        f"- stable_outcome: `{stable_outcome}`",
        f"- confidence: `{confidence}`",
        f"- readiness_decision: `{readiness_decision}`",
        f"- planner_status: `{planner_status}`",
        f"- planner_plan_count: `{planner_plan_count}`",
        f"- planning_readiness_opened: `{planning_readiness_opened}`",
        f"- source_change_decision: `{source_change_decision}`",
        f"- source_change_gate_opened: `False`",
        f"- deploy: `False`",
        f"- next_safe_action: `{next_safe_action}`",
        f"- accept_contract_status: `{accept_contract_status}`",
        f"- chain_status: `{chain_status}`",
        f"- fast_status_dependency_mode: `{fast_status_dependency_mode}`",
        f"- fast_status_result: `{fast_kv.get('learning_v2_fast_status')}`",
        f"- fast_status_deploy: `{fast_kv.get('deploy')}`",
        "",
        "## Failures",
    ]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    lines += ["", "## Warnings"]
    lines += [f"- {x}" for x in warnings] if warnings else ["- none"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("accept_planning_readiness_bridge =", result)
    print("bridge_status =", bridge_status)
    print("target_family =", payload["target_family"])
    print("proposal_id =", payload["proposal_id"])
    print("stable_outcome =", stable_outcome)
    print("confidence =", confidence)
    print("readiness_decision =", readiness_decision)
    print("planner_status =", planner_status)
    print("planner_plan_count =", planner_plan_count)
    print("planning_readiness_opened =", str(planning_readiness_opened).lower())
    print("source_change_decision =", source_change_decision)
    print("source_change_gate_opened = false")
    print("deploy = false")
    print("next_safe_action =", next_safe_action)
    print("accept_contract_status =", accept_contract_status)
    print("chain_status =", chain_status)
    print("fast_status_dependency_mode =", fast_status_dependency_mode)
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
