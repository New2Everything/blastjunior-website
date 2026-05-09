#!/usr/bin/env python3
import argparse
import importlib.util
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
FREEZE_DIR = BASE / "freezes"
OUTCOMES = BASE / "outcomes.jsonl"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
FREEZE_DIR.mkdir(parents=True, exist_ok=True)

RECORDER_ID = "learning-v2-opportunity-outcome-recorder-v0"
TARGET_FAMILY = "quality.missing_asset_reference"
TARGET_FILE = "public/assets/css/site.css"
EXPECTED_MARKER = "learning-v2 repair: missing asset reference"
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

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def latest_report(pattern):
    files = sorted(REPORT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None, {}
    p = files[0]
    return p, load_json(p, default={})

def discovery_quality_bug_count(discovery):
    value = discovery.get("quality_bug_candidates_count")
    if isinstance(value, int):
        return value
    return len(discovery.get("quality_bug_candidates") or [])

def discovery_next_target_family(discovery):
    value = discovery.get("recommended_target_family")
    if value:
        return value
    candidate = discovery.get("recommended_candidate") or {}
    return candidate.get("target_family")

def run(cmd):
    return subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

def load_release_gate_module():
    path = WORKSPACE / "scripts/learning-v2-release-gate.py"
    spec = importlib.util.spec_from_file_location("learning_v2_release_gate_runtime", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def git_head():
    p = run(["git", "rev-parse", "--short", "HEAD"])
    return p.stdout.strip()

def git_head_subject():
    p = run(["git", "log", "-1", "--pretty=%s"])
    return p.stdout.strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Record outcome and close dirty freeze.")
    args = ap.parse_args()

    mode = "apply" if args.apply else "dry_run"
    run_stamp = stamp()

    failures = []
    warnings = []

    state = load_json(STATE, default={}) or {}

    discovery_path, discovery = latest_report("design-opportunity-discovery-*.json")
    validator_path, validator = latest_report("opportunity-post-apply-validator-*.json")
    acceptance_path, acceptance = latest_report("opportunity-business-acceptance-*.json")

    head = git_head()
    subject = git_head_subject()

    if head != "8bf0c72":
        warnings.append(f"head_is_not_expected_8bf0c72:{head}")

    if "Repair missing site stylesheet asset" not in subject:
        warnings.append(f"head_subject_unexpected:{subject}")

    target = WORKSPACE / TARGET_FILE
    if not target.exists():
        failures.append(f"target_file_missing:{TARGET_FILE}")
        content = ""
    else:
        content = target.read_text(encoding="utf-8", errors="ignore")

    if EXPECTED_MARKER not in content:
        failures.append("target_marker_missing")
    if EXPECTED_IMPORT not in content:
        failures.append("target_import_missing")

    if not validator_path:
        failures.append("missing_post_apply_validator_report")
    else:
        if validator.get("result") != "ok":
            failures.append(f"post_apply_validator_not_ok:{validator.get('result')}")
        if validator.get("target_file") != TARGET_FILE:
            failures.append(f"validator_target_unexpected:{validator.get('target_file')}")
        if validator.get("quality_missing_asset_reference_still_reported") is not False:
            failures.append("missing_asset_still_reported")
        if validator.get("quality_bug_candidates_count_after_apply") != 0:
            failures.append(f"quality_bug_count_after_apply_not_zero:{validator.get('quality_bug_candidates_count_after_apply')}")

    discovery_quality_count = discovery_quality_bug_count(discovery) if discovery_path else None
    discovery_next_family = discovery_next_target_family(discovery) if discovery_path else None

    if not discovery_path:
        failures.append("missing_discovery_report")
    else:
        if discovery_quality_count != 0:
            failures.append(f"discovery_quality_bug_count_not_zero:{discovery_quality_count}")
        if discovery.get("recommended_lane") != "design_capability_scan":
            warnings.append(f"discovery_next_lane_unexpected:{discovery.get('recommended_lane')}")

    if not acceptance_path:
        failures.append("missing_business_acceptance_report")
    else:
        if acceptance.get("result") != "ok":
            failures.append(f"business_acceptance_not_ok:{acceptance.get('result')}")
        if acceptance.get("mode") != "apply":
            failures.append(f"business_acceptance_mode_not_apply:{acceptance.get('mode')}")
        if acceptance.get("state_written") is not True:
            failures.append("business_acceptance_state_not_written")

    status_target = run(["git", "status", "--short", "--", TARGET_FILE]).stdout.strip()
    if status_target:
        failures.append(f"target_file_still_dirty:{status_target}")

    staged = run(["git", "diff", "--cached", "--name-status"]).stdout.strip()
    if staged:
        failures.append(f"index_not_empty:{staged}")

    release_gate = load_release_gate_module()
    entries = release_gate.current_dirty_entries()
    business = [x for x in entries if x.get("class") == "business_source_blocked"]

    if business:
        failures.append(f"business_dirty_still_present:{[x.get('path') for x in business]}")

    result = "ok" if not failures else "blocked"

    outcome = {
        "recorded_at": now_iso(),
        "recorder_id": RECORDER_ID,
        "target_family": TARGET_FAMILY,
        "target_file": TARGET_FILE,
        "result": "resolved" if result == "ok" else "blocked",
        "business_commit": head,
        "business_commit_subject": subject,
        "quality_missing_asset_reference_still_reported": validator.get("quality_missing_asset_reference_still_reported"),
        "quality_bug_candidates_count_after_apply": validator.get("quality_bug_candidates_count_after_apply"),
        "next_recommended_lane": discovery.get("recommended_lane"),
        "next_recommended_target_family": discovery_next_family,
        "source_reports": {
            "discovery": str(discovery_path) if discovery_path else None,
            "post_apply_validator": str(validator_path) if validator_path else None,
            "business_acceptance": str(acceptance_path) if acceptance_path else None,
        },
        "git_push": False,
        "deploy": False,
    }

    freeze_path = None
    state_written = False
    outcome_written = False

    if args.apply and result == "ok":
        freeze_path = FREEZE_DIR / f"dirty-freeze-opportunity-outcome-complete-{run_stamp}.json"

        new_freeze = {
            "generated_at": now_iso(),
            "freeze_type": "opportunity_business_change_completed_clean_freeze",
            "recorder_id": RECORDER_ID,
            "target_family": TARGET_FAMILY,
            "target_file": TARGET_FILE,
            "business_commit": head,
            "reason": "Close controlled opportunity business change after successful local business commit and post-commit validation.",
            "business_source_blocked": business,
            "summary": {
                "total_dirty": len(entries),
                "business_source_blocked_count": len(business),
                "closed_target_file": TARGET_FILE,
                "closed_business_commit": head,
                "commit_allowed": False,
                "push_allowed": False,
                "deploy_allowed": False,
            },
            "source_reports": outcome["source_reports"],
            "policy": {
                "source_written_by_outcome_recorder": False,
                "state_written": True,
                "outcome_written": True,
                "git_commit": False,
                "git_push": False,
                "deploy": False,
            },
        }

        save_json(freeze_path, new_freeze)

        with OUTCOMES.open("a", encoding="utf-8") as f:
            f.write(json.dumps(outcome, ensure_ascii=False) + "\n")
        outcome_written = True

        state["last_dirty_freeze"] = {
            "generated_at": new_freeze["generated_at"],
            "path": str(freeze_path),
            "summary": new_freeze["summary"],
        }

        state["last_opportunity_outcome"] = {
            "generated_at": outcome["recorded_at"],
            "recorder_id": RECORDER_ID,
            "target_family": TARGET_FAMILY,
            "target_file": TARGET_FILE,
            "result": outcome["result"],
            "business_commit": head,
            "freeze_path": str(freeze_path),
            "source_reports": outcome["source_reports"],
        }

        state["current_topic"] = None
        state["current_stage"] = None
        state["current_target_family"] = None

        save_json(STATE, state)
        state_written = True

    payload = {
        "generated_at": now_iso(),
        "recorder_id": RECORDER_ID,
        "mode": mode,
        "result": result,
        "target_family": TARGET_FAMILY,
        "target_file": TARGET_FILE,
        "business_commit": head,
        "business_commit_subject": subject,
        "target_file_dirty_status": status_target,
        "index_status": staged,
        "business_dirty_count": len(business),
        "outcome": outcome,
        "freeze_path": str(freeze_path) if freeze_path else None,
        "state_written": state_written,
        "outcome_written": outcome_written,
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
        },
        "recommended_next_stage": "next_opportunity_selection" if result == "ok" else "outcome_revision",
    }

    out_json = REPORT_DIR / f"opportunity-outcome-recorder-{run_stamp}.json"
    out_md = SNAPSHOT_DIR / f"opportunity-outcome-recorder-{run_stamp}.md"

    save_json(out_json, payload)

    lines = [
        "# Learning V2 Opportunity Outcome Recorder",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- recorder_id: `{RECORDER_ID}`",
        f"- mode: `{mode}`",
        f"- result: `{result}`",
        f"- target_family: `{TARGET_FAMILY}`",
        f"- target_file: `{TARGET_FILE}`",
        f"- business_commit: `{head}`",
        f"- business_commit_subject: {subject}",
        f"- business_dirty_count: `{len(business)}`",
        f"- state_written: `{str(state_written).lower()}`",
        f"- outcome_written: `{str(outcome_written).lower()}`",
        f"- freeze_path: `{payload['freeze_path']}`",
        f"- recommended_next_stage: `{payload['recommended_next_stage']}`",
        "",
        "## Outcome",
        "",
        f"- result: `{outcome['result']}`",
        f"- next_recommended_lane: `{outcome.get('next_recommended_lane')}`",
        f"- next_recommended_target_family: `{outcome.get('next_recommended_target_family')}`",
        "",
        "## Failures",
        "",
    ]

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

    print("opportunity_outcome_recorder =", result)
    print("mode =", mode)
    print("target_family =", TARGET_FAMILY)
    print("target_file =", TARGET_FILE)
    print("business_commit =", head)
    print("business_dirty_count =", len(business))
    print("state_written =", str(state_written).lower())
    print("outcome_written =", str(outcome_written).lower())
    print("freeze_path =", payload["freeze_path"])
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
