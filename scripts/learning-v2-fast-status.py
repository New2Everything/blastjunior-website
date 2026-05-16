#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
REPORT_DIR = WORKSPACE / "learning-v2" / "reports"

STATUS_ID = "learning-v2-fast-status-v0"

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

def git_status_line():
    p = subprocess.run(
        ["git", "status", "-sb"],
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    first = (p.stdout or "").splitlines()[0] if p.stdout else "git_status_unavailable"
    return first

def latest_commit_line():
    p = subprocess.run(
        ["git", "log", "--oneline", "-1", "--decorate"],
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return (p.stdout or "").strip() or "latest_commit_unavailable"

def boolish_false(v):
    return v is False or str(v).lower() == "false"

def deep_find(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj.get(key)
        for value in obj.values():
            found = deep_find(value, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = deep_find(item, key)
            if found is not None:
                return found
    return None

def truthy(v):
    return v is True or str(v).lower() == "true"

def agent_status_value(agent):
    for key in ["learning_v2_agent_status", "agent_status", "result", "status"]:
        value = deep_find(agent, key)
        if value in {"ok", "blocked"}:
            return value

    health_ok = deep_find(agent, "learning_v2_health_ok")
    can_continue = deep_find(agent, "can_continue_system_build")
    tamper_ok = deep_find(agent, "tamper_guard_ok")

    if truthy(health_ok) and truthy(can_continue):
        return "ok"
    if health_ok is False or str(health_ok).lower() == "false":
        return "blocked"

    headline = str(deep_find(agent, "headline") or "")
    if "本体健康" in headline or "可以继续系统建设" in headline:
        return "ok"
    if "不应继续推进" in headline or "blocked" in headline.lower():
        return "blocked"

    return "unknown"

def main():
    failures = []

    agg_path, agg = latest_json("learning-v2-review-outcome-aggregator-*.json")
    ready_path, ready = latest_json("learning-v2-implementation-readiness-gate-*.json")
    planner_path, planner = latest_json("learning-v2-controlled-implementation-planner-*.json")
    source_path, source_gate = latest_json("learning-v2-source-change-gate-*.json")
    packet_path, review_packet = latest_json("learning-v2-source-change-review-packet-*.json")
    integrity_path, integrity = latest_json("system-integrity-*.json")
    agent_path, agent = latest_json("learning-v2-agent-status-*.json")

    checks = [
        ("review_outcome_aggregator", agg),
        ("implementation_readiness_gate", ready),
        ("controlled_implementation_planner", planner),
        ("source_change_gate", source_gate),
        ("source_change_review_packet", review_packet),
        ("system_integrity", integrity),
        ("learning_v2_agent_status", agent),
    ]

    for name, data in checks:
        if not data:
            failures.append(f"missing_{name}_report")
        elif data.get("__load_error__"):
            failures.append(f"{name}_load_error:{data.get('__load_error__')}")

    deploy_values = []
    for data in [agg, ready, planner, source_gate, review_packet, integrity, agent]:
        policy = data.get("policy") or {}
        if "deploy" in policy:
            deploy_values.append(policy.get("deploy"))
        elif "deploy" in data:
            deploy_values.append(data.get("deploy"))

    deploy_ok = all(boolish_false(v) for v in deploy_values) if deploy_values else True

    integrity_value = integrity.get("result") or integrity.get("system_integrity")
    agent_value = agent_status_value(agent)

    if not deploy_ok:
        failures.append(f"deploy_not_false:{deploy_values}")
    if integrity_value != "ok":
        failures.append(f"system_integrity_not_ok:{integrity_value}")
    source_gate_result = source_gate.get("result")
    source_change_decision = source_gate.get("source_change_decision")
    source_change_gate_opened = (source_gate.get("policy") or {}).get("source_change_gate_opened")

    review_packet_result = review_packet.get("result")
    packet_status = review_packet.get("packet_status")
    packet_next_safe_action = review_packet.get("next_safe_action")
    packet_source_change_gate_opened = (review_packet.get("policy") or {}).get("source_change_gate_opened")

    if agent_value != "ok":
        failures.append(f"agent_status_not_ok:{agent_value}")
    if source_gate_result != "ok":
        failures.append(f"source_change_gate_not_ok:{source_gate_result}")
    if source_change_gate_opened is not False:
        failures.append(f"source_change_gate_opened_not_false:{source_change_gate_opened}")
    if review_packet_result != "ok":
        failures.append(f"source_change_review_packet_not_ok:{review_packet_result}")
    if packet_source_change_gate_opened is not False:
        failures.append(f"source_change_review_packet_gate_opened_not_false:{packet_source_change_gate_opened}")

    result = "ok" if not failures else "blocked"

    print("learning_v2_fast_status =", result)
    print("status_id =", STATUS_ID)
    print("git =", git_status_line())
    print("latest_commit =", latest_commit_line())
    print("aggregator_result =", agg.get("result"))
    print("stable_outcome =", agg.get("stable_outcome"))
    print("confidence =", agg.get("confidence"))
    print("readiness_result =", ready.get("result"))
    print("readiness_source =", ready.get("source"))
    print("readiness_decision =", ready.get("decision"))
    print("readiness_next_safe_action =", ready.get("next_safe_action"))
    print("planner_result =", planner.get("result"))
    print("planning_status =", planner.get("planning_status"))
    print("plan_item_count =", len(planner.get("plan_items") or []))
    print("source_change_gate =", source_gate_result)
    print("source_change_decision =", source_change_decision)
    print("source_change_gate_opened =", str(source_change_gate_opened).lower())
    print("source_change_review_packet =", review_packet_result)
    print("source_change_packet_status =", packet_status)
    print("source_change_packet_next_safe_action =", packet_next_safe_action)
    print("source_change_packet_gate_opened =", str(packet_source_change_gate_opened).lower())
    print("system_integrity =", integrity_value)
    print("agent_status =", agent_value)
    print("deploy = false" if deploy_ok else f"deploy_values = {deploy_values}")
    print("failure_count =", len(failures))
    if failures:
        print("failures =", failures)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
