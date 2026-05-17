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
        "ok": p.returncode == 0,
        "stdout": p.stdout.strip(),
        "stderr": p.stderr.strip(),
    }

def load_json(path, default=None):
    if not path:
        return default
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main():
    steps = []

    plan = [
        ("system_preflight", ["python3", "scripts/learning-v2-system-preflight.py"]),
        ("policy_lock_audit", ["python3", "scripts/learning-v2-policy-lock-auditor.py"]),
        ("mode_policy_audit", ["python3", "scripts/learning-v2-mode-policy-auditor.py"]),
        ("mode_transition_check", ["python3", "scripts/learning-v2-mode-transition-checker.py", "--inside-integrity"]),
        ("system_drift_audit", ["python3", "scripts/learning-v2-system-drift-auditor.py"]),
        ("tamper_guard", ["python3", "scripts/learning-v2-tamper-guard.py"]),
        ("target_family_registry_auditor", ["python3", "scripts/learning-v2-target-family-registry-auditor.py"]),
        ("lifecycle_sequence_verifier", ["python3", "scripts/learning-v2-lifecycle-sequence-verifier.py"]),
        ("report_dependency_cycle_auditor", ["python3", "scripts/learning-v2-report-dependency-cycle-auditor.py"]),
        ("control_status", ["python3", "scripts/learning-v2-control.py", "status"]),
    ]

    for name, cmd in plan:
        r = run_step(name, cmd)
        steps.append(r)
        if not r["ok"]:
            break

    state = load_json(STATE, default={})

    preflight = state.get("last_system_preflight") or {}
    policy_lock = state.get("last_policy_lock_audit") or {}
    mode_policy = state.get("last_mode_policy_audit") or {}
    mode_transition = state.get("last_mode_transition_check") or {}
    drift = state.get("last_system_drift_audit") or {}
    tamper_step = next((s for s in steps if s["name"] == "tamper_guard"), {})
    tamper_guard_result = None
    for line in (tamper_step.get("stdout") or "").splitlines():
        if line.startswith("learning_v2_tamper_guard"):
            tamper_guard_result = line.split("=", 1)[1].strip()

    gate_summary = preflight.get("gate_summary", {})
    commit_summary = preflight.get("commit_plan_audit_summary", {})

    hard_failures = []

    if not all(s["ok"] for s in steps):
        hard_failures.append("one_or_more_integrity_steps_failed")

    if preflight.get("result") != "ok":
        hard_failures.append("system_preflight_not_ok")

    if policy_lock.get("result") != "ok":
        hard_failures.append("policy_lock_audit_not_ok")

    if mode_policy.get("result") != "ok":
        hard_failures.append("mode_policy_audit_not_ok")

    if mode_transition.get("result") != "ok":
        hard_failures.append("mode_transition_check_not_ok")

    if drift.get("result") != "ok":
        hard_failures.append("system_drift_audit_not_ok")

    if drift.get("drift_count") != 0:
        hard_failures.append("system_drift_detected")

    if tamper_guard_result != "ok":
        hard_failures.append("tamper_guard_not_ok")

    if gate_summary.get("ok_for_system_build") is not True:
        hard_failures.append("ok_for_system_build_not_true")

    if gate_summary.get("ok_for_commit") is not False:
        hard_failures.append("ok_for_commit_not_false")

    if gate_summary.get("ok_for_deploy") is not False:
        hard_failures.append("ok_for_deploy_not_false")

    if gate_summary.get("business_freeze_stable") is not True:
        hard_failures.append("business_freeze_not_stable")

    if commit_summary.get("business_paths_selected_count") != 0:
        hard_failures.append("business_paths_selected_by_commit_plan")

    if commit_summary.get("dry_run_only") is not True:
        hard_failures.append("commit_plan_not_dry_run_only")

    result = "ok" if not hard_failures else "blocked"

    report = {
        "generated_at": now_iso(),
        "integrity": "learning-v2-system-integrity",
        "result": result,
        "hard_failures": hard_failures,
        "steps": steps,
        "latest_system_preflight": preflight,
        "latest_policy_lock_audit": policy_lock,
        "latest_mode_policy_audit": mode_policy,
        "latest_mode_transition_check": mode_transition,
        "latest_system_drift_audit": drift,
        "latest_tamper_guard_step": tamper_step,
        "tamper_guard_result": tamper_guard_result,
        "policy": {
            "no_website_source_changes": True,
            "no_git_add": True,
            "no_git_commit": True,
            "no_git_push": True,
            "no_deploy": True,
            "wrapper_is_observational_only": True,
        },
    }

    out = REPORT_DIR / f"system-integrity-{stamp()}.json"
    save_json(out, report)

    state["last_system_integrity"] = {
        "generated_at": report["generated_at"],
        "path": str(out),
        "result": result,
        "hard_failures": hard_failures,
        "preflight_result": preflight.get("result"),
        "policy_lock_audit_result": policy_lock.get("result"),
        "mode_policy_audit_result": mode_policy.get("result"),
        "mode_transition_check_result": mode_transition.get("result"),
        "drift_audit_result": drift.get("result"),
        "drift_count": drift.get("drift_count"),
        "tamper_guard_result": tamper_guard_result,
        "gate_summary": gate_summary,
        "commit_plan_audit_summary": commit_summary,
    }
    save_json(STATE, state)

    print("system_integrity =", result)
    print("integrity_report =", out)
    print("steps_total =", len(steps))
    print("steps_ok =", all(s["ok"] for s in steps))
    print("preflight_result =", preflight.get("result"))
    print("policy_lock_audit_result =", policy_lock.get("result"))
    print("mode_policy_audit_result =", mode_policy.get("result"))
    print("mode_transition_check_result =", mode_transition.get("result"))
    print("drift_audit_result =", drift.get("result"))
    print("drift_count =", drift.get("drift_count"))
    print("tamper_guard_result =", tamper_guard_result)
    print("ok_for_system_build =", gate_summary.get("ok_for_system_build"))
    print("ok_for_commit =", gate_summary.get("ok_for_commit"))
    print("ok_for_deploy =", gate_summary.get("ok_for_deploy"))
    print("business_freeze_stable =", gate_summary.get("business_freeze_stable"))
    print("business_paths_selected_count =", commit_summary.get("business_paths_selected_count"))
    print("dry_run_only =", commit_summary.get("dry_run_only"))

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
