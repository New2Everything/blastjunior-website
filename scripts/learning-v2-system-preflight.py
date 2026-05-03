#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def run_step(name, cmd):
    p = subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "name": name,
        "cmd": cmd,
        "returncode": p.returncode,
        "stdout": p.stdout.strip(),
        "stderr": p.stderr.strip(),
        "ok": p.returncode == 0,
    }

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_noneish(v):
    return v in (None, "", "None")

def enforce_system_build_only_pause():
    state = load_json(STATE, default={})
    if state.get("system_build_only") is not True:
        return False

    before = {
        "current_topic": state.get("current_topic"),
        "current_stage": state.get("current_stage"),
        "current_target_family": state.get("current_target_family"),
    }

    already_paused = (
        is_noneish(before["current_topic"])
        and is_noneish(before["current_stage"])
        and is_noneish(before["current_target_family"])
    )

    if already_paused:
        return False

    state["current_topic"] = None
    state["current_stage"] = None
    state["current_target_family"] = None

    events = state.get("system_build_only_active_cycle_autopause_events") or []
    events.append({
        "at": now_iso(),
        "reason": "system_preflight enforces active cycle pause while system_build_only is true",
        "previous": before,
    })
    state["system_build_only_active_cycle_autopause_events"] = events[-20:]

    save_json(STATE, state)

    print("system_build_only_active_cycle_autopaused = true")
    print("previous_current_topic =", before["current_topic"])
    print("previous_current_stage =", before["current_stage"])
    print("previous_current_target_family =", before["current_target_family"])

    return True

def main():
    enforce_system_build_only_pause()
    steps = []

    plan = [
        ("control_all_safe", ["python3", "scripts/learning-v2-control.py", "all-safe"]),
        ("release_gate_before", ["python3", "scripts/learning-v2-release-gate.py"]),
        ("commit_planner_dry_run", ["python3", "scripts/learning-v2-commit-planner.py"]),
        ("commit_plan_auditor", ["python3", "scripts/learning-v2-commit-plan-auditor.py"]),
        ("local_git_guard_auditor", ["python3", "scripts/learning-v2-local-git-guard-auditor.py"]),
        ("release_gate_after", ["python3", "scripts/learning-v2-release-gate.py"]),
        ("control_status", ["python3", "scripts/learning-v2-control.py", "status"]),
    ]

    for name, cmd in plan:
        result = run_step(name, cmd)
        steps.append(result)
        if not result["ok"]:
            break

    state = load_json(STATE, default={})

    last_gate_info = state.get("last_release_gate") or {}
    last_gate_path = last_gate_info.get("report")
    last_gate = load_json(last_gate_path, default={}) if last_gate_path else {}
    gate_summary = last_gate.get("summary", {})

    last_audit_info = state.get("last_commit_plan_audit") or {}
    commit_audit_summary = last_audit_info.get("summary", {})
    commit_audit_result = last_audit_info.get("result")

    last_guard_info = state.get("last_local_git_guard_audit") or {}
    guard_audit_result = last_guard_info.get("result")
    guard_hooks = last_guard_info.get("hooks", [])

    hard_failures = []

    if not all(s["ok"] for s in steps):
        hard_failures.append("one_or_more_steps_failed")

    if gate_summary.get("ok_for_system_build") is not True:
        hard_failures.append("release_gate_not_ok_for_system_build")

    if gate_summary.get("ok_for_commit") is not False:
        hard_failures.append("release_gate_commit_flag_not_false")

    if gate_summary.get("ok_for_deploy") is not False:
        hard_failures.append("release_gate_deploy_flag_not_false")

    if gate_summary.get("business_freeze_stable") is not True:
        hard_failures.append("business_freeze_not_stable")

    if commit_audit_result != "ok":
        hard_failures.append("commit_plan_audit_not_ok")

    if commit_audit_summary.get("business_paths_selected_count") != 0:
        hard_failures.append("business_paths_selected_by_commit_plan")

    if commit_audit_summary.get("dry_run_only") is not True:
        hard_failures.append("commit_plan_not_dry_run_only")

    if commit_audit_summary.get("commit_now") is not False:
        hard_failures.append("commit_now_not_false")

    if commit_audit_summary.get("push_now") is not False:
        hard_failures.append("push_now_not_false")

    if commit_audit_summary.get("deploy_now") is not False:
        hard_failures.append("deploy_now_not_false")

    if guard_audit_result != "ok":
        hard_failures.append("local_git_guard_audit_not_ok")

    required_hooks = {"pre-commit", "pre-push"}
    ok_hooks = {h.get("name") for h in guard_hooks if h.get("ok") is True}

    if not required_hooks.issubset(ok_hooks):
        hard_failures.append("required_local_git_hooks_not_ok")

    result = "ok" if not hard_failures else "blocked"

    report = {
        "generated_at": now_iso(),
        "preflight": "learning-v2-system-preflight",
        "result": result,
        "hard_failures": hard_failures,
        "steps": steps,
        "last_release_gate_report": last_gate_path,
        "last_release_gate_summary": gate_summary,
        "last_commit_plan_audit": last_audit_info,
        "last_local_git_guard_audit": last_guard_info,
        "policy": {
            "no_website_source_changes": True,
            "no_git_add": True,
            "no_git_commit": True,
            "no_git_push": True,
            "no_deploy": True,
            "dry_run_only": True,
            "local_git_guards_required": True,
        },
    }

    out = REPORT_DIR / f"system-preflight-{stamp()}.json"
    save_json(out, report)

    state["last_system_preflight"] = {
        "generated_at": report["generated_at"],
        "path": str(out),
        "result": result,
        "hard_failures": hard_failures,
        "gate_summary": gate_summary,
        "commit_plan_audit_summary": commit_audit_summary,
        "local_git_guard_audit_result": guard_audit_result,
    }
    save_json(STATE, state)

    print("system_preflight =", result)
    print("preflight_report =", out)
    print("steps_total =", len(steps))
    print("steps_ok =", all(s["ok"] for s in steps))
    print("ok_for_system_build =", gate_summary.get("ok_for_system_build"))
    print("ok_for_commit =", gate_summary.get("ok_for_commit"))
    print("ok_for_deploy =", gate_summary.get("ok_for_deploy"))
    print("business_freeze_stable =", gate_summary.get("business_freeze_stable"))
    print("business_source_dirty_count =", gate_summary.get("business_source_dirty_count"))
    print("commit_plan_audit =", commit_audit_result)
    print("business_paths_selected_count =", commit_audit_summary.get("business_paths_selected_count"))
    print("dry_run_only =", commit_audit_summary.get("dry_run_only"))
    print("commit_now =", commit_audit_summary.get("commit_now"))
    print("push_now =", commit_audit_summary.get("push_now"))
    print("deploy_now =", commit_audit_summary.get("deploy_now"))
    print("local_git_guard_audit =", guard_audit_result)

    for h in guard_hooks:
        print(f"hook_{h.get('name')}_ok =", h.get("ok"))

    if hard_failures:
        print()
        print("hard_failures:")
        for x in hard_failures:
            print(" ", x)

    print()
    print("step_results:")
    for s in steps:
        print(f"  {s['name']}: rc={s['returncode']} ok={s['ok']}")

    if result != "ok":
        raise SystemExit(2)

if __name__ == "__main__":
    main()
