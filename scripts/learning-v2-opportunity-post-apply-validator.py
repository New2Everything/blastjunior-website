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

VALIDATOR_ID = "learning-v2-opportunity-post-apply-validator-v0"
TARGET_FILE = WORKSPACE / "public/assets/css/site.css"
TARGET_REL = "public/assets/css/site.css"
EXPECTED_IMPORT = '@import url("/styles.css");'

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

def latest_apply_report():
    files = sorted(
        REPORT_DIR.glob("opportunity-controlled-apply-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None

def latest_discovery_report():
    files = sorted(
        REPORT_DIR.glob("design-opportunity-discovery-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None

def run(cmd):
    return subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

def main():
    failures = []
    warnings = []

    apply_path = latest_apply_report()
    if not apply_path:
        failures.append("no_apply_report_found")
        apply_report = {}
    else:
        apply_report = load_json(apply_path, default={}) or {}

    if apply_report.get("mode") != "apply":
        failures.append(f"latest_apply_mode_not_apply:{apply_report.get('mode')}")

    if apply_report.get("applied") is not True:
        failures.append("latest_apply_not_marked_applied_true")

    if not TARGET_FILE.exists():
        failures.append(f"target_file_missing:{TARGET_REL}")
        content = ""
    else:
        content = TARGET_FILE.read_text(encoding="utf-8", errors="ignore")

    if EXPECTED_IMPORT not in content:
        failures.append("expected_import_missing")

    if "learning-v2 repair: missing asset reference" not in content:
        failures.append("expected_repair_marker_missing")

    # Re-run discovery after apply to confirm quality.missing_asset_reference is resolved.
    discovery_run = run(["python3", "scripts/learning-v2-design-opportunity-discoverer.py"])
    if discovery_run.returncode != 0:
        failures.append(f"discovery_rerun_failed:{discovery_run.returncode}")

    discovery_path = latest_discovery_report()
    discovery = load_json(discovery_path, default={}) or {} if discovery_path else {}

    quality_candidates = discovery.get("quality_bug_candidates") or []
    still_missing_asset = [
        c for c in quality_candidates
        if c.get("target_family") == "quality.missing_asset_reference"
    ]

    if still_missing_asset:
        failures.append("quality_missing_asset_reference_still_reported")

    # Check git status only for controlled target.
    status_run = run(["git", "status", "--short", "--", TARGET_REL])
    controlled_status = status_run.stdout.strip()

    if controlled_status not in {f"?? {TARGET_REL}", f"A  {TARGET_REL}", f"?? {TARGET_REL}\n"}:
        if controlled_status:
            warnings.append(f"unexpected_target_git_status:{controlled_status}")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "validator_id": VALIDATOR_ID,
        "result": result,
        "source_apply_report": str(apply_path) if apply_path else None,
        "post_apply_discovery_report": str(discovery_path) if discovery_path else None,
        "target_file": TARGET_REL,
        "target_file_exists": TARGET_FILE.exists(),
        "expected_import_present": EXPECTED_IMPORT in content,
        "repair_marker_present": "learning-v2 repair: missing asset reference" in content,
        "quality_missing_asset_reference_still_reported": bool(still_missing_asset),
        "quality_bug_candidates_count_after_apply": len(quality_candidates),
        "controlled_target_git_status": controlled_status,
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "website_files_changed": True,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
        },
        "recommended_next_stage": "outcome_recording" if result == "ok" else "repair_revision",
    }

    out_json = REPORT_DIR / f"opportunity-post-apply-validator-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"opportunity-post-apply-validator-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Opportunity Post-Apply Validator",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- validator_id: `{VALIDATOR_ID}`",
        f"- result: `{result}`",
        f"- source_apply_report: `{payload['source_apply_report']}`",
        f"- post_apply_discovery_report: `{payload['post_apply_discovery_report']}`",
        f"- target_file: `{TARGET_REL}`",
        f"- target_file_exists: `{str(payload['target_file_exists']).lower()}`",
        f"- expected_import_present: `{str(payload['expected_import_present']).lower()}`",
        f"- repair_marker_present: `{str(payload['repair_marker_present']).lower()}`",
        f"- quality_missing_asset_reference_still_reported: `{str(payload['quality_missing_asset_reference_still_reported']).lower()}`",
        f"- quality_bug_candidates_count_after_apply: `{payload['quality_bug_candidates_count_after_apply']}`",
        f"- controlled_target_git_status: `{controlled_status}`",
        f"- recommended_next_stage: `{payload['recommended_next_stage']}`",
        "",
        "## Failures",
        "",
    ]

    lines += [f"- {f}" for f in failures] if failures else ["- none"]

    lines += [
        "",
        "## Warnings",
        "",
    ]

    lines += [f"- {w}" for w in warnings] if warnings else ["- none"]

    lines += [
        "",
        "## Safety",
        "",
        "- website_files_changed: `true`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
        "- restore_cloudflare_auto_deploy: `false`",
        "",
    ]

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("opportunity_post_apply_validator =", result)
    print("target_file_exists =", str(payload["target_file_exists"]).lower())
    print("expected_import_present =", str(payload["expected_import_present"]).lower())
    print("repair_marker_present =", str(payload["repair_marker_present"]).lower())
    print("quality_missing_asset_reference_still_reported =", str(payload["quality_missing_asset_reference_still_reported"]).lower())
    print("quality_bug_candidates_count_after_apply =", payload["quality_bug_candidates_count_after_apply"])
    print("controlled_target_git_status =", controlled_status)
    print("recommended_next_stage =", payload["recommended_next_stage"])
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
