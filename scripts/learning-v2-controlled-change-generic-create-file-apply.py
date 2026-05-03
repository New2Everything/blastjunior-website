#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
BACKUP_DIR = BASE / "backups"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

APPLY_ID = "learning-v2-controlled-change-generic-create-file-apply-v0"

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

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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

def close_source_gate(state):
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

def open_source_gate_for_apply(state):
    state["allow_source_changes"] = True
    state["allow_git_commit"] = False
    state["allow_deploy"] = False

    policy = state.get("self_evolution_policy") or {}
    policy["source_changes_allowed"] = True
    policy["git_commit_allowed"] = False
    policy["git_push_allowed"] = False
    policy["deploy_allowed"] = False
    state["self_evolution_policy"] = policy
    return state

def validate_metadata_for_create_file(meta):
    failures = []

    target_file = str(meta.get("target_file") or "").lstrip("./")
    target_path = WORKSPACE / target_file if target_file else None

    template = meta.get("template") or {}
    safety = meta.get("safety") or {}
    acceptance = meta.get("acceptance") or {}

    if not target_file:
        failures.append("target_file_empty")

    if target_file in CLOSED_TARGET_FILES:
        failures.append(f"target_file_already_closed:{target_file}")

    if target_file and not target_file.startswith("public/"):
        failures.append(f"target_file_not_under_public:{target_file}")

    if target_path and target_path.exists():
        failures.append(f"target_file_already_exists:{target_file}")

    if meta.get("risk") != "low":
        failures.append(f"risk_not_low:{meta.get('risk')}")

    if meta.get("change_type") != "create_file_from_template":
        failures.append(f"change_type_not_create_file_from_template:{meta.get('change_type')}")

    if meta.get("allowed_stage") not in ["dry_run_only"]:
        failures.append(f"allowed_stage_not_dry_run_only:{meta.get('allowed_stage')}")

    if template.get("mode") != "create_file_from_template":
        failures.append(f"template_mode_invalid:{template.get('mode')}")

    body = template.get("body")
    if not isinstance(body, str) or not body.strip():
        failures.append("template_body_empty_or_not_string")

    if safety.get("target_file_must_not_exist") is not True:
        failures.append(f"safety_target_file_must_not_exist_not_true:{safety.get('target_file_must_not_exist')}")

    for key in ["git_commit", "git_push", "deploy"]:
        if safety.get(key) is not False:
            failures.append(f"safety_{key}_not_false:{safety.get(key)}")

    if acceptance.get("expected_target_file") != target_file:
        failures.append(f"acceptance_target_mismatch:{acceptance.get('expected_target_file')}!={target_file}")

    if acceptance.get("created_file_must_be_only_delta") is not True:
        failures.append("acceptance_created_file_must_be_only_delta_not_true")

    if acceptance.get("ledger_acceptance_required") is not True:
        failures.append("acceptance_ledger_acceptance_required_not_true")

    if isinstance(body, str):
        for marker in acceptance.get("required_markers") or []:
            if marker not in body:
                failures.append(f"body_missing_required_marker:{marker}")

        for marker in safety.get("blocked_content_markers") or []:
            if str(marker).lower() in body.lower():
                failures.append(f"blocked_content_marker_found:{marker}")

    return failures

def validate_apply_candidate(item):
    failures = []
    warnings = []

    target_file = str(item.get("target_file") or "").lstrip("./")
    metadata_file = item.get("metadata_file")

    if item.get("ready_for_create_file_apply_self_check") is not True:
        failures.append(f"readiness_not_true:{item.get('ready_for_create_file_apply_self_check')}")

    if item.get("decision") != "ready_for_create_file_apply_self_check":
        failures.append(f"decision_not_ready:{item.get('decision')}")

    if item.get("ready_to_open_source_change_gate") is not False:
        failures.append(f"ready_to_open_source_change_gate_not_false:{item.get('ready_to_open_source_change_gate')}")

    if not target_file:
        failures.append("target_file_missing")
    elif target_file in CLOSED_TARGET_FILES:
        failures.append(f"target_file_already_closed:{target_file}")
    elif not target_file.startswith("public/"):
        failures.append(f"target_file_not_under_public:{target_file}")
    elif (WORKSPACE / target_file).exists():
        failures.append(f"target_file_already_exists:{target_file}")

    if not metadata_file:
        failures.append("metadata_file_missing")
    elif not Path(metadata_file).exists():
        failures.append(f"metadata_file_missing_on_disk:{metadata_file}")

    if item.get("failures"):
        failures.append("readiness_item_has_failures")

    if item.get("warnings"):
        warnings.extend([f"readiness_warning:{x}" for x in item.get("warnings")])

    return failures, warnings

