#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path("/root/.openclaw/workspace/learning-v2")
STATE = BASE / "state.json"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def load_state():
    return json.loads(STATE.read_text(encoding="utf-8"))

def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "show"

    state = load_state()

    if mode == "show":
        print(json.dumps(state.get("self_evolution_policy"), ensure_ascii=False, indent=2))
        return 0

    if mode == "system-build":
        state["self_evolution_policy"] = {
            "mode": "system_build_only",
            "allow_source_changes": False,
            "allowed_source_roots": ["public", "components"],
            "require_exact_line_match": True,
            "require_backup": True,
            "require_post_apply_validation": True,
            "auto_rollback_on_validation_failure": True,
            "allow_git_commit": False,
            "allow_deploy": False,
            "note": "Temporary mode for building learning-v2 system. Website source auto-apply is blocked."
        }
        state["next_action"] = "Build learning-v2 system infrastructure. Source-writing auto-apply is temporarily blocked."
        state["updated_at"] = now_iso()
        save_state(state)
        print("mode_set = system_build_only")
        print("allow_source_changes = false")
        print("allow_git_commit = false")
        print("allow_deploy = false")
        return 0

    if mode == "autonomous":
        state["self_evolution_policy"] = {
            "mode": "autonomous_guarded_apply",
            "allow_source_changes": True,
            "allowed_source_roots": ["public", "components"],
            "require_exact_line_match": True,
            "require_backup": True,
            "require_post_apply_validation": True,
            "auto_rollback_on_validation_failure": True,
            "allow_git_commit": False,
            "allow_deploy": False,
            "note": "Autonomous guarded local source changes are allowed, but commit/deploy remain disabled."
        }
        state["next_action"] = "Autonomous guarded apply is enabled locally. Git commit and deploy remain disabled."
        state["updated_at"] = now_iso()
        save_state(state)
        print("mode_set = autonomous_guarded_apply")
        print("allow_source_changes = true")
        print("allow_git_commit = false")
        print("allow_deploy = false")
        return 0

    raise SystemExit("Usage: learning-v2-mode.py show|system-build|autonomous")

if __name__ == "__main__":
    raise SystemExit(main())
