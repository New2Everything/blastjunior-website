#!/usr/bin/env python3
import argparse
import json
import shutil
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

APPLY_ID = "learning-v2-controlled-change-generic-apply-v0"

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

def build_proposed_from_metadata(meta):
    target_file = meta.get("target_file")
    target_path = WORKSPACE / target_file

    insertion = meta.get("insertion") or {}
    anchor = insertion.get("anchor") or ""
    block = insertion.get("block") or ""

    original = target_path.read_text(encoding="utf-8", errors="ignore")
    proposed = original.replace(anchor, anchor + block, 1)

    return original, proposed

def validate_apply_candidate(item):
    failures = []
    warnings = []

    target_file = item.get("target_file")
    metadata_file = item.get("metadata_file")

    if item.get("ready_to_open_source_change_gate") is not True:
        failures.append(f"readiness_not_true:{item.get('ready_to_open_source_change_gate')}")

    if item.get("decision") != "ready_for_generic_apply_self_check":
        failures.append(f"decision_not_ready:{item.get('decision')}")

    if not metadata_file or not Path(metadata_file).exists():
        failures.append(f"metadata_file_missing:{metadata_file}")

    if not target_file:
        failures.append("target_file_missing")
    elif not (WORKSPACE / target_file).exists():
        failures.append(f"target_file_does_not_exist:{target_file}")

    if target_file in ["public/index.html", "public/gallery.html", "public/news.html"]:
        failures.append(f"target_file_already_closed:{target_file}")

    if item.get("failures"):
        failures.append("readiness_item_has_failures")

    if item.get("warnings"):
        warnings.extend([f"readiness_warning:{x}" for x in item.get("warnings")])

    return failures, warnings

def validate_metadata_for_apply(meta):
    failures = []

    if meta.get("risk") != "low":
        failures.append(f"risk_not_low:{meta.get('risk')}")

    if meta.get("allowed_stage") not in ["dry_run_only"]:
        failures.append(f"allowed_stage_not_dry_run_only:{meta.get('allowed_stage')}")

    target_file = meta.get("target_file")
    acceptance = meta.get("acceptance") or {}
    if acceptance.get("expected_target_file") != target_file:
        failures.append(f"acceptance_target_mismatch:{acceptance.get('expected_target_file')}!={target_file}")

    safety = meta.get("safety") or {}
    if safety.get("git_commit") is not False:
        failures.append(f"safety_git_commit_not_false:{safety.get('git_commit')}")
    if safety.get("git_push") is not False:
        failures.append(f"safety_git_push_not_false:{safety.get('git_push')}")
    if safety.get("deploy") is not False:
        failures.append(f"safety_deploy_not_false:{safety.get('deploy')}")
    if safety.get("allow_removed_lines") is not False:
        failures.append(f"safety_allow_removed_lines_not_false:{safety.get('allow_removed_lines')}")

    return failures

