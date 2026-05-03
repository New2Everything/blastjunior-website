#!/usr/bin/env python3
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
SCRIPTS = WORKSPACE / "scripts"

COMMANDS = {
    "mode": "learning-v2-mode.py",
    "doctor": "learning-v2-doctor.py",
    "deploy-observer": "learning-v2-deploy-observer.py",
    "ledger": "learning-v2-change-ledger.py",
    "release-plan": "learning-v2-release-planner.py",
    "manifest": "learning-v2-system-manifest.py",
    "package-plan": "learning-v2-package-planner.py",
    "local-exclude": "learning-v2-local-exclude-manager.py",
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def load_state():
    return json.loads(STATE.read_text(encoding="utf-8"))

def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def run_script(name, args=None):
    args = args or []
    script = SCRIPTS / COMMANDS[name]

    if not script.exists():
        print(f"ERROR: missing script: {script}")
        return 1

    print("")
    print(f"=== learning-v2 control: {name} ===")
    r = subprocess.run(
        ["/usr/bin/env", "python3", str(script)] + args,
        cwd=str(WORKSPACE),
        text=True,
        check=False,
    )
    return r.returncode

def print_status():
    state = load_state()
    legacy_policy = state.get("self_evolution_policy") or {}

    mode_policy_path = BASE / "mode-policy.json"
    mode_policy = {}
    if mode_policy_path.exists():
        mode_policy = json.loads(mode_policy_path.read_text(encoding="utf-8"))

    def resolve_current_mode():
        known_modes = set((mode_policy.get("modes") or {}).keys())

        sep_mode = legacy_policy.get("mode")
        if sep_mode in known_modes:
            return sep_mode

        mp = state.get("mode_policy")
        if isinstance(mp, dict) and mp.get("mode") in known_modes:
            return mp.get("mode")
        if isinstance(mp, str) and mp in known_modes:
            return mp

        last_mode_audit = state.get("last_mode_policy_audit") or {}
        audit_mode = last_mode_audit.get("current_mode")
        if audit_mode in known_modes:
            return audit_mode

        if state.get("system_build_only") is True:
            return "system_build_only"

        return None

    current_mode = resolve_current_mode()
    mode_rule = (mode_policy.get("modes") or {}).get(current_mode) or {}
    last_mode_audit = state.get("last_mode_policy_audit") or {}
    last_integrity = state.get("last_system_integrity") or {}

    print("learning_v2_status = ok")
    print("current_mode =", current_mode)
    print("mode_policy_version =", mode_policy.get("version"))
    print("mode_policy_audit_result =", last_mode_audit.get("result"))
    print("system_integrity_result =", last_integrity.get("result"))
    print("system_build_only =", state.get("system_build_only"))
    print("learning_cycle_enabled =", mode_rule.get("learning_cycle_enabled"))
    print("topic_selector_allowed =", mode_rule.get("topic_selector_allowed"))
    print("stage_executor_allowed =", mode_rule.get("stage_executor_allowed"))
    print("proposal_generation_allowed =", mode_rule.get("proposal_generation_allowed"))
    print("source_changes_allowed =", mode_rule.get("source_changes_allowed"))
    print("git_add_allowed =", mode_rule.get("git_add_allowed"))
    print("git_commit_allowed =", mode_rule.get("git_commit_allowed"))
    print("git_push_allowed =", mode_rule.get("git_push_allowed"))
    print("deploy_allowed =", mode_rule.get("deploy_allowed"))
    print("active_cycle_must_be_paused =", mode_rule.get("active_cycle_must_be_paused"))
    print("current_topic =", state.get("current_topic"))
    print("current_stage =", state.get("current_stage"))
    print("current_target_family =", state.get("current_target_family"))
    print("next_action =", state.get("next_action"))
    print("legacy_policy_mode =", legacy_policy.get("mode"))
    print("allow_source_changes_state =", state.get("allow_source_changes"))
    print("allow_git_commit_state =", state.get("allow_git_commit"))
    print("allow_deploy_state =", state.get("allow_deploy"))
    print("applied_targets_count =", len(state.get("applied_targets") or []))
    print("disabled_target_families =", state.get("disabled_target_families") or [])

    if state.get("last_package_plan"):
        print("last_package_plan =", state["last_package_plan"].get("snapshot_report"))

    if state.get("last_change_ledger"):
        print("last_change_ledger =", state["last_change_ledger"].get("snapshot_report"))

    if state.get("last_system_manifest"):
        print("last_system_manifest =", state["last_system_manifest"].get("snapshot_report"))

def all_safe():
    """
    Safe system-build diagnostics only.
    No website source auto-apply.
    No git commit.
    No git push.
    No deploy.
    """
    sequence = [
        ("doctor", []),
        ("deploy-observer", []),
        ("ledger", []),
        ("release-plan", []),
        ("manifest", []),
        ("package-plan", []),
        ("doctor", []),
    ]

    for name, args in sequence:
        rc = run_script(name, args)
        if rc != 0:
            print(f"all_safe_result = failed_at_{name}")
            return rc

    state = load_state()
    state["last_control_run"] = {
        "at": now_iso(),
        "command": "all-safe",
        "result": "ok",
        "source_changed": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }
    state["next_action"] = "System diagnostics complete. Review package plan before any release action."
    state["updated_at"] = now_iso()
    save_state(state)

    print("")
    print("all_safe_result = ok")
    print("source_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    return 0

def usage():
    print("""
Usage:
  python3 scripts/learning-v2-control.py status
  python3 scripts/learning-v2-control.py all-safe
  python3 scripts/learning-v2-control.py doctor
  python3 scripts/learning-v2-control.py deploy-observer
  python3 scripts/learning-v2-control.py ledger
  python3 scripts/learning-v2-control.py release-plan
  python3 scripts/learning-v2-control.py manifest
  python3 scripts/learning-v2-control.py package-plan
  python3 scripts/learning-v2-control.py local-exclude
  python3 scripts/learning-v2-control.py mode show
  python3 scripts/learning-v2-control.py mode system-build
  python3 scripts/learning-v2-control.py mode autonomous
""".strip())

def main():
    if len(sys.argv) < 2:
        usage()
        return 1

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "status":
        print_status()
        return 0

    if cmd == "all-safe":
        return all_safe()

    if cmd == "mode":
        return run_script("mode", args)

    if cmd in COMMANDS:
        return run_script(cmd, args)

    usage()
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
