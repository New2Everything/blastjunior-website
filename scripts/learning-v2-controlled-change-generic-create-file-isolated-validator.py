#!/usr/bin/env python3
import difflib
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

VALIDATOR_ID = "learning-v2-controlled-change-generic-create-file-isolated-validator-v0"

CLOSED_TARGET_FILES = {
    "public/index.html",
    "public/gallery.html",
    "public/news.html",
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def latest_report(pattern):
    files = sorted(REPORT_DIR.glob(pattern))
    if not files:
        return None, {}
    p = files[-1]
    return p, load_json(p, default={})

def latest_create_file_apply_report():
    apply_files = sorted(
        REPORT_DIR.glob("controlled-change-generic-create-file-apply-apply-*.json"),
        key=lambda x: x.stat().st_mtime
    )
    dry_run_files = sorted(
        REPORT_DIR.glob("controlled-change-generic-create-file-apply-dry-run-*.json"),
        key=lambda x: x.stat().st_mtime
    )

    # Prefer a real apply report, especially one that actually wrote source.
    for p in reversed(apply_files):
        data = load_json(p, default={})
        if data.get("result") == "ok" and data.get("source_written") is True:
            return p, data

    if apply_files:
        p = apply_files[-1]
        return p, load_json(p, default={})

    if dry_run_files:
        p = dry_run_files[-1]
        return p, load_json(p, default={})

    return None, {}

def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for value in obj.values():
            found = find_key(value, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = find_key(item, key)
            if found is not None:
                return found
    return None

def validate_one_create_file_apply_result(item, run_stamp):
    failures = []
    warnings = []

    target_file = str(item.get("target_file") or "").lstrip("./")
    created_file_path = item.get("created_file_path")
    source_written = item.get("source_written")
    apply_flag = item.get("apply")

    if apply_flag is not True:
        failures.append(f"apply_not_true:{apply_flag}")

    if source_written is not True:
        failures.append(f"source_written_not_true:{source_written}")

    if not target_file:
        failures.append("target_file_missing")
    elif target_file in CLOSED_TARGET_FILES:
        failures.append(f"target_file_already_closed:{target_file}")
    elif not target_file.startswith("public/"):
        failures.append(f"target_file_not_under_public:{target_file}")
    elif not (WORKSPACE / target_file).exists():
        failures.append(f"target_file_missing_on_disk:{target_file}")

    if not created_file_path:
        failures.append("created_file_path_missing")
    elif not Path(created_file_path).exists():
        failures.append(f"created_file_path_missing_on_disk:{created_file_path}")

    for key in ["git_commit", "git_push", "deploy"]:
        if item.get(key) is not False:
            failures.append(f"{key}_not_false:{item.get(key)}")

    added_line_count = 0
    removed_line_count = 0
    diff_path = None
    isolated_delta_interpretation = "blocked_or_unclassified_create_file_delta"

    if not failures:
        current_text = (WORKSPACE / target_file).read_text(encoding="utf-8", errors="ignore")

        diff_lines = list(difflib.unified_diff(
            [],
            current_text.splitlines(),
            fromfile=f"{target_file}:missing",
            tofile=f"{target_file}:current",
            lineterm="",
        ))

        added_lines = [x for x in diff_lines if x.startswith("+") and not x.startswith("+++")]
        removed_lines = [x for x in diff_lines if x.startswith("-") and not x.startswith("---")]

        added_line_count = len(added_lines)
        removed_line_count = len(removed_lines)

        safe_id = str(item.get("change_unit_id") or "generic-create-file").replace("/", "-")
        diff_path = REPORT_DIR / f"generic-create-file-isolated-validator-{safe_id}-{run_stamp}.diff"
        diff_path.write_text("\n".join(diff_lines) + "\n", encoding="utf-8")

        if added_line_count <= 0:
            failures.append("no_added_lines_detected_for_created_file")

        if removed_line_count != 0:
            failures.append(f"removed_line_count_not_zero:{removed_line_count}")

        if not failures:
            isolated_delta_interpretation = "missing_to_current_delta_is_created_target_file_only"

    return {
        "change_unit_id": item.get("change_unit_id"),
        "target_family": item.get("target_family"),
        "target_file": target_file,
        "metadata_file": item.get("metadata_file"),
        "result": "ok" if not failures else "blocked",
        "source_written": source_written,
        "created_file_path": created_file_path,
        "added_line_count": added_line_count,
        "removed_line_count": removed_line_count,
        "diff_path": str(diff_path) if diff_path else None,
        "isolated_delta_interpretation": isolated_delta_interpretation,
        "metadata_written": False,
        "state_written": False,
        "business_source_written": False,
        "source_change_gate_opened": False,
        "fourth_loop_started": False,
        "human_review_required": False,
        "machine_policy_gate": True,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "warnings": warnings,
        "failures": failures,
    }

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    template_validator_path, template_validator = latest_report("controlled-change-new-file-template-validator-*.json")
    dry_runner_path, dry_runner = latest_report("controlled-change-generic-create-file-dry-run-runner-*.json")
    policy_gate_path, policy_gate = latest_report("controlled-change-generic-create-file-policy-gate-*.json")
    readiness_path, readiness = latest_report("controlled-change-generic-create-file-readiness-*.json")
    apply_path, apply_report = latest_create_file_apply_report()
    extension_plan_path, extension_plan = latest_report("create-file-from-template-lifecycle-extension-plan-*.json")
    integrity_path, integrity = latest_report("system-integrity-*.json")
    drift_path, drift = latest_report("system-drift-audit-*.json")

    failures = []
    warnings = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    for key in ["source_changes_allowed", "git_commit_allowed", "git_push_allowed", "deploy_allowed"]:
        if policy.get(key) is not False:
            failures.append(f"policy_{key}_not_false:{policy.get(key)}")

    for label, path, report in [
        ("new_file_template_validator", template_validator_path, template_validator),
        ("generic_create_file_dry_run_runner", dry_runner_path, dry_runner),
        ("generic_create_file_policy_gate", policy_gate_path, policy_gate),
        ("generic_create_file_readiness", readiness_path, readiness),
        ("generic_create_file_apply", apply_path, apply_report),
        ("create_file_extension_plan", extension_plan_path, extension_plan),
        ("system_integrity", integrity_path, integrity),
    ]:
        if not path:
            failures.append(f"missing_{label}_report")
        elif report.get("result") != "ok":
            failures.append(f"{label}_not_ok:{report.get('result')}")

    integrity_drift_count = integrity.get("drift_count")
    if integrity_drift_count is None:
        integrity_drift_count = find_key(integrity, "drift_count")
    if integrity_drift_count is None:
        integrity_drift_count = drift.get("drift_count")

    business_freeze_stable = integrity.get("business_freeze_stable")
    if business_freeze_stable is None:
        business_freeze_stable = find_key(integrity, "business_freeze_stable")
    if business_freeze_stable is None:
        business_freeze_stable = drift.get("business_freeze_stable")

    if integrity_drift_count != 0:
        failures.append(f"drift_count_not_zero:{integrity_drift_count}")

    if business_freeze_stable is not True:
        failures.append(f"business_freeze_not_stable:{business_freeze_stable}")

    if dry_runner.get("blocked_dry_run_count") not in (0, None):
        failures.append(f"blocked_dry_run_count_not_zero:{dry_runner.get('blocked_dry_run_count')}")

    if policy_gate.get("blocked_gate_result_count") not in (0, None):
        failures.append(f"blocked_gate_result_count_not_zero:{policy_gate.get('blocked_gate_result_count')}")

    if readiness.get("blocked_readiness_result_count") not in (0, None):
        failures.append(f"blocked_readiness_result_count_not_zero:{readiness.get('blocked_readiness_result_count')}")

    if apply_report.get("blocked_apply_result_count") not in (0, None):
        failures.append(f"blocked_apply_result_count_not_zero:{apply_report.get('blocked_apply_result_count')}")

    if apply_report.get("source_written") is not False and not apply_report.get("apply_results"):
        failures.append("apply_report_source_written_true_but_missing_apply_results")

    apply_results = apply_report.get("apply_results") or []
    validation_results = []

    if not failures:
        for item in apply_results:
            if item.get("source_written") is True:
                validation_results.append(validate_one_create_file_apply_result(item, stamp()))
            else:
                warnings.append(f"skip_non_written_create_file_apply_result:{item.get('change_unit_id')}")

    blocked_validation_results = [x for x in validation_results if x.get("result") != "ok"]

    if blocked_validation_results:
        failures.append(f"blocked_create_file_isolated_validation_results:{len(blocked_validation_results)}")

    if apply_report.get("metadata_file_count", 0) == 0:
        validator_mode = "no_metadata_safe_noop"
        recommended_next_step = "build_generic_create_file_ledger_acceptance"
    else:
        validator_mode = "create_file_isolated_validation"
        recommended_next_step = (
            "build_generic_create_file_ledger_acceptance"
            if not failures
            else "fix_generic_create_file_isolated_validator_blockers"
        )

    result = "ok" if not failures else "blocked"

    out_json = REPORT_DIR / f"controlled-change-generic-create-file-isolated-validator-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"controlled-change-generic-create-file-isolated-validator-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "validator_id": VALIDATOR_ID,
        "result": result,
        "validator_mode": validator_mode,
        "metadata_file_count": apply_report.get("metadata_file_count"),
        "apply_result_count": len(apply_results),
        "validation_result_count": len(validation_results),
        "blocked_validation_result_count": len(blocked_validation_results),
        "validation_results": validation_results,
        "new_file_template_validator_report": str(template_validator_path) if template_validator_path else None,
        "generic_create_file_dry_run_runner_report": str(dry_runner_path) if dry_runner_path else None,
        "generic_create_file_policy_gate_report": str(policy_gate_path) if policy_gate_path else None,
        "generic_create_file_readiness_report": str(readiness_path) if readiness_path else None,
        "generic_create_file_apply_report": str(apply_path) if apply_path else None,
        "create_file_extension_plan_report": str(extension_plan_path) if extension_plan_path else None,
        "integrity_report": str(integrity_path) if integrity_path else None,
        "source_written": False,
        "metadata_written": False,
        "state_written": False,
        "business_source_written": False,
        "source_change_gate_opened": False,
        "fourth_loop_started": False,
        "human_review_required": False,
        "machine_policy_gate": True,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "recommended_next_step": recommended_next_step,
        "policy": {
            "validator_only": True,
            "metadata_written": False,
            "state_written": False,
            "business_source_written": False,
            "source_change_gate_opened": False,
            "fourth_loop_started": False,
            "human_review_required": False,
            "machine_policy_gate": True,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
        "warnings": warnings,
        "failures": failures,
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Controlled Change Generic Create File Isolated Validator")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- validator_id: `{VALIDATOR_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- validator_mode: `{validator_mode}`")
    lines.append(f"- metadata_file_count: `{payload['metadata_file_count']}`")
    lines.append(f"- apply_result_count: `{len(apply_results)}`")
    lines.append(f"- validation_result_count: `{len(validation_results)}`")
    lines.append(f"- blocked_validation_result_count: `{len(blocked_validation_results)}`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")
    lines.append("- source_written: `false`")
    lines.append("- metadata_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- fourth_loop_started: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Validation Results")
    if validation_results:
        for item in validation_results:
            lines.append(
                f"- `{item.get('change_unit_id')}` target=`{item.get('target_file')}` "
                f"result=`{item.get('result')}` added=`{item.get('added_line_count')}` removed=`{item.get('removed_line_count')}`"
            )
    else:
        lines.append("- none; no create-file source writes yet")

    if warnings:
        lines.append("")
        lines.append("## Warnings")
        for w in warnings:
            lines.append(f"- {w}")

    if failures:
        lines.append("")
        lines.append("## Failures")
        for f in failures:
            lines.append(f"- {f}")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("controlled_change_generic_create_file_isolated_validator =", result)
    print("validator_mode =", validator_mode)
    print("metadata_file_count =", apply_report.get("metadata_file_count"))
    print("apply_result_count =", len(apply_results))
    print("validation_result_count =", len(validation_results))
    print("blocked_validation_result_count =", len(blocked_validation_results))
    print("source_written = False")
    print("metadata_written = False")
    print("state_written = False")
    print("business_source_written = False")
    print("source_change_gate_opened = False")
    print("fourth_loop_started = False")
    print("human_review_required = False")
    print("machine_policy_gate = True")
    print("git_commit = False")
    print("git_push = False")
    print("deploy = False")
    print("recommended_next_step =", recommended_next_step)
    print("report_json =", out_json)
    print("report_md =", out_md)

    if warnings:
        print("warnings =", json.dumps(warnings, ensure_ascii=False))
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
