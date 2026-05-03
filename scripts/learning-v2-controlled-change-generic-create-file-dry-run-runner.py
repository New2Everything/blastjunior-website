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
CREATE_FILE_METADATA_DIR = BASE / "controlled-create-files"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
CREATE_FILE_METADATA_DIR.mkdir(parents=True, exist_ok=True)

RUNNER_ID = "learning-v2-controlled-change-generic-create-file-dry-run-runner-v0"

FORBIDDEN_TARGET_FILES = {
    "wrangler.toml",
    "package.json",
    "components/nav.html",
    "components/nav.css",
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

def validate_create_file_metadata(meta):
    failures = []
    warnings = []

    target_file = str(meta.get("target_file") or "").lstrip("./")
    target_path = WORKSPACE / target_file if target_file else None

    template = meta.get("template") or {}
    safety = meta.get("safety") or {}
    acceptance = meta.get("acceptance") or {}

    body = template.get("body")

    if not target_file:
        failures.append("target_file_empty")

    if target_file in FORBIDDEN_TARGET_FILES:
        failures.append(f"target_file_forbidden:{target_file}")

    if target_path and target_path.exists():
        failures.append(f"target_file_already_exists:{target_file}")

    allowed_prefixes = safety.get("allowed_target_prefixes") or []
    if target_file and allowed_prefixes:
        if not any(target_file.startswith(str(prefix).lstrip("./")) for prefix in allowed_prefixes):
            failures.append(f"target_file_not_under_allowed_prefix:{target_file}")

    if meta.get("risk") != "low":
        failures.append(f"risk_not_low:{meta.get('risk')}")

    if meta.get("change_type") != "create_file_from_template":
        failures.append(f"change_type_not_create_file_from_template:{meta.get('change_type')}")

    if meta.get("allowed_stage") not in ["dry_run_only"]:
        failures.append(f"allowed_stage_not_dry_run_only:{meta.get('allowed_stage')}")

    if template.get("mode") != "create_file_from_template":
        failures.append(f"template_mode_invalid:{template.get('mode')}")

    if not isinstance(body, str) or not body.strip():
        failures.append("template_body_empty_or_not_string")

    if safety.get("target_file_must_not_exist") is not True:
        failures.append(f"safety_target_file_must_not_exist_not_true:{safety.get('target_file_must_not_exist')}")

    for key in ["git_commit", "git_push", "deploy"]:
        if safety.get(key) is not False:
            failures.append(f"safety_{key}_not_false:{safety.get(key)}")

    max_total_lines = safety.get("max_total_lines")
    if not isinstance(max_total_lines, int):
        failures.append("safety_max_total_lines_not_integer")
    elif isinstance(body, str):
        total_lines = len(body.splitlines())
        if total_lines > max_total_lines:
            failures.append(f"body_line_count_exceeds_max:{total_lines}>{max_total_lines}")

    if isinstance(body, str):
        for marker in safety.get("blocked_content_markers") or []:
            if str(marker).lower() in body.lower():
                failures.append(f"blocked_content_marker_found:{marker}")

        for section in template.get("required_sections") or []:
            if section not in body:
                failures.append(f"template_body_missing_required_section:{section}")

        for marker in acceptance.get("required_markers") or []:
            if marker not in body:
                failures.append(f"template_body_missing_acceptance_marker:{marker}")

    if acceptance.get("expected_target_file") != target_file:
        failures.append(f"acceptance_target_mismatch:{acceptance.get('expected_target_file')}!={target_file}")

    if acceptance.get("created_file_must_be_only_delta") is not True:
        failures.append("acceptance_created_file_must_be_only_delta_not_true")

    if acceptance.get("ledger_acceptance_required") is not True:
        failures.append("acceptance_ledger_acceptance_required_not_true")

    return failures, warnings

def dry_run_one(meta_path, meta):
    failures, warnings = validate_create_file_metadata(meta)

    change_unit_id = meta.get("change_unit_id")
    target_family = meta.get("target_family")
    target_file = str(meta.get("target_file") or "").lstrip("./")
    template = meta.get("template") or {}
    body = template.get("body") or ""

    proposed_text = body
    added_line_count = len(proposed_text.splitlines())
    removed_line_count = 0

    diff_lines = list(difflib.unified_diff(
        [],
        proposed_text.splitlines(),
        fromfile=f"{target_file}:missing",
        tofile=f"{target_file}:proposed-create-file",
        lineterm="",
    ))

    safe_id = str(change_unit_id or meta_path.stem).replace("/", "-")
    run_stamp = stamp()
    out_json = REPORT_DIR / f"generic-create-file-dry-run-{safe_id}-{run_stamp}.json"
    out_diff = REPORT_DIR / f"generic-create-file-dry-run-{safe_id}-{run_stamp}.diff"

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "runner_id": RUNNER_ID,
        "result": result,
        "metadata_file": str(meta_path),
        "change_unit_id": change_unit_id,
        "target_family": target_family,
        "target_file": target_file,
        "change_type": meta.get("change_type"),
        "changed_in_dry_run": result == "ok",
        "target_file_exists_before_dry_run": bool(target_file and (WORKSPACE / target_file).exists()),
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
        "added_line_count": added_line_count,
        "removed_line_count": removed_line_count,
        "diff_path": str(out_diff),
        "recommended_next_step": "run_generic_create_file_policy_gate" if result == "ok" else "fix_create_file_metadata_or_template",
        "warnings": warnings,
        "failures": failures,
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_diff.write_text("\n".join(diff_lines) + "\n", encoding="utf-8")

    return payload

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    template_validator_path, template_validator = latest_report("controlled-change-new-file-template-validator-*.json")
    extension_plan_path, extension_plan = latest_report("create-file-from-template-lifecycle-extension-plan-*.json")
    readiness_guard_path, readiness_guard = latest_report("new-file-creation-lifecycle-readiness-guard-*.json")
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
        ("create_file_extension_plan", extension_plan_path, extension_plan),
        ("new_file_readiness_guard", readiness_guard_path, readiness_guard),
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

    if readiness_guard.get("target_file") != "public/about.html":
        failures.append(f"readiness_guard_target_file_unexpected:{readiness_guard.get('target_file')}")

    if readiness_guard.get("target_file_exists") is not False:
        failures.append(f"readiness_guard_target_file_exists_not_false:{readiness_guard.get('target_file_exists')}")

    metadata_files = sorted(CREATE_FILE_METADATA_DIR.glob("*.json"))
    dry_run_results = []

    if not failures:
        for meta_path in metadata_files:
            meta = load_json(meta_path, default={})
            dry_run_results.append(dry_run_one(meta_path, meta))

    blocked_dry_runs = [x for x in dry_run_results if x.get("result") != "ok"]

    if blocked_dry_runs:
        failures.append(f"blocked_create_file_dry_runs:{len(blocked_dry_runs)}")

    result = "ok" if not failures else "blocked"

    recommended_next_step = (
        "build_generic_create_file_policy_gate"
        if result == "ok"
        else "fix_generic_create_file_dry_run_runner_blockers"
    )

    out_json = REPORT_DIR / f"controlled-change-generic-create-file-dry-run-runner-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"controlled-change-generic-create-file-dry-run-runner-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "runner_id": RUNNER_ID,
        "result": result,
        "runner_mode": "create_file_dry_run_only",
        "metadata_file_count": len(metadata_files),
        "dry_run_result_count": len(dry_run_results),
        "blocked_dry_run_count": len(blocked_dry_runs),
        "dry_run_results": dry_run_results,
        "new_file_template_validator_report": str(template_validator_path) if template_validator_path else None,
        "create_file_extension_plan_report": str(extension_plan_path) if extension_plan_path else None,
        "new_file_readiness_guard_report": str(readiness_guard_path) if readiness_guard_path else None,
        "integrity_report": str(integrity_path) if integrity_path else None,
        "fourth_loop_allowed_now": False,
        "metadata_written": False,
        "source_written": False,
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
            "runner_only": True,
            "dry_run_only": True,
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
    lines.append("# Learning V2 Controlled Change Generic Create File Dry Run Runner")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- runner_id: `{RUNNER_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append("- runner_mode: `create_file_dry_run_only`")
    lines.append(f"- metadata_file_count: `{len(metadata_files)}`")
    lines.append(f"- dry_run_result_count: `{len(dry_run_results)}`")
    lines.append(f"- blocked_dry_run_count: `{len(blocked_dry_runs)}`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")
    lines.append("- fourth_loop_allowed_now: `false`")
    lines.append("- metadata_written: `false`")
    lines.append("- source_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- fourth_loop_started: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Dry Run Results")
    if dry_run_results:
        for item in dry_run_results:
            lines.append(
                f"- `{item.get('change_unit_id')}` target=`{item.get('target_file')}` "
                f"result=`{item.get('result')}` added=`{item.get('added_line_count')}` failures=`{item.get('failures')}`"
            )
    else:
        lines.append("- none; no create-file metadata files yet")

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

    print("controlled_change_generic_create_file_dry_run_runner =", result)
    print("runner_mode = create_file_dry_run_only")
    print("metadata_file_count =", len(metadata_files))
    print("dry_run_result_count =", len(dry_run_results))
    print("blocked_dry_run_count =", len(blocked_dry_runs))
    print("fourth_loop_allowed_now = False")
    print("metadata_written = False")
    print("source_written = False")
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
