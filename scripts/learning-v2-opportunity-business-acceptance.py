#!/usr/bin/env python3
import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
FREEZE_DIR = BASE / "freezes"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
FREEZE_DIR.mkdir(parents=True, exist_ok=True)

ACCEPTANCE_ID = "learning-v2-opportunity-business-acceptance-v0"
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
    return json.loads(p.read_text(encoding="utf-8"))

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def latest_report(pattern):
    files = sorted(REPORT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None, {}
    p = files[0]
    return p, load_json(p, default={})

def report_flag_false(report, key):
    if report.get(key) is False:
        return True
    policy = report.get("policy") or {}
    return policy.get(key) is False

def load_release_gate_module():
    path = WORKSPACE / "scripts/learning-v2-release-gate.py"
    spec = importlib.util.spec_from_file_location("learning_v2_release_gate_runtime", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def close_permissions(state):
    state["allow_source_changes"] = False
    state["allow_git_commit"] = False
    state["allow_deploy"] = False

    policy = state.get("self_evolution_policy") or {}
    policy["source_changes_allowed"] = False
    policy["git_commit_allowed"] = False
    policy["git_push_allowed"] = False
    policy["deploy_allowed"] = False
    state["self_evolution_policy"] = policy
    return state

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Record acceptance into learning-v2 state/freeze.")
    args = ap.parse_args()

    mode = "apply" if args.apply else "dry_run"
    run_stamp = stamp()

    failures = []
    warnings = []

    state = load_json(STATE, default={}) or {}
    policy = state.get("self_evolution_policy") or {}

    apply_path, apply_report = latest_report("opportunity-controlled-apply-*.json")
    validator_path, validator = latest_report("opportunity-post-apply-validator-*.json")
    discovery_path, discovery = latest_report("design-opportunity-discovery-*.json")

    target = WORKSPACE / TARGET_REL

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if not apply_path:
        failures.append("missing_controlled_apply_report")
    else:
        if apply_report.get("mode") != "apply":
            failures.append(f"controlled_apply_mode_not_apply:{apply_report.get('mode')}")
        if apply_report.get("applied") is not True:
            failures.append("controlled_apply_applied_not_true")
        if apply_report.get("target_file") != TARGET_REL:
            failures.append(f"controlled_apply_target_unexpected:{apply_report.get('target_file')}")
        if not report_flag_false(apply_report, "git_push"):
            failures.append("controlled_apply_git_push_not_false")
        if not report_flag_false(apply_report, "deploy"):
            failures.append("controlled_apply_deploy_not_false")

    if not validator_path:
        failures.append("missing_post_apply_validator_report")
    else:
        if validator.get("result") != "ok":
            failures.append(f"post_apply_validator_not_ok:{validator.get('result')}")
        if validator.get("target_file") != TARGET_REL:
            failures.append(f"post_apply_target_unexpected:{validator.get('target_file')}")
        if validator.get("target_file_exists") is not True:
            failures.append("post_apply_target_file_exists_not_true")
        if validator.get("expected_import_present") is not True:
            failures.append("post_apply_expected_import_not_true")
        if validator.get("repair_marker_present") is not True:
            failures.append("post_apply_repair_marker_not_true")
        if validator.get("quality_missing_asset_reference_still_reported") is not False:
            failures.append("missing_asset_still_reported_after_apply")

    if not target.exists():
        failures.append(f"target_file_missing:{TARGET_REL}")
        content = ""
    else:
        content = target.read_text(encoding="utf-8", errors="ignore")

    if EXPECTED_IMPORT not in content:
        failures.append("target_content_missing_expected_import")
    if EXPECTED_MARKER not in content:
        failures.append("target_content_missing_repair_marker")

    if TARGET_REL != "public/assets/css/site.css":
        failures.append("target_not_exact_expected_path")

    # Inspect current dirty entries using release gate runtime.
    release_gate = load_release_gate_module()
    entries = release_gate.current_dirty_entries()
    business = [x for x in entries if x.get("class") == "business_source_blocked"]
    freeze_compare = release_gate.compare_business_freeze(state, business)

    business_paths = sorted([x.get("path") for x in business if x.get("path")])
    new_business_paths = sorted([x.get("path") for x in freeze_compare.get("new_business_dirty", []) if x.get("path")])
    changed_paths = sorted([x.get("path") for x in freeze_compare.get("changed", []) if x.get("path")])
    missing_or_cleaned_paths = sorted([x.get("path") for x in freeze_compare.get("missing_or_cleaned", []) if x.get("path")])

    # Git may report an untracked directory as public/assets/ rather than the file.
    accepted_dirty_paths = sorted(set(new_business_paths + changed_paths))
    acceptable_dirty_path_sets = [
        [TARGET_REL],
        ["public/assets/"],
        ["public/assets/", TARGET_REL],
    ]

    if accepted_dirty_paths not in acceptable_dirty_path_sets:
        failures.append(f"accepted_dirty_paths_unexpected:{accepted_dirty_paths}")

    if missing_or_cleaned_paths:
        failures.append(f"missing_or_cleaned_business_paths_present:{missing_or_cleaned_paths}")

    result = "ok" if not failures else "blocked"
    state_written = False
    freeze_path = None

    if args.apply and result == "ok":
        freeze_path = FREEZE_DIR / f"dirty-freeze-opportunity-business-acceptance-{run_stamp}.json"

        new_freeze = {
            "generated_at": now_iso(),
            "freeze_type": "opportunity_controlled_business_change_acceptance",
            "acceptance_id": ACCEPTANCE_ID,
            "accepted_target_file": TARGET_REL,
            "accepted_dirty_paths": accepted_dirty_paths,
            "reason": "Accept opportunity pipeline controlled business change after post-apply validation.",
            "source_reports": {
                "controlled_apply": str(apply_path),
                "post_apply_validator": str(validator_path),
                "post_apply_discovery": str(discovery_path) if discovery_path else None,
            },
            "freeze_compare_before_acceptance": freeze_compare,
            "business_source_blocked": business,
            "summary": {
                "total_dirty": len(entries),
                "business_source_blocked_count": len(business),
                "accepted_dirty_paths": accepted_dirty_paths,
                "commit_allowed": False,
                "push_allowed": False,
                "deploy_allowed": False,
            },
            "policy": {
                "source_written_by_acceptance": False,
                "state_written": True,
                "git_commit": False,
                "git_push": False,
                "deploy": False,
            },
        }

        save_json(freeze_path, new_freeze)

        state["last_dirty_freeze"] = {
            "generated_at": new_freeze["generated_at"],
            "path": str(freeze_path),
            "summary": new_freeze["summary"],
        }

        state["last_opportunity_business_acceptance"] = {
            "generated_at": new_freeze["generated_at"],
            "acceptance_id": ACCEPTANCE_ID,
            "target_file": TARGET_REL,
            "accepted_dirty_paths": accepted_dirty_paths,
            "freeze_path": str(freeze_path),
            "source_reports": new_freeze["source_reports"],
        }

        close_permissions(state)
        save_json(STATE, state)
        state_written = True

    payload = {
        "generated_at": now_iso(),
        "acceptance_id": ACCEPTANCE_ID,
        "mode": mode,
        "result": result,
        "target_file": TARGET_REL,
        "controlled_apply_report": str(apply_path) if apply_path else None,
        "post_apply_validator_report": str(validator_path) if validator_path else None,
        "target_file_exists": target.exists(),
        "expected_import_present": EXPECTED_IMPORT in content,
        "repair_marker_present": EXPECTED_MARKER in content,
        "business_paths": business_paths,
        "accepted_dirty_paths": accepted_dirty_paths,
        "new_business_paths": new_business_paths,
        "changed_paths": changed_paths,
        "missing_or_cleaned_paths": missing_or_cleaned_paths,
        "state_written": state_written,
        "freeze_path": str(freeze_path) if freeze_path else None,
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "business_source_written": False,
            "state_written": state_written,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
        },
        "recommended_next_stage": "business_staging_review" if result == "ok" else "acceptance_revision",
    }

    out_json = REPORT_DIR / f"opportunity-business-acceptance-{run_stamp}.json"
    out_md = SNAPSHOT_DIR / f"opportunity-business-acceptance-{run_stamp}.md"
    save_json(out_json, payload)

    lines = [
        "# Learning V2 Opportunity Business Acceptance",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- acceptance_id: `{ACCEPTANCE_ID}`",
        f"- mode: `{mode}`",
        f"- result: `{result}`",
        f"- target_file: `{TARGET_REL}`",
        f"- target_file_exists: `{str(payload['target_file_exists']).lower()}`",
        f"- expected_import_present: `{str(payload['expected_import_present']).lower()}`",
        f"- repair_marker_present: `{str(payload['repair_marker_present']).lower()}`",
        f"- accepted_dirty_paths: `{accepted_dirty_paths}`",
        f"- state_written: `{str(state_written).lower()}`",
        f"- freeze_path: `{payload['freeze_path']}`",
        f"- recommended_next_stage: `{payload['recommended_next_stage']}`",
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
        "- business_source_written: `false`",
        f"- state_written: `{str(state_written).lower()}`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
        "- restore_cloudflare_auto_deploy: `false`",
        "",
    ]

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("opportunity_business_acceptance =", result)
    print("mode =", mode)
    print("target_file =", TARGET_REL)
    print("target_file_exists =", str(payload["target_file_exists"]).lower())
    print("expected_import_present =", str(payload["expected_import_present"]).lower())
    print("repair_marker_present =", str(payload["repair_marker_present"]).lower())
    print("accepted_dirty_paths =", json.dumps(accepted_dirty_paths, ensure_ascii=False))
    print("state_written =", str(state_written).lower())
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
