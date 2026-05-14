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

NEXT_ACTION_ID = "learning-v2-next-action-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

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

def parse_kv(text):
    out = {}
    for line in text.splitlines():
        if " = " in line:
            k, v = line.split(" = ", 1)
            out[k.strip()] = v.strip()
    return out

def bool_text(v):
    return str(v).lower() in ["true", "ok"]

def main():
    checks = {
        "agent_status": run_script("scripts/learning-v2-agent-status.py"),
        "lifecycle_router": run_script("scripts/learning-v2-lifecycle-router.py"),
        "lifecycle_sequence_verifier": run_script("scripts/learning-v2-lifecycle-sequence-verifier.py"),
        "system_integrity": run_script("scripts/learning-v2-system-integrity.py"),
    }

    failures = []
    warnings = []

    agent = checks["agent_status"]["kv"]
    router = checks["lifecycle_router"]["kv"]
    sequence = checks["lifecycle_sequence_verifier"]["kv"]
    integrity = checks["system_integrity"]["kv"]

    if agent.get("learning_v2_agent_status") != "ok":
        failures.append(f"agent_status_not_ok:{agent.get('learning_v2_agent_status')}")

    if integrity.get("system_integrity") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('system_integrity')}")

    if router.get("lifecycle_router") != "ok":
        failures.append(f"lifecycle_router_not_ok:{router.get('lifecycle_router')}")

    if sequence.get("lifecycle_sequence_verifier") != "ok":
        failures.append(f"lifecycle_sequence_verifier_not_ok:{sequence.get('lifecycle_sequence_verifier')}")

    for key in ["apply_allowed", "source_change_allowed", "commit_allowed", "push_allowed", "deploy_allowed"]:
        if router.get(key) != "false":
            failures.append(f"router_{key}_not_false:{router.get(key)}")

    next_allowed_stage = router.get("next_allowed_stage")
    target_family = router.get("target_family")
    lifecycle_stage = router.get("lifecycle_stage")

    if failures:
        result = "blocked"
        next_safe_action = "stop_and_fix_blockers"
        next_safe_command = "python3 scripts/learning-v2-system-integrity.py"
        human_message = "Blocked. Fix health or lifecycle consistency before continuing."
    elif next_allowed_stage == "design_review_or_implementation_readiness":
        result = "ok"
        next_safe_action = "prepare_design_review_or_implementation_readiness"
        next_safe_command = "python3 scripts/learning-v2-lifecycle-router.py && python3 scripts/learning-v2-lifecycle-sequence-verifier.py"
        human_message = "Safe next stage: design review / implementation readiness only. Do not apply website source changes yet."
    elif next_allowed_stage:
        result = "ok"
        next_safe_action = f"continue_to_{next_allowed_stage}"
        next_safe_command = "python3 scripts/learning-v2-lifecycle-router.py"
        human_message = f"Safe next stage: {next_allowed_stage}. Keep policy gates closed unless a later gate explicitly opens them."
    else:
        result = "blocked"
        next_safe_action = "no_next_stage_detected"
        next_safe_command = "python3 scripts/learning-v2-lifecycle-router.py"
        human_message = "No next stage detected. Re-run router and sequence verifier."

    payload = {
        "generated_at": now_iso(),
        "next_action_id": NEXT_ACTION_ID,
        "result": result,
        "target_family": target_family,
        "lifecycle_stage": lifecycle_stage,
        "next_allowed_stage": next_allowed_stage,
        "next_safe_action": next_safe_action,
        "next_safe_command": next_safe_command,
        "human_message": human_message,
        "checks": {
            name: {
                "script": data["script"],
                "returncode": data["returncode"],
                "kv": data["kv"],
                "stderr": data["stderr"],
            }
            for name, data in checks.items()
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
        },
    }

    out_json = REPORT_DIR / f"learning-v2-next-action-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-next-action-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Next Action",
        "",
        f"- result: `{result}`",
        f"- target_family: `{target_family}`",
        f"- lifecycle_stage: `{lifecycle_stage}`",
        f"- next_allowed_stage: `{next_allowed_stage}`",
        f"- next_safe_action: `{next_safe_action}`",
        f"- next_safe_command: `{next_safe_command}`",
        f"- human_message: {human_message}",
        "",
        "## Failures",
    ]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    lines += ["", "## Warnings"]
    lines += [f"- {x}" for x in warnings] if warnings else ["- none"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("learning_v2_next_action =", result)
    print("target_family =", target_family)
    print("lifecycle_stage =", lifecycle_stage)
    print("next_allowed_stage =", next_allowed_stage)
    print("next_safe_action =", next_safe_action)
    print("next_safe_command =", next_safe_command)
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
