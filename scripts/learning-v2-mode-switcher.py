#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
MODE_POLICY = BASE / "mode-policy.json"
BACKUP_DIR = BASE / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

FROM_MODE = "system_build_only"
TO_MODE = "learning_observe_only"

ACTIVE_FIELDS = [
    "current_topic",
    "current_stage",
    "current_target_family",
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def parse_kv(text):
    out = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out

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
        "stdout": p.stdout,
        "stderr": p.stderr,
        "kv": parse_kv(p.stdout),
        "ok": p.returncode == 0,
    }

def noneish(v):
    return v in (None, "", "None")

def current_mode(state):
    sep = state.get("self_evolution_policy") or {}
    if isinstance(sep, dict) and sep.get("mode"):
        return sep.get("mode")

    mp = state.get("mode_policy")
    if isinstance(mp, dict) and mp.get("mode"):
        return mp.get("mode")
    if isinstance(mp, str):
        return mp

    if state.get("system_build_only") is True:
        return "system_build_only"

    audit = state.get("last_mode_policy_audit") or {}
    if audit.get("current_mode"):
        return audit.get("current_mode")

    return None

def add_failure(failures, name, details=None):
    failures.append({
        "name": name,
        "details": details or {},
    })

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually switch system_build_only -> learning_observe_only")
    ap.add_argument("--target", default=TO_MODE, help="target mode; only learning_observe_only is allowed")
    args = ap.parse_args()

    print("mode_switcher = start")
    print("apply =", str(args.apply).lower())
    print("from_mode_required =", FROM_MODE)
    print("target_mode =", args.target)

    failures = []

    if args.target != TO_MODE:
        add_failure(failures, "unsupported_target_mode", {"target": args.target, "allowed": TO_MODE})

    state = load_json(STATE, default={})
    policy = load_json(MODE_POLICY, default={})
    modes = policy.get("modes") or {}
    target_rule = modes.get(TO_MODE) or {}

    mode_before = current_mode(state)
    print("current_mode_before =", mode_before)

    if mode_before != FROM_MODE:
        add_failure(failures, "current_mode_not_system_build_only", {"current_mode": mode_before})

    if not all(noneish(state.get(k)) for k in ACTIVE_FIELDS):
        add_failure(failures, "active_cycle_not_paused", {k: state.get(k) for k in ACTIVE_FIELDS})

    if state.get("allow_source_changes") is not False:
        add_failure(failures, "allow_source_changes_not_false", {"value": state.get("allow_source_changes")})

    if state.get("allow_git_commit") is not False:
        add_failure(failures, "allow_git_commit_not_false", {"value": state.get("allow_git_commit")})

    if state.get("allow_deploy") is not False:
        add_failure(failures, "allow_deploy_not_false", {"value": state.get("allow_deploy")})

    if TO_MODE not in modes:
        add_failure(failures, "target_mode_missing_from_mode_policy", {"target": TO_MODE, "known_modes": sorted(modes.keys())})

    if target_rule.get("learning_cycle_enabled") is not True:
        add_failure(failures, "target_learning_cycle_not_enabled", {"value": target_rule.get("learning_cycle_enabled")})

    if target_rule.get("topic_selector_allowed") is not True:
        add_failure(failures, "target_topic_selector_not_allowed", {"value": target_rule.get("topic_selector_allowed")})

    if target_rule.get("source_changes_allowed") is not False:
        add_failure(failures, "target_source_changes_not_blocked", {"value": target_rule.get("source_changes_allowed")})

    if target_rule.get("git_commit_allowed") is not False:
        add_failure(failures, "target_git_commit_not_blocked", {"value": target_rule.get("git_commit_allowed")})

    if target_rule.get("git_push_allowed") is not False:
        add_failure(failures, "target_git_push_not_blocked", {"value": target_rule.get("git_push_allowed")})

    if target_rule.get("deploy_allowed") is not False:
        add_failure(failures, "target_deploy_not_blocked", {"value": target_rule.get("deploy_allowed")})

    print()
    print("=== precheck: system integrity ===")
    integrity = run_step("system_integrity", ["python3", "scripts/learning-v2-system-integrity.py"])
    print(integrity["stdout"], end="")
    if integrity["stderr"]:
        print("stderr:")
        print(integrity["stderr"])

    ikv = integrity["kv"]
    if not integrity["ok"]:
        add_failure(failures, "system_integrity_command_failed", {"returncode": integrity["returncode"]})
    if ikv.get("system_integrity") != "ok":
        add_failure(failures, "system_integrity_not_ok", {"value": ikv.get("system_integrity")})
    if ikv.get("drift_count") != "0":
        add_failure(failures, "system_drift_not_zero", {"drift_count": ikv.get("drift_count")})
    if ikv.get("ok_for_commit") != "False":
        add_failure(failures, "ok_for_commit_not_false", {"value": ikv.get("ok_for_commit")})
    if ikv.get("ok_for_deploy") != "False":
        add_failure(failures, "ok_for_deploy_not_false", {"value": ikv.get("ok_for_deploy")})
    if ikv.get("business_freeze_stable") != "True":
        add_failure(failures, "business_freeze_not_stable", {"value": ikv.get("business_freeze_stable")})
    if ikv.get("business_paths_selected_count") != "0":
        add_failure(failures, "business_paths_selected", {"value": ikv.get("business_paths_selected_count")})
    if ikv.get("dry_run_only") != "True":
        add_failure(failures, "commit_plan_not_dry_run_only", {"value": ikv.get("dry_run_only")})

    print()
    print("=== precheck: mode transition checker ===")
    transition = run_step("mode_transition_check", ["python3", "scripts/learning-v2-mode-transition-checker.py"])
    print(transition["stdout"], end="")
    if transition["stderr"]:
        print("stderr:")
        print(transition["stderr"])

    tkv = transition["kv"]
    if not transition["ok"]:
        add_failure(failures, "mode_transition_checker_command_failed", {"returncode": transition["returncode"]})
    if tkv.get("mode_transition_check") != "ok":
        add_failure(failures, "mode_transition_check_not_ok", {"value": tkv.get("mode_transition_check")})
    if tkv.get("from_mode") != FROM_MODE:
        add_failure(failures, "transition_from_mode_not_system_build_only", {"value": tkv.get("from_mode")})
    if tkv.get("to_mode") != TO_MODE:
        add_failure(failures, "transition_to_mode_not_learning_observe_only", {"value": tkv.get("to_mode")})
    if tkv.get("would_allow_topic_selector") != "true":
        add_failure(failures, "transition_would_not_allow_topic_selector", {"value": tkv.get("would_allow_topic_selector")})
    if tkv.get("would_allow_learning_cycle") != "true":
        add_failure(failures, "transition_would_not_allow_learning_cycle", {"value": tkv.get("would_allow_learning_cycle")})
    if tkv.get("would_allow_source_changes") != "false":
        add_failure(failures, "transition_would_allow_source_changes", {"value": tkv.get("would_allow_source_changes")})
    if tkv.get("would_allow_git_commit") != "false":
        add_failure(failures, "transition_would_allow_git_commit", {"value": tkv.get("would_allow_git_commit")})
    if tkv.get("would_allow_deploy") != "false":
        add_failure(failures, "transition_would_allow_deploy", {"value": tkv.get("would_allow_deploy")})

    planned_changes = {
        "system_build_only": False,
        "self_evolution_policy.mode": TO_MODE,
        "learning_cycle_enabled": True,
        "topic_selector_allowed": True,
        "allow_source_changes": False,
        "allow_git_commit": False,
        "allow_deploy": False,
        "current_topic": None,
        "current_stage": None,
        "current_target_family": None,
    }

    print()
    print("=== decision ===")

    if failures:
        print("mode_switch = blocked")
        print("failure_count =", len(failures))
        for f in failures:
            print("failure =", f["name"], json.dumps(f["details"], ensure_ascii=False))
        print("state_written = false")
        print("business_source_written = false")
        print("git_commit = false")
        print("git_push = false")
        print("deploy = false")
        raise SystemExit(2)

    if not args.apply:
        print("mode_switch = dry_run_ok")
        print("would_switch_from =", FROM_MODE)
        print("would_switch_to =", TO_MODE)
        for k, v in planned_changes.items():
            print(f"would_set_{k} = {repr(v)}")
        print("state_written = false")
        print("business_source_written = false")
        print("git_commit = false")
        print("git_push = false")
        print("deploy = false")
        return

    backup = BACKUP_DIR / f"state-before-mode-switch-{stamp()}.json"
    shutil.copy2(STATE, backup)

    sep = state.get("self_evolution_policy")
    if not isinstance(sep, dict):
        sep = {}
    sep["mode"] = TO_MODE
    sep["allow_source_changes"] = False
    sep["allow_git_commit"] = False
    sep["allow_deploy"] = False
    sep["note"] = "learning_observe_only: topic selector and learning cycle may run; website source changes, git actions, and deploy remain blocked."
    state["self_evolution_policy"] = sep
    state["system_build_only"] = False

    state["learning_cycle_enabled"] = True
    state["topic_selector_allowed"] = True
    state["allow_source_changes"] = False
    state["allow_git_commit"] = False
    state["allow_deploy"] = False

    for k in ACTIVE_FIELDS:
        state[k] = None

    state["last_mode_switch"] = {
        "generated_at": now_iso(),
        "result": "applied",
        "from": FROM_MODE,
        "to": TO_MODE,
        "backup": str(backup),
        "planned_changes": planned_changes,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }

    save_json(STATE, state)

    print("mode_switch = applied")
    print("backup =", backup)
    print("switched_from =", FROM_MODE)
    print("switched_to =", TO_MODE)
    print("state_written = true")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("note = post-apply audits should be run before any further action")

if __name__ == "__main__":
    main()
