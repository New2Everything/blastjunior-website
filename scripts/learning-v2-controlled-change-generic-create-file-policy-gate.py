#!/usr/bin/env python3
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

GATE_ID = "learning-v2-controlled-change-generic-create-file-policy-gate-v0"

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

def check_create_file_dry_run(item):
    failures = []
    warnings = []

    target_file = item.get("target_file")

    if item.get("result") != "ok":
        failures.append(f"dry_run_result_not_ok:{item.get('result')}")

    if item.get("changed_in_dry_run") is not True:
        warnings.append(f"changed_in_dry_run_not_true:{item.get('changed_in_dry_run')}")

    if item.get("target_file_exists_before_dry_run") is not False:
        failures.append(f"target_file_exists_before_dry_run_not_false:{item.get('target_file_exists_before_dry_run')}")

    if not target_file:
        failures.append("target_file_missing")
    elif target_file in CLOSED_TARGET_FILES:
        failures.append(f"target_file_already_closed:{target_file}")
    elif not str(target_file).startswith("public/"):
        failures.append(f"target_file_not_under_public:{target_file}")

    if item.get("source_written") is not False:
        failures.append(f"source_written_not_false:{item.get('source_written')}")

    if item.get("metadata_written") is not False:
        failures.append(f"metadata_written_not_false:{item.get('metadata_written')}")

    if item.get("state_written") is not False:
        failures.append(f"state_written_not_false:{item.get('state_written')}")

    if item.get("business_source_written") is not False:
        failures.append(f"business_source_written_not_false:{item.get('business_source_written')}")

    if item.get("source_change_gate_opened") is not False:
        failures.append(f"source_change_gate_opened_not_false:{item.get('source_change_gate_opened')}")

    if item.get("fourth_loop_started") is not False:
        failures.append(f"fourth_loop_started_not_false:{item.get('fourth_loop_started')}")

    if item.get("human_review_required") is not False:
        failures.append(f"human_review_required_not_false:{item.get('human_review_required')}")

    if item.get("machine_policy_gate") is not True:
        failures.append(f"machine_policy_gate_not_true:{item.get('machine_policy_gate')}")

    for key in ["git_commit", "git_push", "deploy"]:
        if item.get(key) is not False:
            failures.append(f"{key}_not_false:{item.get(key)}")

    if item.get("removed_line_count") not in (0, None):
        failures.append(f"removed_line_count_not_zero:{item.get('removed_line_count')}")

    if item.get("added_line_count") is None:
        warnings.append("added_line_count_missing")
    elif item.get("added_line_count") > 240:
        failures.append(f"added_line_count_too_large:{item.get('added_line_count')}")

    if item.get("failures"):
        failures.append("dry_run_has_failures")

    return failures, warnings

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    template_validator_path, template_validator = latest_report("controlled-change-new-file-template-validator-*.json")
    dry_runner_path, dry_runner = latest_report("controlled-change-generic-create-file-dry-run-runner-*.json")
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
        ("generic_create_file_dry_run_runner", dry_runner_path, dry_runner),
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

    if dry_runner.get("blocked_dry_run_count") not in (0, None):
        failures.append(f"blocked_dry_run_count_not_zero:{dry_runner.get('blocked_dry_run_count')}")

    dry_run_results = dry_runner.get("dry_run_results") or []
    gate_results = []

    for item in dry_run_results:
        item_failures, item_warnings = check_create_file_dry_run(item)
        decision = "allow_next_create_file_readiness" if not item_failures else "blocked"

        gate_results.append({
            "change_unit_id": item.get("change_unit_id"),
            "target_family": item.get("target_family"),
            "target_file": item.get("target_file"),
            "metadata_file": item.get("metadata_file"),
            "dry_run_report": item.get("report_json"),
            "decision": decision,
            "failures": item_failures,
            "warnings": item_warnings,
        })

    blocked_gate_results = [
        x for x in gate_results
        if x.get("decision") != "allow_next_create_file_readiness"
    ]

    if blocked_gate_results:
        failures.append(f"blocked_create_file_gate_results:{len(blocked_gate_results)}")

    if dry_runner.get("metadata_file_count", 0) == 0:
        gate_mode = "no_metadata_safe_noop"
        recommended_next_step = "build_generic_create_file_readiness"
    else:
        gate_mode = "create_file_dry_run_policy_checked"
        recommended_next_step = "build_generic_create_file_readiness" if not failures else "fix_generic_create_file_policy_gate_blockers"

    result = "ok" if not failures else "blocked"

    out_json = REPORT_DIR / f"controlled-change-generic-create-file-policy-gate-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"controlled-change-generic-create-file-policy-gate-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "gate_id": GATE_ID,
        "result": result,
        "gate_mode": gate_mode,
        "metadata_file_count": dry_runner.get("metadata_file_count"),
        "dry_run_result_count": len(dry_run_results),
        "gate_result_count": len(gate_results),
        "blocked_gate_result_count": len(blocked_gate_results),
        "gate_results": gate_results,
        "new_file_template_validator_report": str(template_validator_path) if template_validator_path else None,
        "generic_create_file_dry_run_runner_report": str(dry_runner_path) if dry_runner_path else None,
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
            "gate_only": True,
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
    lines.append("# Learning V2 Controlled Change Generic Create File Policy Gate")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- gate_id: `{GATE_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- gate_mode: `{gate_mode}`")
    lines.append(f"- metadata_file_count: `{payload['metadata_file_count']}`")
    lines.append(f"- dry_run_result_count: `{len(dry_run_results)}`")
    lines.append(f"- gate_result_count: `{len(gate_results)}`")
    lines.append(f"- blocked_gate_result_count: `{len(blocked_gate_results)}`")
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
    lines.append("## Gate Results")
    if gate_results:
        for item in gate_results:
            lines.append(
                f"- `{item.get('change_unit_id')}` target=`{item.get('target_file')}` "
                f"decision=`{item.get('decision')}` failures=`{item.get('failures')}`"
            )
    else:
        lines.append("- none; no create-file metadata dry-run results yet")

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

    print("controlled_change_generic_create_file_policy_gate =", result)
    print("gate_mode =", gate_mode)
    print("metadata_file_count =", dry_runner.get("metadata_file_count"))
    print("dry_run_result_count =", len(dry_run_results))
    print("gate_result_count =", len(gate_results))
    print("blocked_gate_result_count =", len(blocked_gate_results))
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
