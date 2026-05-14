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

READINESS_ID = "learning-v2-design-review-implementation-readiness-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def parse_kv(text):
    out = {}
    for line in text.splitlines():
        if " = " in line:
            k, v = line.split(" = ", 1)
            out[k.strip()] = v.strip()
    return out

def run_script(script):
    p = subprocess.run(
        ["python3", script],
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "script": script,
        "returncode": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
        "kv": parse_kv(p.stdout),
    }

def latest_json(pattern):
    files = sorted(REPORT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None, {}
    p = files[0]
    try:
        return p, json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return p, {"__load_error__": str(e)}

def main():
    failures = []
    warnings = []

    checks = {
        "next_action": run_script("scripts/learning-v2-next-action.py"),
        "lifecycle_router": run_script("scripts/learning-v2-lifecycle-router.py"),
        "lifecycle_sequence_verifier": run_script("scripts/learning-v2-lifecycle-sequence-verifier.py"),
        "system_integrity": run_script("scripts/learning-v2-system-integrity.py"),
        "agent_status": run_script("scripts/learning-v2-agent-status.py"),
    }

    next_action = checks["next_action"]["kv"]
    router = checks["lifecycle_router"]["kv"]
    sequence = checks["lifecycle_sequence_verifier"]["kv"]
    integrity = checks["system_integrity"]["kv"]
    agent = checks["agent_status"]["kv"]

    plan_path, plan = latest_json("opportunity-controlled-change-plan-*.json")

    if next_action.get("learning_v2_next_action") != "ok":
        failures.append(f"next_action_not_ok:{next_action.get('learning_v2_next_action')}")
    if next_action.get("next_safe_action") != "prepare_design_review_or_implementation_readiness":
        failures.append(f"next_safe_action_unexpected:{next_action.get('next_safe_action')}")

    if router.get("lifecycle_router") != "ok":
        failures.append(f"router_not_ok:{router.get('lifecycle_router')}")
    if router.get("next_allowed_stage") != "design_review_or_implementation_readiness":
        failures.append(f"router_next_allowed_stage_unexpected:{router.get('next_allowed_stage')}")

    if sequence.get("lifecycle_sequence_verifier") != "ok":
        failures.append(f"sequence_verifier_not_ok:{sequence.get('lifecycle_sequence_verifier')}")

    if integrity.get("system_integrity") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('system_integrity')}")
    if agent.get("learning_v2_agent_status") != "ok":
        failures.append(f"agent_status_not_ok:{agent.get('learning_v2_agent_status')}")

    for key in ["apply_allowed", "source_change_allowed", "commit_allowed", "push_allowed", "deploy_allowed"]:
        if router.get(key) != "false":
            failures.append(f"router_{key}_not_false:{router.get(key)}")

    if not plan_path:
        failures.append("missing_controlled_change_plan_report")
    else:
        if plan.get("__load_error__"):
            failures.append(f"controlled_change_plan_load_error:{plan.get('__load_error__')}")
        if plan.get("result") != "ok":
            failures.append(f"controlled_change_plan_result_not_ok:{plan.get('result')}")
        if plan.get("target_family") != "event.storytelling_path":
            failures.append(f"target_family_unexpected:{plan.get('target_family')}")
        if plan.get("registry_plan_mode") != "proposal_only_no_source_change":
            failures.append(f"registry_plan_mode_unexpected:{plan.get('registry_plan_mode')}")
        if plan.get("recommended_next_stage") != "design_review_or_implementation_readiness":
            failures.append(f"plan_next_stage_unexpected:{plan.get('recommended_next_stage')}")

        policy = plan.get("policy") or {}
        for key in ["website_files_changed", "git_commit", "git_push", "deploy", "restore_cloudflare_auto_deploy"]:
            if policy.get(key) is not False:
                failures.append(f"plan_policy_{key}_not_false:{policy.get(key)}")

    result = "ok" if not failures else "blocked"

    if result == "ok":
        readiness_decision = "design_review_ready_implementation_not_opened"
        next_safe_action = "prepare_human_design_review_packet"
        human_message = "Ready for design review packet. Implementation/source-change gate remains closed."
    else:
        readiness_decision = "blocked"
        next_safe_action = "stop_and_fix_readiness_blockers"
        human_message = "Blocked. Fix readiness blockers before any implementation planning."

    payload = {
        "generated_at": now_iso(),
        "readiness_id": READINESS_ID,
        "result": result,
        "target_family": router.get("target_family"),
        "lifecycle_stage": router.get("lifecycle_stage"),
        "next_allowed_stage": router.get("next_allowed_stage"),
        "readiness_decision": readiness_decision,
        "next_safe_action": next_safe_action,
        "human_message": human_message,
        "controlled_change_plan_report": str(plan_path) if plan_path else None,
        "failures": failures,
        "warnings": warnings,
        "checks": {
            name: {
                "script": data["script"],
                "returncode": data["returncode"],
                "kv": data["kv"],
                "stderr": data["stderr"],
            }
            for name, data in checks.items()
        },
        "policy": {
            "dry_run_only": True,
            "website_files_changed": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
            "source_change_gate_opened": False,
            "implementation_gate_opened": False
        },
    }

    out_json = REPORT_DIR / f"learning-v2-design-review-implementation-readiness-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-design-review-implementation-readiness-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Design Review / Implementation Readiness",
        "",
        f"- result: `{result}`",
        f"- target_family: `{payload['target_family']}`",
        f"- lifecycle_stage: `{payload['lifecycle_stage']}`",
        f"- next_allowed_stage: `{payload['next_allowed_stage']}`",
        f"- readiness_decision: `{readiness_decision}`",
        f"- next_safe_action: `{next_safe_action}`",
        f"- human_message: {human_message}",
        "",
        "## Failures",
    ]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    lines += ["", "## Warnings"]
    lines += [f"- {x}" for x in warnings] if warnings else ["- none"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("design_review_implementation_readiness =", result)
    print("target_family =", payload["target_family"])
    print("lifecycle_stage =", payload["lifecycle_stage"])
    print("next_allowed_stage =", payload["next_allowed_stage"])
    print("readiness_decision =", readiness_decision)
    print("next_safe_action =", next_safe_action)
    print("human_message =", human_message)
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