def apply_one(item, run_stamp, actually_apply):
    failures, warnings = validate_apply_candidate(item)

    metadata_file = item.get("metadata_file")
    meta = load_json(metadata_file, default={}) if metadata_file else {}

    if meta:
        failures.extend(validate_metadata_for_apply(meta))

    target_file = item.get("target_file")
    target_path = WORKSPACE / target_file if target_file else None

    changed_in_apply_plan = False
    backup_path = None
    source_written = False
    gate_opened_during_apply = False
    gate_closed_after_apply = False

    if not failures:
        original, proposed = build_proposed_from_metadata(meta)
        changed_in_apply_plan = proposed != original

        if not changed_in_apply_plan:
            failures.append("proposed_no_change")

    if actually_apply and not failures:
        try:
            state = load_json(STATE, default={})
            state = open_source_gate_for_apply(state)
            save_json(STATE, state)
            gate_opened_during_apply = True

            safe_id = str(item.get("change_unit_id") or "generic-change").replace("/", "-")
            backup_path = BACKUP_DIR / f"{safe_id}-{target_file.replace('/', '-')}-before-generic-apply-{run_stamp}.bak"
            shutil.copy2(target_path, backup_path)
            target_path.write_text(proposed, encoding="utf-8")
            source_written = True
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
        "source_written": source_written,
        "backup_path": str(backup_path) if backup_path else None,
        "gate_opened_during_apply": gate_opened_during_apply,
        "gate_closed_after_apply": gate_closed_after_apply,
        "state_written": bool(actually_apply and result == "ok"),
        "business_source_written": source_written,
        "source_change_gate_opened": False,
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
    ap.add_argument("--apply", action="store_true", help="perform controlled generic source write")
    args = ap.parse_args()

    run_stamp = stamp()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    metadata_validator_path, metadata_validator = latest_report("controlled-change-lifecycle-metadata-validator-*.json")
    dry_runner_path, dry_runner = latest_report("controlled-change-generic-dry-run-runner-*.json")
    policy_gate_path, policy_gate = latest_report("controlled-change-generic-policy-gate-*.json")
    readiness_path, readiness = latest_report("controlled-change-generic-readiness-*.json")
    duplication_guard_path, duplication_guard = latest_report("controlled-change-duplication-guard-*.json")
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

    if not metadata_validator_path:
        failures.append("missing_metadata_validator_report")
    elif metadata_validator.get("result") != "ok":
        failures.append(f"metadata_validator_not_ok:{metadata_validator.get('result')}")

    if not dry_runner_path:
        failures.append("missing_generic_dry_run_runner_report")
    elif dry_runner.get("result") != "ok":
        failures.append(f"generic_dry_run_runner_not_ok:{dry_runner.get('result')}")

    if dry_runner.get("blocked_dry_run_count") not in (0, None):
        failures.append(f"blocked_dry_run_count_not_zero:{dry_runner.get('blocked_dry_run_count')}")

    if not policy_gate_path:
        failures.append("missing_generic_policy_gate_report")
    elif policy_gate.get("result") != "ok":
        failures.append(f"generic_policy_gate_not_ok:{policy_gate.get('result')}")

    if policy_gate.get("blocked_gate_result_count") not in (0, None):
        failures.append(f"blocked_gate_result_count_not_zero:{policy_gate.get('blocked_gate_result_count')}")

    if not readiness_path:
        failures.append("missing_generic_readiness_report")
    elif readiness.get("result") != "ok":
        failures.append(f"generic_readiness_not_ok:{readiness.get('result')}")

    if readiness.get("blocked_readiness_result_count") not in (0, None):
        failures.append(f"blocked_readiness_result_count_not_zero:{readiness.get('blocked_readiness_result_count')}")

    if not duplication_guard_path:
        failures.append("missing_duplication_guard_report")
    elif duplication_guard.get("result") != "ok":
        failures.append(f"duplication_guard_not_ok:{duplication_guard.get('result')}")

    guard_recommendation = duplication_guard.get("recommendation") or {}
    if guard_recommendation.get("fourth_loop_allowed_now") is not False:
        failures.append(f"duplication_guard_allows_fourth_loop_unexpected:{guard_recommendation.get('fourth_loop_allowed_now')}")

    if not integrity_path:
        failures.append("missing_system_integrity_report")
    elif integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

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

    readiness_results = readiness.get("readiness_results") or []
    apply_results = []

    if not failures:
        for item in readiness_results:
            apply_results.append(apply_one(item, run_stamp, args.apply))

    blocked_apply_results = [x for x in apply_results if x.get("result") != "ok"]

    if blocked_apply_results:
        failures.append(f"blocked_generic_apply_results:{len(blocked_apply_results)}")

    if readiness.get("metadata_file_count", 0) == 0:
        apply_mode = "no_metadata_safe_noop"
        recommended_next_step = "build_controlled_change_generic_isolated_validator"
    else:
        apply_mode = "generic_apply_self_check" if not args.apply else "generic_apply"
        recommended_next_step = (
            "build_controlled_change_generic_isolated_validator"
            if not failures
            else "fix_controlled_change_generic_apply_blockers"
        )

    result = "ok" if not failures else "blocked"

    # Always close source gate at process end, including self-check/no-op.
    latest_state = load_json(STATE, default={})
    latest_state = close_source_gate(latest_state)
    save_json(STATE, latest_state)

    out_json = REPORT_DIR / f"controlled-change-generic-apply-{'apply' if args.apply else 'dry-run'}-{run_stamp}.json"
    out_md = SNAPSHOT_DIR / f"controlled-change-generic-apply-{'apply' if args.apply else 'dry-run'}-{run_stamp}.md"

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
        "metadata_validator_report": str(metadata_validator_path) if metadata_validator_path else None,
        "generic_dry_run_runner_report": str(dry_runner_path) if dry_runner_path else None,
        "generic_policy_gate_report": str(policy_gate_path) if policy_gate_path else None,
        "generic_readiness_report": str(readiness_path) if readiness_path else None,
        "duplication_guard_report": str(duplication_guard_path) if duplication_guard_path else None,
        "integrity_report": str(integrity_path) if integrity_path else None,
        "source_written": any(x.get("source_written") for x in apply_results),
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
    lines.append("# Learning V2 Controlled Change Generic Apply")
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
        lines.append("- none; no generic readiness results yet")

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

    print("controlled_change_generic_apply =", result)
    print("apply =", args.apply)
    print("apply_mode =", apply_mode)
    print("metadata_file_count =", readiness.get("metadata_file_count"))
    print("readiness_result_count =", len(readiness_results))
    print("apply_result_count =", len(apply_results))
    print("blocked_apply_result_count =", len(blocked_apply_results))
    print("source_written =", payload["source_written"])
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
