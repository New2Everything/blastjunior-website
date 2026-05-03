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

GATE_ID = "learning-v2-controlled-change-generic-policy-gate-v0"

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

def check_dry_run_result(item):
    failures = []
    warnings = []

    if item.get("result") != "ok":
        failures.append(f"dry_run_result_not_ok:{item.get('result')}")

    if item.get("source_written") is not False:
        failures.append(f"source_written_not_false:{item.get('source_written')}")

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
    elif item.get("added_line_count") > 30:
        failures.append(f"added_line_count_too_large:{item.get('added_line_count')}")

    if item.get("changed_in_dry_run") is not True:
        warnings.append(f"changed_in_dry_run_not_true:{item.get('changed_in_dry_run')}")

    if item.get("target_file") in ["public/index.html", "public/gallery.html", "public/news.html"]:
        failures.append(f"target_file_already_closed:{item.get('target_file')}")

    return failures, warnings

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    metadata_validator_path, metadata_validator = latest_report("controlled-change-lifecycle-metadata-validator-*.json")
    dry_runner_path, dry_runner = latest_report("controlled-change-generic-dry-run-runner-*.json")
    duplication_guard_path, duplication_guard = latest_report("controlled-change-duplication-guard-*.json")
    readiness_path, readiness = latest_report("next-loop-readiness-auditor-*.json")
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

    if not duplication_guard_path:
        failures.append("missing_duplication_guard_report")
    elif duplication_guard.get("result") != "ok":
        failures.append(f"duplication_guard_not_ok:{duplication_guard.get('result')}")

    guard_recommendation = duplication_guard.get("recommendation") or {}
    if guard_recommendation.get("fourth_loop_allowed_now") is not False:
        failures.append(f"duplication_guard_allows_fourth_loop_unexpected:{guard_recommendation.get('fourth_loop_allowed_now')}")

    if not readiness_path:
        failures.append("missing_next_loop_readiness_report")
    elif readiness.get("result") != "ok":
        failures.append(f"next_loop_readiness_not_ok:{readiness.get('result')}")

    if readiness.get("fourth_loop_allowed_now") is not False:
        failures.append(f"readiness_allows_fourth_loop_unexpected:{readiness.get('fourth_loop_allowed_now')}")

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

    dry_run_results = dry_runner.get("dry_run_results") or []
    gate_results = []

    for item in dry_run_results:
        item_failures, item_warnings = check_dry_run_result(item)
        decision = "allow_next_generic_readiness" if not item_failures else "blocked"

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

    blocked_gate_results = [x for x in gate_results if x.get("decision") != "allow_next_generic_readiness"]

    if blocked_gate_results:
        failures.append(f"blocked_generic_gate_results:{len(blocked_gate_results)}")

    result = "ok" if not failures else "blocked"

    if dry_runner.get("metadata_file_count", 0) == 0:
        gate_mode = "no_metadata_safe_noop"
        recommended_next_step = "build_controlled_change_generic_readiness"
    else:
        gate_mode = "metadata_dry_run_policy_checked"
        recommended_next_step = "build_controlled_change_generic_readiness" if result == "ok" else "fix_generic_policy_gate_blockers"

    out_json = REPORT_DIR / f"controlled-change-generic-policy-gate-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"controlled-change-generic-policy-gate-{stamp()}.md"

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
        "metadata_validator_report": str(metadata_validator_path) if metadata_validator_path else None,
        "generic_dry_run_runner_report": str(dry_runner_path) if dry_runner_path else None,
        "duplication_guard_report": str(duplication_guard_path) if duplication_guard_path else None,
        "next_loop_readiness_auditor": str(readiness_path) if readiness_path else None,
        "integrity_report": str(integrity_path) if integrity_path else None,
        "recommended_next_step": recommended_next_step,
        "policy": {
            "gate_only": True,
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
    lines.append("# Learning V2 Controlled Change Generic Policy Gate")
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
    lines.append("- gate_only: `true`")
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
    lines.append("## Gate Results")
    if gate_results:
        for item in gate_results:
            lines.append(
                f"- `{item.get('change_unit_id')}` target=`{item.get('target_file')}` "
                f"decision=`{item.get('decision')}` failures=`{item.get('failures')}`"
            )
    else:
        lines.append("- none; no metadata dry-run results yet")

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

    print("controlled_change_generic_policy_gate =", result)
    print("gate_mode =", gate_mode)
    print("metadata_file_count =", dry_runner.get("metadata_file_count"))
    print("dry_run_result_count =", len(dry_run_results))
    print("gate_result_count =", len(gate_results))
    print("blocked_gate_result_count =", len(blocked_gate_results))
    print("recommended_next_step =", recommended_next_step)
    print("gate_only = True")
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
