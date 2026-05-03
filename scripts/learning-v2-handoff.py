#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
SNAPSHOT_DIR = BASE / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

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


def find_key(obj, key):
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                found.append(v)
            found.extend(find_key(v, key))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(find_key(item, key))
    return found

def last_value(state, key, default=None):
    values = find_key(state, key)
    if not values:
        return default
    return values[-1]

def policy_value(state, key, default=None):
    # Prefer direct state policy booleans so False is preserved.
    # Fall back to recursive lookup only for older event/report-style records.
    if key in state:
        return state.get(key)
    return last_value(state, key, default)

def main():
    state = load_json(STATE, default={})

    allow_source_changes = policy_value(state, "allow_source_changes")
    allow_git_commit = policy_value(state, "allow_git_commit")
    allow_deploy = policy_value(state, "allow_deploy")

    policy_mode = (
        last_value(state, "policy_mode")
        or last_value(state, "mode")
        or (
            "system_build_only"
            if allow_source_changes is False
            and allow_git_commit is False
            and allow_deploy is False
            else None
        )
    )

    status = {
        "current_topic": state.get("current_topic"),
        "current_stage": state.get("current_stage"),
        "current_target_family": state.get("current_target_family"),
        "policy_mode": policy_mode,
        "allow_source_changes": allow_source_changes,
        "allow_git_commit": allow_git_commit,
        "allow_deploy": allow_deploy,
        "applied_targets_count": len(state.get("applied_targets", [])),
        "disabled_target_families": state.get("disabled_target_families"),
    }

    latest = {
        "system_integrity": state.get("last_system_integrity"),
        "system_preflight": state.get("last_system_preflight"),
        "policy_lock_audit": state.get("last_policy_lock_audit"),
        "mode_policy_audit": state.get("last_mode_policy_audit"),
        "system_baseline": state.get("last_system_baseline"),
        "system_drift_audit": state.get("last_system_drift_audit"),
        "release_gate": state.get("last_release_gate"),
        "dirty_freeze": state.get("last_dirty_freeze"),
        "commit_plan": state.get("last_commit_plan"),
        "commit_plan_audit": state.get("last_commit_plan_audit"),
        "local_git_guard_audit": state.get("last_local_git_guard_audit"),
        "package_plan": state.get("last_package_plan"),
        "change_ledger": state.get("last_change_ledger"),
        "system_manifest": state.get("last_system_manifest"),
    }

    baseline_summary = (latest.get("system_baseline") or {}).get("summary", {})
    integrity_summary = latest.get("system_integrity") or {}
    preflight_summary = latest.get("system_preflight") or {}
    policy_lock_summary = latest.get("policy_lock_audit") or {}
    mode_policy_summary = latest.get("mode_policy_audit") or {}
    commit_plan = latest.get("commit_plan") or {}
    commit_audit = latest.get("commit_plan_audit") or {}
    commit_audit_summary = commit_audit.get("summary", {})

    handoff = {
        "generated_at": now_iso(),
        "handoff": "learning-v2-system-engineering-handoff",
        "status": status,
        "latest": latest,
        "summary": {
            "recommended_first_command": "python3 scripts/learning-v2-system-integrity.py",
            "system_integrity_result": integrity_summary.get("result"),
            "system_preflight_result": preflight_summary.get("result"),
            "policy_lock_audit_result": policy_lock_summary.get("result"),
            "mode_policy_audit_result": mode_policy_summary.get("result"),
            "mode_policy_current_mode": mode_policy_summary.get("current_mode"),
            "mode_policy_version": mode_policy_summary.get("policy_version"),
            "system_baseline_result": (latest.get("system_baseline") or {}).get("result"),
            "system_drift_result": (latest.get("system_drift_audit") or {}).get("result"),
            "drift_count": (latest.get("system_drift_audit") or {}).get("drift_count"),
            "learning_v2_script_count": baseline_summary.get("learning_v2_script_count"),
            "baseline_file_count": baseline_summary.get("baseline_file_count"),
            "business_source_dirty_count": baseline_summary.get("business_source_dirty_count"),
            "business_freeze_stable": baseline_summary.get("business_freeze_stable"),
            "ok_for_system_build": baseline_summary.get("ok_for_system_build"),
            "ok_for_commit": baseline_summary.get("ok_for_commit"),
            "ok_for_deploy": baseline_summary.get("ok_for_deploy"),
            "business_paths_selected_count": commit_audit_summary.get("business_paths_selected_count"),
            "dry_run_only": commit_audit_summary.get("dry_run_only"),
            "force_add_selected_count": commit_plan.get("force_add_selected_count"),
            "normal_add_selected_count": commit_plan.get("normal_add_selected_count"),
        },
        "rules": {
            "do_not_modify_website_source": True,
            "do_not_commit": True,
            "do_not_push": True,
            "do_not_deploy": True,
            "system_build_only": True,
            "active_cycle_must_remain_paused": True,
            "policy_lock_must_pass": True,
            "mode_policy_must_pass": True,
        },
        "known_frozen_business_dirty_files": [
            "components/nav.css",
            "components/nav.html",
            "public/index.html",
            "public/styles.css",
            "public/index.html.bak.20260427-105549",
            "public/styles.css.backup-20260422-064217",
            "public/styles.css.backup-20260422-064300",
            "public/styles.css.backup-20260422-064725",
            "public/styles.css.before-color-fix",
        ],
        "safe_next_steps": [
            "Continue system engineering only.",
            "Run system integrity first.",
            "Policy lock audit must remain ok before any further system engineering.",
            "Mode policy audit must remain ok before changing learning or source-change permissions.",
            "If any learning-v2 system script or RUNBOOK changes, regenerate baseline and rerun integrity.",
            "Do not add drift auditor into preflight directly because that can create recursive checks.",
            "Use system-integrity as the highest-level wrapper.",
        ],
    }

    json_path = SNAPSHOT_DIR / f"learning-v2-handoff-{stamp()}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-handoff-{stamp()}.md"

    save_json(json_path, handoff)

    lines = []
    lines.append("# learning-v2 handoff summary")
    lines.append("")
    lines.append(f"generated_at: {handoff['generated_at']}")
    lines.append("")
    lines.append("## Current mode")
    lines.append("")
    lines.append(f"- policy_mode: {status.get('policy_mode')}")
    lines.append(f"- current_topic: {status.get('current_topic')}")
    lines.append(f"- current_stage: {status.get('current_stage')}")
    lines.append(f"- allow_source_changes: {status.get('allow_source_changes')}")
    lines.append(f"- allow_git_commit: {status.get('allow_git_commit')}")
    lines.append(f"- allow_deploy: {status.get('allow_deploy')}")
    lines.append("")
    lines.append("## Recommended first command")
    lines.append("")
    lines.append("    cd /root/.openclaw/workspace")
    lines.append("    python3 scripts/learning-v2-system-integrity.py")
    lines.append("")
    lines.append("## Latest safety summary")
    lines.append("")
    for k, v in handoff["summary"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Hard rules")
    lines.append("")
    lines.append("- Do not modify website source.")
    lines.append("- Do not commit.")
    lines.append("- Do not push.")
    lines.append("- Do not deploy.")
    lines.append("- Stay in system_build_only.")
    lines.append("- Keep active cycle paused.")
    lines.append("")
    lines.append("## Frozen business dirty files")
    lines.append("")
    for x in handoff["known_frozen_business_dirty_files"]:
        lines.append(f"- {x}")
    lines.append("")
    lines.append("## Safe next steps")
    lines.append("")
    for x in handoff["safe_next_steps"]:
        lines.append(f"- {x}")
    lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    state["last_handoff"] = {
        "generated_at": handoff["generated_at"],
        "json": str(json_path),
        "md": str(md_path),
        "summary": handoff["summary"],
    }
    save_json(STATE, state)

    print("handoff = ok")
    print("handoff_json =", json_path)
    print("handoff_md =", md_path)
    print("recommended_first_command = python3 scripts/learning-v2-system-integrity.py")
    print("system_integrity_result =", handoff["summary"].get("system_integrity_result"))
    print("policy_lock_audit_result =", handoff["summary"].get("policy_lock_audit_result"))
    print("mode_policy_audit_result =", handoff["summary"].get("mode_policy_audit_result"))
    print("mode_policy_current_mode =", handoff["summary"].get("mode_policy_current_mode"))
    print("drift_count =", handoff["summary"].get("drift_count"))
    print("business_freeze_stable =", handoff["summary"].get("business_freeze_stable"))
    print("ok_for_commit =", handoff["summary"].get("ok_for_commit"))
    print("ok_for_deploy =", handoff["summary"].get("ok_for_deploy"))

if __name__ == "__main__":
    main()