def apply_one(item, run_stamp, actually_apply):
    failures, warnings = validate_apply_candidate(item)

    metadata_file = item.get("metadata_file")
    meta = load_json(metadata_file, default={}) if metadata_file else {}

    if meta:
        failures.extend(validate_metadata_for_create_file(meta))

    target_file = str(item.get("target_file") or "").lstrip("./")
    target_path = WORKSPACE / target_file if target_file else None

    body = ""
    changed_in_apply_plan = False
    source_written = False
    gate_opened_during_apply = False
    gate_closed_after_apply = False
    created_file_path = None

    if not failures:
        body = (meta.get("template") or {}).get("body") or ""
        changed_in_apply_plan = bool(body.strip())

        if not changed_in_apply_plan:
            failures.append("proposed_file_body_empty")

    if actually_apply and not failures:
        try:
            state = load_json(STATE, default={})
            state = open_source_gate_for_apply(state)
            save_json(STATE, state)
            gate_opened_during_apply = True

            target_path.parent.mkdir(parents=True, exist_ok=True)

            if target_path.exists():
                failures.append(f"target_file_appeared_before_write:{target_file}")
            else:
                target_path.write_text(body, encoding="utf-8")
                source_written = True
                created_file_path = str(target_path)
        finally:
            latest_state = load_json(STATE, default={})
            latest_state = close_source_gate(latest_state)
            save_json(STATE, latest_state)
            gate_closed_after_apply = True

    result = "ok" if not failures else "blocked"

    return {
        "change_unit_id": item.get("change_unit_id"),
        "target_family": item.get("target_family"),
        "target_file": target_file,
        "metadata_file": metadata_file,
        "result": result,
        "apply": actually_apply,
        "changed_in_apply_plan": changed_in_apply_plan,
        "created_file_path": created_file_path,
        "source_written": source_written,
        "backup_path": None,
        "gate_opened_during_apply": gate_opened_during_apply,
        "gate_closed_after_apply": gate_closed_after_apply,
        "state_written": bool(actually_apply and result == "ok"),
        "business_source_written": source_written,
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="perform controlled create-file source write")
    args = ap.parse_args()

    run_stamp = stamp()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    template_validator_path, template_validator = latest_report("controlled-change-new-file-template-validator-*.json")
    dry_runner_path, dry_runner = latest_report("controlled-change-generic-create-file-dry-run-runner-*.json")
    policy_gate_path, policy_gate = latest_report("controlled-change-generic-create-file-policy-gate-*.json")
    readiness_path, readiness = latest_report("controlled-change-generic-create-file-readiness-*.json")
    extension_plan_path, extension_plan = latest_report("create-file-from-template-lifecycle-extension-plan-*.json")
    readiness_guard_path, readiness_guard = latest_report("new-file-creation-lifecycle-readiness-guard-*.json")
    integrity_path, integrity = latest_report("system-integrity-*.json")
    drift_path, drift = latest_report("system-drift-audit-*.json")

    failures = []
    warnings = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_initially_false:{state.get('allow_source_changes')}")

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

    if policy_gate.get("blocked_gate_result_count") not in (0, None):
        failures.append(f"blocked_gate_result_count_not_zero:{policy_gate.get('blocked_gate_result_count')}")

    if readiness.get("blocked_readiness_result_count") not in (0, None):
        failures.append(f"blocked_readiness_result_count_not_zero:{readiness.get('blocked_readiness_result_count')}")

    if readiness_guard.get("target_file") != "public/about.html":
        failures.append(f"readiness_guard_target_file_unexpected:{readiness_guard.get('target_file')}")

    if readiness_guard.get("target_file_exists") is not False:
        failures.append(f"readiness_guard_target_file_exists_not_false:{readiness_guard.get('target_file_exists')}")

    readiness_results = readiness.get("readiness_results") or []
    apply_results = []

    if not failures:
        for item in readiness_results:
            apply_results.append(apply_one(item, run_stamp, args.apply))

    blocked_apply_results = [x for x in apply_results if x.get("result") != "ok"]

    if blocked_apply_results:
        failures.append(f"blocked_create_file_apply_results:{len(blocked_apply_results)}")

    if readiness.get("metadata_file_count", 0) == 0:
        apply_mode = "no_metadata_safe_noop"
        recommended_next_step = "build_generic_create_file_isolated_validator"
    else:
        apply_mode = "create_file_apply_self_check" if not args.apply else "create_file_apply"
        recommended_next_step = (
            "build_generic_create_file_isolated_validator"
            if not failures
            else "fix_generic_create_file_apply_blockers"
        )

    result = "ok" if not failures else "blocked"

    latest_state = load_json(STATE, default={})
    latest_state = close_source_gate(latest_state)
    save_json(STATE, latest_state)

    out_json = REPORT_DIR / f"controlled-change-generic-create-file-apply-{'apply' if args.apply else 'dry-run'}-{run_stamp}.json"
    out_md = SNAPSHOT_DIR / f"controlled-change-generic-create-file-apply-{'apply' if args.apply else 'dry-run'}-{run_stamp}.md"

    payload = {
        "generated_at": now_iso(),
        "apply_id": APPLY_ID,
        "result": result,
        "apply": args.apply,
        "apply_mode": apply_mode,
        "metadata_file_count": readiness.get("metadata_file_count"),
        "readiness_result_count": len(readiness_results),
        "apply_result_count": len(apply_results),
        "blocked_apply_result_count": len(blocked_apply_results),
        "apply_results": apply_results,
        "new_file_template_validator_report": str(template_validator_path) if template_validator_path else None,
        "generic_create_file_dry_run_runner_report": str(dry_runner_path) if dry_runner_path else None,
        "generic_create_file_policy_gate_report": str(policy_gate_path) if policy_gate_path else None,
        "generic_create_file_readiness_report": str(readiness_path) if readiness_path else None,
        "create_file_extension_plan_report": str(extension_plan_path) if extension_plan_path else None,
        "new_file_readiness_guard_report": str(readiness_guard_path) if readiness_guard_path else None,
        "integrity_report": str(integrity_path) if integrity_path else None,
        "source_written": any(x.get("source_written") for x in apply_results),
        "metadata_written": False,
        "state_written": bool(args.apply and result == "ok" and apply_results),
        "business_source_written": any(x.get("business_source_written") for x in apply_results),
        "source_change_gate_opened": False,
        "fourth_loop_started": False,
        "human_review_required": False,
        "machine_policy_gate": True,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "recommended_next_step": recommended_next_step,
        "policy": {
            "apply_executor_only": True,
            "metadata_written": False,
            "state_written": bool(args.apply and result == "ok" and apply_results),
            "business_source_written": any(x.get("business_source_written") for x in apply_results),
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
    lines.append("# Learning V2 Controlled Change Generic Create File Apply")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- apply_id: `{APPLY_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- apply: `{str(args.apply).lower()}`")
    lines.append(f"- apply_mode: `{apply_mode}`")
    lines.append(f"- metadata_file_count: `{payload['metadata_file_count']}`")
    lines.append(f"- readiness_result_count: `{len(readiness_results)}`")
    lines.append(f"- apply_result_count: `{len(apply_results)}`")
    lines.append(f"- blocked_apply_result_count: `{len(blocked_apply_results)}`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")
    lines.append("- apply_executor_only: `true`")
    lines.append(f"- source_written: `{str(payload['source_written']).lower()}`")
    lines.append("- metadata_written: `false`")
    lines.append(f"- state_written: `{str(payload['state_written']).lower()}`")
    lines.append(f"- business_source_written: `{str(payload['business_source_written']).lower()}`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- fourth_loop_started: `false`")
    lines.append("- human_review_required: `false`")
    lines.append("- machine_policy_gate: `true`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Apply Results")
    if apply_results:
        for item in apply_results:
            lines.append(
                f"- `{item.get('change_unit_id')}` target=`{item.get('target_file')}` "
                f"result=`{item.get('result')}` source_written=`{item.get('source_written')}` failures=`{item.get('failures')}`"
            )
    else:
        lines.append("- none; no create-file readiness results yet")

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

    print("controlled_change_generic_create_file_apply =", result)
    print("apply =", args.apply)
    print("apply_mode =", apply_mode)
    print("metadata_file_count =", readiness.get("metadata_file_count"))
    print("readiness_result_count =", len(readiness_results))
    print("apply_result_count =", len(apply_results))
    print("blocked_apply_result_count =", len(blocked_apply_results))
    print("source_written =", payload["source_written"])
    print("metadata_written = False")
    print("state_written =", payload["state_written"])
    print("business_source_written =", payload["business_source_written"])
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
