#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

GATE_ID = "learning-v2-system-only-commit-gate-v0"

ALLOWED_STAGED_PREFIXES = (
    "scripts/learning-v2-",
)

ALLOWED_STAGED_EXACT = {
    "learning-v2/RUNBOOK.md",
    "learning-v2/push-approval-state.json",
    "learning-v2/cloudflare-option-b-state.json",
}

FORBIDDEN_STAGED_PREFIXES = (
    "public/",
    "components/",
    "worker/",
    "artifacts/",
    "harness/",
    "blxst/",
    "learning-v2/reports/",
    "learning-v2/snapshots/",
    "learning-v2/backups/",
    "learning-v2/cache/",
)

FORBIDDEN_STAGED_EXACT = {
    "learning-v2/state.json",
    "learning-v2/experiments.jsonl",
    "learning-v2/outcomes.jsonl",
    "scripts/hourly-optimization.sh",
    "scripts/auto-optimization.sh",
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def run(cmd):
    p = subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def staged_paths():
    rc, out, err = run(["git", "diff", "--cached", "--name-only"])
    if rc != 0:
        raise RuntimeError(f"git diff --cached --name-only failed: {err}")
    return [x.strip() for x in out.splitlines() if x.strip()]

def staged_name_status():
    rc, out, err = run(["git", "diff", "--cached", "--name-status"])
    if rc != 0:
        raise RuntimeError(f"git diff --cached --name-status failed: {err}")
    return [x for x in out.splitlines() if x.strip()]

def is_allowed_staged(path):
    return path in ALLOWED_STAGED_EXACT or any(path.startswith(prefix) for prefix in ALLOWED_STAGED_PREFIXES)

def is_forbidden_staged(path):
    return path in FORBIDDEN_STAGED_EXACT or any(path.startswith(prefix) for prefix in FORBIDDEN_STAGED_PREFIXES)

def main():
    state = load_json(STATE, default={})
    commit_info = state.get("last_commit_plan") or {}
    audit_info = state.get("last_commit_plan_audit") or {}
    plan_path = Path(commit_info.get("json", ""))
    plan = load_json(plan_path, default={}) if plan_path.exists() else {}

    release_rc, release_out, release_err = run(["python3", "scripts/learning-v2-release-gate.py"])
    latest_release_reports = sorted(REPORT_DIR.glob("release-gate-*.json"))
    release_report_path = latest_release_reports[-1] if latest_release_reports else None
    release_report = load_json(release_report_path, default={}) if release_report_path else {}
    release_summary = release_report.get("summary") or {}

    stage_rc, stage_out, stage_err = run(["python3", "scripts/learning-v2-staging-guard.py"])
    latest_stage_reports = sorted(REPORT_DIR.glob("learning-v2-staging-guard-*.json"))
    stage_report_path = latest_stage_reports[-1] if latest_stage_reports else None
    stage_report = load_json(stage_report_path, default={}) if stage_report_path else {}

    staged = staged_paths()
    staged_status = staged_name_status()

    failures = []
    warnings = []

    if not staged:
        failures.append("no_staged_files")

    if not plan_path.exists():
        failures.append(f"missing_commit_plan:{plan_path}")

    if plan.get("dry_run_only") is not True:
        failures.append(f"commit_plan_not_dry_run_only:{plan.get('dry_run_only')}")

    decision = plan.get("decision") or {}
    if decision.get("commit_now") is not False:
        failures.append(f"commit_now_not_false:{decision.get('commit_now')}")
    if decision.get("push_now") is not False:
        failures.append(f"push_now_not_false:{decision.get('push_now')}")
    if decision.get("deploy_now") is not False:
        failures.append(f"deploy_now_not_false:{decision.get('deploy_now')}")

    if audit_info.get("result") != "ok":
        failures.append(f"commit_plan_audit_not_ok:{audit_info.get('result')}")

    audit_summary = audit_info.get("summary") or {}
    if audit_summary.get("business_paths_selected_count") != 0:
        failures.append(f"business_paths_selected_in_commit_plan:{audit_summary.get('business_paths_selected_count')}")

    if stage_report.get("result") != "ok":
        failures.append(f"staging_guard_not_ok:{stage_report.get('result')}")

    staged_not_allowed = [p for p in staged if not is_allowed_staged(p)]
    staged_forbidden = [p for p in staged if is_forbidden_staged(p)]

    if staged_not_allowed:
        failures.append("staged_paths_not_allowed_for_system_only_commit")
    if staged_forbidden:
        failures.append("forbidden_paths_staged")

    if release_summary.get("ok_for_system_build") is not True:
        failures.append(f"release_gate_system_build_not_ok:{release_summary.get('ok_for_system_build')}")

    if release_summary.get("ok_for_deploy") is not False:
        failures.append(f"release_gate_deploy_not_false:{release_summary.get('ok_for_deploy')}")

    # A system-only commit may be staged while global ok_for_commit remains false,
    # because business source is dirty but not staged. This gate does not unlock commit.
    if release_summary.get("ok_for_commit") is not False:
        warnings.append(f"release_gate_commit_unexpectedly_true:{release_summary.get('ok_for_commit')}")

    hard_blocks = release_summary.get("hard_blocks") or []
    if "business_source_dirty_exists" in hard_blocks:
        warnings.append("global_release_gate_blocks_normal_commit_due_to_business_source_dirty")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "gate_id": GATE_ID,
        "result": result,
        "mode": "system_only_commit_gate",
        "commit_plan_json": str(plan_path),
        "commit_plan_audit_result": audit_info.get("result"),
        "business_paths_selected_count": audit_summary.get("business_paths_selected_count"),
        "release_gate_report": str(release_report_path) if release_report_path else None,
        "release_gate_summary": release_summary,
        "staging_guard_report": str(stage_report_path) if stage_report_path else None,
        "staged_count": len(staged),
        "staged_paths": staged,
        "staged_name_status": staged_status,
        "staged_not_allowed": staged_not_allowed,
        "staged_forbidden": staged_forbidden,
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "gate_only": True,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "business_source_commit_allowed": False,
            "system_only_commit_review_ready": result == "ok",
        },
        "recommended_next_step": (
            "review staged diff summary; commit remains manual-only and push/deploy remain forbidden"
            if result == "ok"
            else "fix staged set before any commit"
        ),
    }

    out_json = REPORT_DIR / f"learning-v2-system-only-commit-gate-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-system-only-commit-gate-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 System Only Commit Gate")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- mode: `{payload['mode']}`")
    lines.append(f"- staged_count: `{len(staged)}`")
    lines.append(f"- commit_plan_audit_result: `{audit_info.get('result')}`")
    lines.append(f"- business_paths_selected_count: `{audit_summary.get('business_paths_selected_count')}`")
    lines.append(f"- release_ok_for_system_build: `{release_summary.get('ok_for_system_build')}`")
    lines.append(f"- release_ok_for_commit: `{release_summary.get('ok_for_commit')}`")
    lines.append(f"- release_ok_for_deploy: `{release_summary.get('ok_for_deploy')}`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Staged summary")
    for row in staged_status[:250]:
        lines.append(f"- `{row}`")
    if len(staged_status) > 250:
        lines.append(f"- ... truncated {len(staged_status) - 250} more")
    lines.append("")
    lines.append("## Failures")
    if failures:
        for f in failures:
            lines.append(f"- {f}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Warnings")
    if warnings:
        for w in warnings:
            lines.append(f"- {w}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Recommended next step")
    lines.append(payload["recommended_next_step"])
    lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("system_only_commit_gate =", result)
    print("mode = system_only_commit_gate")
    print("staged_count =", len(staged))
    print("commit_plan_audit_result =", audit_info.get("result"))
    print("business_paths_selected_count =", audit_summary.get("business_paths_selected_count"))
    print("release_ok_for_system_build =", release_summary.get("ok_for_system_build"))
    print("release_ok_for_commit =", release_summary.get("ok_for_commit"))
    print("release_ok_for_deploy =", release_summary.get("ok_for_deploy"))
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("recommended_next_step =", payload["recommended_next_step"])
    print("report_json =", out_json)
    print("report_md =", out_md)

    if warnings:
        print("warnings =", json.dumps(warnings, ensure_ascii=False))
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
