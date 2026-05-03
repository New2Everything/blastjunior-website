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

READINESS_ID = "learning-v2-controlled-change-generic-readiness-v0"

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

def check_gate_result_ready(item, closed_target_files):
    failures = []
    warnings = []

    if item.get("decision") != "allow_next_generic_readiness":
        failures.append(f"gate_decision_not_allow:{item.get('decision')}")

    target_file = item.get("target_file")
    if not target_file:
        failures.append("target_file_missing")
    elif target_file in closed_target_files:
        failures.append(f"target_file_already_closed:{target_file}")
    elif not (WORKSPACE / target_file).exists():
        failures.append(f"target_file_does_not_exist:{target_file}")

    if item.get("failures"):
        failures.append("gate_result_has_failures")

    if item.get("warnings"):
        warnings.extend([f"gate_warning:{x}" for x in item.get("warnings")])

    return failures, warnings

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    metadata_validator_path, metadata_validator = latest_report("controlled-change-lifecycle-metadata-validator-*.json")
    dry_runner_path, dry_runner = latest_report("controlled-change-generic-dry-run-runner-*.json")
    policy_gate_path, policy_gate = latest_report("controlled-change-generic-policy-gate-*.json")
    duplication_guard_path, duplication_guard = latest_report("controlled-change-duplication-guard-*.json")
    next_loop_path, next_loop = latest_report("next-loop-readiness-auditor-*.json")
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

    if not duplication_guard_path:
        failures.append("missing_duplication_guard_report")
    elif duplication_guard.get("result") != "ok":
        failures.append(f"duplication_guard_not_ok:{duplication_guard.get('result')}")

    guard_recommendation = duplication_guard.get("recommendation") or {}
    if guard_recommendation.get("fourth_loop_allowed_now") is not False:
        failures.append(f"duplication_guard_allows_fourth_loop_unexpected:{guard_recommendation.get('fourth_loop_allowed_now')}")

    if not next_loop_path:
        failures.append("missing_next_loop_readiness_auditor_report")
    elif next_loop.get("result") != "ok":
        failures.append(f"next_loop_readiness_not_ok:{next_loop.get('result')}")

    if next_loop.get("fourth_loop_allowed_now") is not False:
        failures.append(f"next_loop_allows_fourth_loop_unexpected:{next_loop.get('fourth_loop_allowed_now')}")

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

    closed_target_files = set(duplication_guard.get("closed_target_files") or [])
    gate_results = policy_gate.get("gate_results") or []

    readiness_results = []
    for item in gate_results:
        item_failures, item_warnings = check_gate_result_ready(item, closed_target_files)
        ready = not item_failures
        readiness_results.append({
            "change_unit_id": item.get("change_unit_id"),
            "target_family": item.get("target_family"),
            "target_file": item.get("target_file"),
            "metadata_file": item.get("metadata_file"),
            "dry_run_report": item.get("dry_run_report"),
            "ready_to_open_source_change_gate": ready,
            "decision": "ready_for_generic_apply_self_check" if ready else "blocked",
            "failures": item_failures,
            "warnings": item_warnings,
        })

    blocked_readiness_results = [
        x for x in readiness_results
        if x.get("ready_to_open_source_change_gate") is not True
    ]

    if blocked_readiness_results:
        failures.append(f"blocked_generic_readiness_results:{len(blocked_readiness_results)}")

    if policy_gate.get("metadata_file_count", 0) == 0:
        readiness_mode = "no_metadata_safe_noop"
        recommended_next_step = "build_controlled_change_generic_apply"
    else:
        readiness_mode = "metadata_policy_gate_checked"
        recommended_next_step = "build_controlled_change_generic_apply" if not failures else "fix_generic_readiness_blockers"

    result = "ok" if not failures else "blocked"

    out_json = REPORT_DIR / f"controlled-change-generic-readiness-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"controlled-change-generic-readiness-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "readiness_id": READINESS_ID,
        "result": result,
        "readiness_mode": readiness_mode,
        "metadata_file_count": policy_gate.get("metadata_file_count"),
        "gate_result_count": len(gate_results),
        "readiness_result_count": len(readiness_results),
        "blocked_readiness_result_count": len(blocked_readiness_results),
        "readiness_results": readiness_results,
        "metadata_validator_report": str(metadata_validator_path) if metadata_validator_path else None,
        "generic_dry_run_runner_report": str(dry_runner_path) if dry_runner_path else None,
        "generic_policy_gate_report": str(policy_gate_path) if policy_gate_path else None,
        "duplication_guard_report": str(duplication_guard_path) if duplication_guard_path else None,
        "next_loop_readiness_auditor": str(next_loop_path) if next_loop_path else None,
        "integrity_report": str(integrity_path) if integrity_path else None,
        "recommended_next_step": recommended_next_step,
        "policy": {
            "readiness_only": True,
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
    lines.append("# Learning V2 Controlled Change Generic Readiness")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- readiness_id: `{READINESS_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- readiness_mode: `{readiness_mode}`")
    lines.append(f"- metadata_file_count: `{payload['metadata_file_count']}`")
    lines.append(f"- gate_result_count: `{len(gate_results)}`")
    lines.append(f"- readiness_result_count: `{len(readiness_results)}`")
    lines.append(f"- blocked_readiness_result_count: `{len(blocked_readiness_results)}`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")
    lines.append("- readiness_only: `true`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- fourth_loop_started: `false`")
    lines.append("- human_review_required: `false`")
    lines.append("- machine_policy_gate: `true`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Readiness Results")
    if readiness_results:
        for item in readiness_results:
            lines.append(
                f"- `{item.get('change_unit_id')}` target=`{item.get('target_file')}` "
                f"decision=`{item.get('decision')}` failures=`{item.get('failures')}`"
            )
    else:
        lines.append("- none; no generic gate results yet")

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

    print("controlled_change_generic_readiness =", result)
    print("readiness_mode =", readiness_mode)
    print("metadata_file_count =", policy_gate.get("metadata_file_count"))
    print("gate_result_count =", len(gate_results))
    print("readiness_result_count =", len(readiness_results))
    print("blocked_readiness_result_count =", len(blocked_readiness_results))
    print("recommended_next_step =", recommended_next_step)
    print("readiness_only = True")
    print("state_written = False")
    print("business_source_written = False")
    print("source_change_gate_opened = False")
    print("fourth_loop_started = False")
    print("human_review_required = False")
    print("machine_policy_gate = True")
    print("git_commit = False")
    print("git_push = False")
    print("deploy = False")
    print("report_json =", out_json)
    print("report_md =", out_md)

    if warnings:
        print("warnings =", json.dumps(warnings, ensure_ascii=False))
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
