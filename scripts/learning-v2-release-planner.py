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

def load_state():
    return json.loads(STATE.read_text(encoding="utf-8"))

def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def load_last_ledger(state):
    info = state.get("last_change_ledger") or {}
    p = Path(info.get("snapshot_json", ""))
    if not p.exists():
        raise FileNotFoundError(f"last change ledger not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))

def is_runtime_artifact(path):
    runtime_prefixes = [
        "learning-v2/reports/",
        "learning-v2/snapshots/",
        "learning-v2/backups/",
    ]
    runtime_files = [
        "learning-v2/state.json",
        "learning-v2/outcomes.jsonl",
        "learning-v2/experiments.jsonl",
    ]
    return any(path.startswith(x) for x in runtime_prefixes) or path in runtime_files

def is_system_core(path):
    if path.startswith("scripts/learning-v2-"):
        return True
    if path == "learning-v2/deployment-policy.json":
        return True
    return False

def classify_release_lane(item):
    path = item["path"]
    status = item["status"]
    category = item.get("category")

    if status.strip().startswith("D"):
        return "blocked_deletions"

    if is_runtime_artifact(path):
        return "runtime_artifacts_do_not_commit"

    if is_system_core(path):
        return "learning_v2_system_core_candidate"

    if category == "website_source":
        return "website_experiment_changes_hold"

    if category in ["deployment_config", "cloudflare_worker_or_config", "github_workflow"]:
        return "deployment_related_hold"

    if category in ["generated_or_experimental", "media_or_verification_artifact"]:
        return "generated_or_media_hold"

    return "manual_review_hold"

def main():
    state = load_state()
    ledger = load_last_ledger(state)
    entries = ledger.get("entries") or []

    lanes = {}
    for item in entries:
        lane = classify_release_lane(item)
        lanes.setdefault(lane, []).append(item)

    local_exclude_policy = state.get("local_exclude_policy") or {}
    last_commit_plan_audit = state.get("last_commit_plan_audit") or {}
    commit_audit_summary = last_commit_plan_audit.get("summary") or {}

    local_exclude_ready = bool(local_exclude_policy.get("exclude_file"))
    commit_plan_audit_ok = last_commit_plan_audit.get("result") == "ok"
    business_paths_selected_count = commit_audit_summary.get("business_paths_selected_count")

    if not local_exclude_ready:
        safe_next_build_step = "Create a local ignore/exclude policy for learning-v2 runtime artifacts, then rerun ledger."
    elif not commit_plan_audit_ok:
        safe_next_build_step = "Run learning-v2 commit planner and commit plan auditor; keep commit/push/deploy disabled."
    elif business_paths_selected_count != 0:
        safe_next_build_step = "Fix commit plan audit because business paths are selected; do not commit/push/deploy."
    else:
        safe_next_build_step = "Review guarded selected-file commit plan for learning-v2 system files only; do not push or deploy."

    release_plan = {
        "generated_at": now_iso(),
        "mode": "release_planning_only",
        "source_changed": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "input_ledger": state.get("last_change_ledger", {}).get("snapshot_json"),
        "deployment_policy": state.get("deployment_policy_path"),
        "summary": {k: len(v) for k, v in lanes.items()},
        "lanes": lanes,
        "recommendation": {
            "immediate_action": "Do not commit/push/deploy yet.",
            "safe_next_build_step": safe_next_build_step,
            "local_exclude_ready": local_exclude_ready,
            "commit_plan_audit_ok": commit_plan_audit_ok,
            "business_paths_selected_count": business_paths_selected_count,
            "release_sequence": [
                "First stabilize learning-v2 system files only.",
                "Exclude runtime reports/snapshots/backups from release.",
                "Review website experiment changes separately.",
                "Resolve or restore high-risk deleted files before any push to main.",
                "Only after clean release plan, consider a guarded GitHub commit plan.",
            ],
        },
        "proposed_git_lanes": {
            "commit_later_learning_v2_system_core_candidate": [
                item["path"] for item in lanes.get("learning_v2_system_core_candidate", [])
            ],
            "do_not_commit_runtime_artifacts": [
                item["path"] for item in lanes.get("runtime_artifacts_do_not_commit", [])
            ],
            "hold_website_experiments": [
                item["path"] for item in lanes.get("website_experiment_changes_hold", [])
            ],
            "blocked_deletions": [
                item["path"] for item in lanes.get("blocked_deletions", [])
            ],
            "hold_deployment_related": [
                item["path"] for item in lanes.get("deployment_related_hold", [])
            ],
        },
    }

    out_json = SNAPSHOT_DIR / f"learning-v2-release-plan-{stamp()}.json"
    out_json.write_text(json.dumps(release_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out_md = SNAPSHOT_DIR / f"learning-v2-release-plan-{stamp()}.md"
    lines = []
    lines.append("# Learning V2 Release Plan")
    lines.append("")
    lines.append(f"- generated_at: `{release_plan['generated_at']}`")
    lines.append("- mode: `release_planning_only`")
    lines.append("- source_changed: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    for k, v in sorted(release_plan["summary"].items()):
        lines.append(f"- {k}: `{v}`")
    lines.append("")
    lines.append("## Recommendation")
    lines.append("")
    lines.append(f"- immediate_action: `{release_plan['recommendation']['immediate_action']}`")
    lines.append(f"- safe_next_build_step: `{release_plan['recommendation']['safe_next_build_step']}`")
    lines.append("")
    lines.append("## Proposed release sequence")
    lines.append("")
    for step in release_plan["recommendation"]["release_sequence"]:
        lines.append(f"- {step}")
    lines.append("")
    lines.append("## Lanes")
    lines.append("")
    for lane, items in sorted(lanes.items()):
        lines.append(f"### {lane} ({len(items)})")
        lines.append("")
        for item in items[:120]:
            lines.append(f"- `{item['status']}` `{item['path']}` category=`{item.get('category')}` risk=`{item.get('risk')}`")
        if len(items) > 120:
            lines.append(f"- ... truncated {len(items) - 120} more")
        lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")

    state["last_release_plan"] = {
        "at": now_iso(),
        "snapshot_json": str(out_json),
        "snapshot_report": str(out_md),
        "summary": release_plan["summary"],
        "source_changed": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }
    state["next_action"] = "Review release plan. Next: create local exclude policy for runtime artifacts; do not commit/push/deploy."
    state["updated_at"] = now_iso()
    save_state(state)

    print("release_planner_result = ok")
    print("source_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("snapshot_json =", out_json)
    print("snapshot_report =", out_md)
    print("summary =", json.dumps(release_plan["summary"], ensure_ascii=False))
    print("safe_next_build_step =", release_plan["recommendation"]["safe_next_build_step"])

if __name__ == "__main__":
    main()
