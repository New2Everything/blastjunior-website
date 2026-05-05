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

def load_manifest(state):
    info = state.get("last_system_manifest") or {}
    p = Path(info.get("snapshot_json", ""))
    if not p.exists():
        raise FileNotFoundError(f"system manifest not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))

def main():
    state = load_state()
    manifest = load_manifest(state)

    core = [x for x in manifest["items"] if x["role"] == "core"]
    support = [x for x in manifest["items"] if x["role"] == "support"]

    learning_v2_config_candidates = [
        "learning-v2/CONSTITUTION.md",
        "learning-v2/deployment-policy.json",
        "learning-v2/push-approval-state.json",
    ]

    learning_v2_data_hold = [
        "learning-v2/inbox/directives-inbox.jsonl",
        "learning-v2/patterns.jsonl",
        "learning-v2/source_log.jsonl",
        "learning-v2/root-crontab.backup.20260426-085520",
        "learning-v2/root-crontab.before-delete-frozen.20260426-095737",
    ]

    package_plan = {
        "generated_at": now_iso(),
        "mode": "package_planning_only",
        "source_changed": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "recommended_strategy": "force_add_selected_files",
        "reason": (
            "The repo ignores scripts/ globally. For v0.1, use git add -f on selected learning-v2 files "
            "instead of changing .gitignore or moving paths."
        ),
        "v0_1_package": {
            "core_scripts": [x["path"] for x in core],
            "support_scripts_optional": [x["path"] for x in support],
            "config_candidates": learning_v2_config_candidates,
            "hold_data_files": learning_v2_data_hold,
        },
        "explicitly_exclude": [
            "learning-v2/reports/",
            "learning-v2/snapshots/",
            "learning-v2/backups/",
            "learning-v2/cache/",
            "learning-v2/state.json",
            "learning-v2/outcomes.jsonl",
            "learning-v2/experiments.jsonl",
            "website experiment changes in public/ and components/",
            "high-risk deleted files",
            "Cloudflare/wrangler/worker changes until separately reviewed",
        ],
        "future_git_commands_preview_only": [
            "git add -f scripts/learning-v2-dispatch.py",
            "git add -f scripts/learning-v2-topic-selector.py",
            "git add -f scripts/learning-v2-discover-executor.py",
            "git add -f scripts/learning-v2-simplicity-audit.py",
            "git add -f scripts/learning-v2-validate-executor.py",
            "git add -f scripts/learning-v2-apply-guardrails.py",
            "git add -f scripts/learning-v2-auto-apply-executor.py",
            "git add -f scripts/learning-v2-post-apply-validator.py",
            "git add -f scripts/learning-v2-outcome-recorder.py",
            "git add -f scripts/learning-v2-mode.py",
            "git add -f scripts/learning-v2-doctor.py",
            "git add -f scripts/learning-v2-change-ledger.py",
            "git add -f scripts/learning-v2-release-planner.py",
            "git add -f scripts/learning-v2-deploy-observer.py",
            "git add -f learning-v2/CONSTITUTION.md learning-v2/deployment-policy.json",
        ],
        "release_gate_before_any_commit": [
            "doctor_result must be ok",
            "policy_mode must remain system_build_only or explicit release mode",
            "website source changes must be reviewed separately",
            "high-risk deletions must not be included",
            "Cloudflare Pages deployment trigger must be acknowledged",
            "commit/push must remain disabled unless explicitly switched",
        ],
    }

    out_json = SNAPSHOT_DIR / f"learning-v2-package-plan-{stamp()}.json"
    out_json.write_text(json.dumps(package_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out_md = SNAPSHOT_DIR / f"learning-v2-package-plan-{stamp()}.md"
    lines = []
    lines.append("# Learning V2 Package Plan")
    lines.append("")
    lines.append(f"- generated_at: `{package_plan['generated_at']}`")
    lines.append("- mode: `package_planning_only`")
    lines.append("- source_changed: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append(f"- recommended_strategy: `{package_plan['recommended_strategy']}`")
    lines.append("")
    lines.append("## Reason")
    lines.append("")
    lines.append(package_plan["reason"])
    lines.append("")
    lines.append("## V0.1 core scripts")
    lines.append("")
    for x in package_plan["v0_1_package"]["core_scripts"]:
        lines.append(f"- `{x}`")
    lines.append("")
    lines.append("## Optional support scripts")
    lines.append("")
    for x in package_plan["v0_1_package"]["support_scripts_optional"]:
        lines.append(f"- `{x}`")
    lines.append("")
    lines.append("## Config candidates")
    lines.append("")
    for x in package_plan["v0_1_package"]["config_candidates"]:
        lines.append(f"- `{x}`")
    lines.append("")
    lines.append("## Hold / do not package yet")
    lines.append("")
    for x in package_plan["v0_1_package"]["hold_data_files"]:
        lines.append(f"- `{x}`")
    lines.append("")
    lines.append("## Explicitly exclude")
    lines.append("")
    for x in package_plan["explicitly_exclude"]:
        lines.append(f"- {x}")
    lines.append("")
    lines.append("## Future commands preview only")
    lines.append("")
    lines.append("```bash")
    for x in package_plan["future_git_commands_preview_only"]:
        lines.append(x)
    lines.append("```")
    lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")

    state["last_package_plan"] = {
        "at": now_iso(),
        "snapshot_json": str(out_json),
        "snapshot_report": str(out_md),
        "recommended_strategy": package_plan["recommended_strategy"],
        "core_scripts_count": len(core),
        "support_scripts_count": len(support),
        "source_changed": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }
    state["next_action"] = "Review package plan. Do not run git add/commit/push yet."
    state["updated_at"] = now_iso()
    save_state(state)

    print("package_planner_result = ok")
    print("source_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("snapshot_json =", out_json)
    print("snapshot_report =", out_md)
    print("recommended_strategy =", package_plan["recommended_strategy"])
    print("core_scripts_count =", len(core))
    print("support_scripts_count =", len(support))
    print("config_candidates_count =", len(learning_v2_config_candidates))
    print("hold_data_files_count =", len(learning_v2_data_hold))

if __name__ == "__main__":
    main()
