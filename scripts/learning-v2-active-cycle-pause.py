#!/usr/bin/env python3
import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
BACKUP_DIR = BASE / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

ACTIVE_FIELDS = [
    "current_topic",
    "current_stage",
    "current_target_family",
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_state():
    return json.loads(STATE.read_text(encoding="utf-8"))

def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def noneish(v):
    return v in (None, "", "None")

def current_mode(state):
    audit = state.get("last_mode_policy_audit") or {}
    if audit.get("current_mode"):
        return audit.get("current_mode")

    sep = state.get("self_evolution_policy") or {}
    if sep.get("mode"):
        return sep.get("mode")

    mp = state.get("mode_policy")
    if isinstance(mp, dict) and mp.get("mode"):
        return mp.get("mode")
    if isinstance(mp, str):
        return mp

    if state.get("system_build_only") is True:
        return "system_build_only"

    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually clear active-cycle fields")
    args = ap.parse_args()

    state = load_state()
    mode = current_mode(state)
    sep = state.get("self_evolution_policy") or {}

    failures = []

    if mode != "system_build_only":
        failures.append(f"current_mode_not_system_build_only:{mode}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if sep.get("allow_source_changes") is not False:
        failures.append(f"self_evolution_policy_allow_source_changes_not_false:{sep.get('allow_source_changes')}")

    if sep.get("allow_git_commit") is not False:
        failures.append(f"self_evolution_policy_allow_git_commit_not_false:{sep.get('allow_git_commit')}")

    if sep.get("allow_deploy") is not False:
        failures.append(f"self_evolution_policy_allow_deploy_not_false:{sep.get('allow_deploy')}")

    before = {k: state.get(k) for k in ACTIVE_FIELDS}
    already_paused = all(noneish(v) for v in before.values())

    print("active_cycle_pause_tool = start")
    print("mode =", mode)
    print("apply =", str(args.apply).lower())
    for k, v in before.items():
        print(f"before_{k} = {repr(v)}")

    if failures:
        print("active_cycle_pause = blocked")
        print("failure_count =", len(failures))
        for x in failures:
            print("failure =", x)
        raise SystemExit(2)

    if already_paused:
        print("active_cycle_pause = noop_already_paused")
        print("state_written = false")
        print("business_source_written = false")
        print("git_commit = false")
        print("deploy = false")
        return

    if not args.apply:
        print("active_cycle_pause = dry_run_ok")
        for k in ACTIVE_FIELDS:
            print(f"would_set_{k} = None")
        print("state_written = false")
        print("business_source_written = false")
        print("git_commit = false")
        print("deploy = false")
        return

    backup = BACKUP_DIR / f"state-before-active-cycle-pause-{stamp()}.json"
    shutil.copy2(STATE, backup)

    for k in ACTIVE_FIELDS:
        state[k] = None

    state["last_active_cycle_pause"] = {
        "generated_at": now_iso(),
        "result": "applied",
        "previous_fields": before,
        "new_fields": {k: None for k in ACTIVE_FIELDS},
        "backup": str(backup),
        "business_source_written": False,
        "git_commit": False,
        "deploy": False,
        "reason": "Normalize active cycle to paused state before safe mode switcher dry-run."
    }

    save_state(state)

    print("active_cycle_pause = applied")
    print("backup =", backup)
    for k in ACTIVE_FIELDS:
        print(f"after_{k} = None")
    print("state_written = true")
    print("business_source_written = false")
    print("git_commit = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
