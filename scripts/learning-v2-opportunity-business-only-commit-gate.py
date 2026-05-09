#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

GATE_ID = "learning-v2-opportunity-business-only-commit-gate-v0"
TARGET_REL = "public/assets/css/site.css"
EXPECTED_IMPORT = '@import url("/styles.css");'
EXPECTED_MARKER = "learning-v2 repair: missing asset reference"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def latest_report(pattern):
    files = sorted(
        REPORT_DIR.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        return None, {}
    p = files[0]
    return p, load_json(p, default={})

def run(cmd):
    return subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

def staged_rows():
    p = run(["git", "diff", "--cached", "--name-status"])
    rows = []
    for line in p.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append({"status": parts[0].strip(), "path": parts[-1].strip()})
    return rows

def main():
    failures = []
    warnings = []

    acceptance_path, acceptance = latest_report("opportunity-business-acceptance-*.json")
    validator_path, validator = latest_report("opportunity-post-apply-validator-*.json")

    target = WORKSPACE / TARGET_REL

    if not acceptance_path:
        failures.append("missing_opportunity_business_acceptance_report")
    else:
        if acceptance.get("result") != "ok":
            failures.append(f"acceptance_not_ok:{acceptance.get('result')}")
        if acceptance.get("mode") != "apply":
            failures.append(f"acceptance_mode_not_apply:{acceptance.get('mode')}")
        if acceptance.get("target_file") != TARGET_REL:
            failures.append(f"acceptance_target_unexpected:{acceptance.get('target_file')}")
        if acceptance.get("state_written") is not True:
            failures.append("acceptance_state_written_not_true")

    if not validator_path:
        failures.append("missing_post_apply_validator_report")
    else:
        if validator.get("result") != "ok":
            failures.append(f"post_apply_validator_not_ok:{validator.get('result')}")
        if validator.get("target_file") != TARGET_REL:
            failures.append(f"post_apply_target_unexpected:{validator.get('target_file')}")
        if validator.get("quality_missing_asset_reference_still_reported") is not False:
            failures.append("missing_asset_still_reported_after_apply")

    if not target.exists():
        failures.append(f"target_file_missing:{TARGET_REL}")
        content = ""
    else:
        content = target.read_text(encoding="utf-8", errors="ignore")

    if EXPECTED_IMPORT not in content:
        failures.append("target_missing_expected_import")
    if EXPECTED_MARKER not in content:
        failures.append("target_missing_expected_marker")

    rows = staged_rows()
    staged_paths = {r["path"] for r in rows}

    if not staged_paths:
        failures.append("no_staged_files")
    elif staged_paths != {TARGET_REL}:
        failures.append(f"unexpected_staged_paths:{sorted(staged_paths)}")

    target_rows = [r for r in rows if r["path"] == TARGET_REL]
    if target_rows:
        allowed_status = {"A", "AM"}
        if target_rows[0]["status"] not in allowed_status:
            failures.append(f"target_staged_status_unexpected:{target_rows[0]['status']}")

    release = run(["python3", "scripts/learning-v2-release-gate.py"])
    release_report_path = None
    release_summary = {}

    for line in release.stdout.splitlines():
        if line.startswith("release_gate_report ="):
            release_report_path = line.split("=", 1)[1].strip()

    if release_report_path:
        data = load_json(release_report_path, default={}) or {}
        release_summary = data.get("summary") or data
    else:
        warnings.append("release_gate_report_not_found")

    # When the accepted opportunity business target is staged, the global release gate may
    # temporarily report business_freeze_stable=false because the dirty representation changes
    # from an untracked directory such as public/assets/ to the staged file path.
    # This dedicated gate may tolerate that only if the staged set is exactly the accepted target.
    staged_target_only = staged_paths == {TARGET_REL}
    release_hard_blocks = set(release_summary.get("hard_blocks") or [])
    tolerated_release_blocks = {
        "business_source_dirty_exists",
        "business_source_dirty_changed_since_freeze",
    }
    release_blocked_only_by_accepted_staged_target = (
        staged_target_only
        and release_summary.get("business_source_dirty_count") == 1
        and release_hard_blocks.issubset(tolerated_release_blocks)
    )

    if release_summary.get("ok_for_system_build") is not True and not release_blocked_only_by_accepted_staged_target:
        failures.append(f"release_gate_system_build_not_true:{release_summary.get('ok_for_system_build')}")
    elif release_summary.get("ok_for_system_build") is not True:
        warnings.append("release_gate_system_build_false_only_because_accepted_target_is_staged")

    if release_summary.get("business_freeze_stable") is not True and not release_blocked_only_by_accepted_staged_target:
        failures.append("business_freeze_not_stable")
    elif release_summary.get("business_freeze_stable") is not True:
        warnings.append("business_freeze_false_only_because_accepted_target_is_staged")

    if release_summary.get("business_source_dirty_count") != 1:
        failures.append(f"business_source_dirty_count_unexpected:{release_summary.get('business_source_dirty_count')}")

    # Normal release gate should still block commit/deploy globally.
    if release_summary.get("ok_for_commit") is not False:
        warnings.append(f"release_gate_commit_unexpected:{release_summary.get('ok_for_commit')}")
    if release_summary.get("ok_for_deploy") is not False:
        warnings.append(f"release_gate_deploy_unexpected:{release_summary.get('ok_for_deploy')}")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "gate_id": GATE_ID,
        "result": result,
        "target_file": TARGET_REL,
        "staged_rows": rows,
        "staged_count": len(staged_paths),
        "acceptance_report": str(acceptance_path) if acceptance_path else None,
        "post_apply_validator_report": str(validator_path) if validator_path else None,
        "release_gate_report": release_report_path,
        "release_gate_summary": release_summary,
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
        },
        "recommended_next_step": (
            "business-only staged set is ready for manual local commit review; push/deploy remain forbidden"
            if result == "ok"
            else "fix opportunity business staged set before commit"
        ),
    }

    out_json = REPORT_DIR / f"learning-v2-opportunity-business-only-commit-gate-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-opportunity-business-only-commit-gate-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Opportunity Business Only Commit Gate",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- gate_id: `{GATE_ID}`",
        f"- result: `{result}`",
        f"- target_file: `{TARGET_REL}`",
        f"- staged_count: `{len(staged_paths)}`",
        f"- recommended_next_step: {payload['recommended_next_step']}",
        "",
        "## Staged rows",
        "",
    ]

    if rows:
        for r in rows:
            lines.append(f"- `{r['status']}    {r['path']}`")
    else:
        lines.append("- none")

    lines += ["", "## Failures", ""]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]

    lines += ["", "## Warnings", ""]
    lines += [f"- {x}" for x in warnings] if warnings else ["- none"]

    lines += [
        "",
        "## Safety",
        "",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
        "- restore_cloudflare_auto_deploy: `false`",
        "",
    ]

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("opportunity_business_only_commit_gate =", result)
    print("target_file =", TARGET_REL)
    print("staged_count =", len(staged_paths))
    print("recommended_next_step =", payload["recommended_next_step"])
    print("report_json =", out_json)
    print("report_md =", out_md)
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
    if warnings:
        print("warnings =", json.dumps(warnings, ensure_ascii=False, indent=2))
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
