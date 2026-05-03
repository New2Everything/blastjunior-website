#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
SCRIPTS = WORKSPACE / "scripts"
DISPATCH = SCRIPTS / "learning-v2-dispatch.py"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

REQUIRED_SCRIPTS = [
    "learning-v2-topic-selector.py",
    "learning-v2-dispatch.py",
    "learning-v2-discover-executor.py",
    "learning-v2-validate-executor.py",
    "learning-v2-apply-guardrails.py",
    "learning-v2-auto-apply-executor.py",
    "learning-v2-post-apply-validator.py",
    "learning-v2-outcome-recorder.py",
    "learning-v2-validate-blocked-resolver.py",
    "learning-v2-track-complete-finalizer.py",
    "learning-v2-nav-discover-executor.py",
    "learning-v2-nav-proposal-executor.py",
    "learning-v2-mode.py",
    "learning-v2-control.py",
    "learning-v2-local-exclude-manager.py",
    "learning-v2-system-manifest.py",
    "learning-v2-package-planner.py",
]

REQUIRED_HOOK_MARKERS = [
    "empty state selector bridge",
    "simplicity discover executor hook",
    "nav discover executor hook",
    "nav proposal executor hook",
    "validate executor hook",
    "apply guardrails hook",
    "auto apply executor hook",
    "post apply validator hook",
    "outcome recorder hook",
    "validate blocked resolver hook",
    "track complete finalizer hook",
    "source write policy gate",
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def run(cmd):
    r = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return {
        "cmd": " ".join(cmd),
        "returncode": r.returncode,
        "stdout": r.stdout.strip(),
        "stderr": r.stderr.strip(),
    }

def load_state():
    return json.loads(STATE.read_text(encoding="utf-8"))

def main():
    state = load_state()
    dispatch_text = DISPATCH.read_text(encoding="utf-8", errors="ignore") if DISPATCH.exists() else ""

    scripts_status = []
    for name in REQUIRED_SCRIPTS:
        p = SCRIPTS / name
        scripts_status.append({
            "name": name,
            "exists": p.exists(),
            "executable": p.exists() and bool(p.stat().st_mode & 0o111),
        })

    hooks_status = []
    for marker in REQUIRED_HOOK_MARKERS:
        hooks_status.append({
            "marker": marker,
            "present": marker in dispatch_text,
        })

    git_status = run(["git", "status", "--short"])

    reports = sorted(REPORT_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]

    result = {
        "generated_at": now_iso(),
        "current_topic": state.get("current_topic"),
        "current_stage": state.get("current_stage"),
        "current_target_family": state.get("current_target_family"),
        "next_action": state.get("next_action"),
        "policy": state.get("self_evolution_policy"),
        "applied_targets_count": len(state.get("applied_targets") or []),
        "applied_targets": state.get("applied_targets") or [],
        "disabled_target_families": state.get("disabled_target_families") or [],
        "completed_tracks": state.get("completed_tracks") or [],
        "scripts_status": scripts_status,
        "hooks_status": hooks_status,
        "git_status_short": git_status,
        "recent_reports": [str(p) for p in reports],
    }

    missing_scripts = [x["name"] for x in scripts_status if not x["exists"]]
    missing_hooks = [x["marker"] for x in hooks_status if not x["present"]]

    result["health"] = {
        "missing_scripts": missing_scripts,
        "missing_hooks": missing_hooks,
        "ok": not missing_scripts and not missing_hooks,
    }

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    snapshot = SNAPSHOT_DIR / f"learning-v2-doctor-{stamp}.json"
    snapshot.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = SNAPSHOT_DIR / f"learning-v2-doctor-{stamp}.md"
    lines = []
    lines.append("# Learning V2 Doctor Report")
    lines.append("")
    lines.append(f"- generated_at: `{result['generated_at']}`")
    lines.append(f"- current_topic: `{result['current_topic']}`")
    lines.append(f"- current_stage: `{result['current_stage']}`")
    lines.append(f"- current_target_family: `{result['current_target_family']}`")
    lines.append(f"- policy_mode: `{(result.get('policy') or {}).get('mode')}`")
    lines.append(f"- allow_source_changes: `{(result.get('policy') or {}).get('allow_source_changes')}`")
    lines.append(f"- allow_git_commit: `{(result.get('policy') or {}).get('allow_git_commit')}`")
    lines.append(f"- allow_deploy: `{(result.get('policy') or {}).get('allow_deploy')}`")
    lines.append(f"- health_ok: `{result['health']['ok']}`")
    lines.append("")
    lines.append("## Missing scripts")
    lines.append("")
    lines.append("\n".join(f"- {x}" for x in missing_scripts) if missing_scripts else "none")
    lines.append("")
    lines.append("## Missing hooks")
    lines.append("")
    lines.append("\n".join(f"- {x}" for x in missing_hooks) if missing_hooks else "none")
    lines.append("")
    lines.append("## Applied targets")
    lines.append("")
    if result["applied_targets"]:
        for x in result["applied_targets"]:
            lines.append(f"- `{x}`")
    else:
        lines.append("none")
    lines.append("")
    lines.append("## Disabled target families")
    lines.append("")
    if result["disabled_target_families"]:
        for x in result["disabled_target_families"]:
            lines.append(f"- `{x}`")
    else:
        lines.append("none")
    lines.append("")
    lines.append("## Git status short")
    lines.append("")
    lines.append("```")
    lines.append(git_status["stdout"] or "(empty)")
    lines.append("```")
    lines.append("")
    lines.append("## Recent reports")
    lines.append("")
    for p in reports:
        lines.append(f"- `{p}`")
    lines.append("")
    report.write_text("\n".join(lines), encoding="utf-8")

    print("doctor_result =", "ok" if result["health"]["ok"] else "needs_attention")
    print("snapshot_json =", snapshot)
    print("snapshot_report =", report)
    print("policy_mode =", (result.get("policy") or {}).get("mode"))
    print("allow_source_changes =", (result.get("policy") or {}).get("allow_source_changes"))
    print("missing_scripts =", len(missing_scripts))
    print("missing_hooks =", len(missing_hooks))
    print("applied_targets_count =", result["applied_targets_count"])
    print("disabled_target_families =", result["disabled_target_families"])

if __name__ == "__main__":
    main()
