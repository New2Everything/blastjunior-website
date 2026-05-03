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

ACCEPTANCE_ID = "learning-v2-controlled-change-generic-ledger-acceptance-v0"

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

def load_release_gate_module():
    path = WORKSPACE / "scripts/learning-v2-release-gate.py"
    spec = importlib.util.spec_from_file_location("learning_v2_release_gate_runtime", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def close_all_permissions(state):
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
    ap.add_argument("--apply", action="store_true", help="accept validated generic source delta into dirty-freeze")
    args = ap.parse_args()

    run_stamp = stamp()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    metadata_validator_path, metadata_validator = latest_report("controlled-change-lifecycle-metadata-validator-*.json")
    dry_runner_path, dry_runner = latest_report("controlled-change-generic-dry-run-runner-*.json")
    policy_gate_path, policy_gate = latest_report("controlled-change-generic-policy-gate-*.json")
    readiness_path, readiness = latest_report("controlled-change-generic-readiness-*.json")
    apply_path, apply_report = latest_report("controlled-change-generic-apply-*.json")
    isolated_path, isolated = latest_report("controlled-change-generic-isolated-validator-*.json")
    duplication_guard_path, duplication_guard = latest_report("controlled-change-duplication-guard-*.json")
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
        ("metadata_validator", metadata_validator_path, metadata_validator),
        ("generic_dry_run_runner", dry_runner_path, dry_runner),
        ("generic_policy_gate", policy_gate_path, policy_gate),
        ("generic_readiness", readiness_path, readiness),
        ("generic_apply", apply_path, apply_report),
        ("generic_isolated_validator", isolated_path, isolated),
        ("duplication_guard", duplication_guard_path, duplication_guard),
    ]:
        if not path:
            failures.append(f"missing_{label}_report")
        elif report.get("result") != "ok":
            failures.append(f"{label}_not_ok:{report.get('result')}")

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

    if apply_report.get("source_written") is not False and not apply_report.get("apply_results"):
        failures.append("apply_source_written_true_but_missing_apply_results")

    if isolated.get("source_written") is not False:
        failures.append(f"isolated_validator_source_written_not_false:{isolated.get('source_written')}")

    validation_results = isolated.get("validation_results") or []
    blocked_validation_results = [
        x for x in validation_results
        if x.get("result") != "ok"
    ]

    if blocked_validation_results:
        failures.append(f"blocked_validation_results:{len(blocked_validation_results)}")

    metadata_file_count = isolated.get("metadata_file_count", 0)

    acceptance_results = []
    controlled_delta_paths = []

    if not failures:
        for item in validation_results:
            target_file = item.get("target_file")
            if not target_file:
                acceptance_results.append({
                    "result": "blocked",
                    "reason": "target_file_missing",
                    "item": item,
                })
                continue

            if item.get("isolated_delta_interpretation") != "backup_to_current_delta_is_generic_target_only":
                acceptance_results.append({
                    "result": "blocked",
                    "target_file": target_file,
                    "reason": f"isolated_delta_not_clean:{item.get('isolated_delta_interpretation')}",
                })
                continue

            controlled_delta_paths.append(target_file)
            acceptance_results.append({
                "result": "ok",
                "target_file": target_file,
                "change_unit_id": item.get("change_unit_id"),
                "metadata_file": item.get("metadata_file"),
            })

    blocked_acceptance_results = [
        x for x in acceptance_results
        if x.get("result") != "ok"
    ]

    if blocked_acceptance_results:
        failures.append(f"blocked_generic_acceptance_results:{len(blocked_acceptance_results)}")

    if metadata_file_count == 0:
        acceptance_mode = "no_metadata_safe_noop"
        recommended_next_step = "close_generic_lifecycle_scaffold_summary"
    else:
        acceptance_mode = "generic_ledger_acceptance"
        recommended_next_step = (
            "close_generic_lifecycle_scaffold_summary"
            if not failures
            else "fix_controlled_change_generic_ledger_acceptance_blockers"
        )

    result = "ok" if not failures else "blocked"

    new_dirty_freeze_path = None
    state_written = False

    if args.apply and result == "ok" and controlled_delta_paths:
        release_gate = load_release_gate_module()
        entries = release_gate.current_dirty_entries()
        business = [x for x in entries if x.get("class") == "business_source_blocked"]
        freeze_compare = release_gate.compare_business_freeze(state, business)

        changed_paths = sorted([x.get("path") for x in freeze_compare.get("changed", []) if x.get("path")])
        new_business_paths = sorted([x.get("path") for x in freeze_compare.get("new_business_dirty", []) if x.get("path")])
        missing_or_cleaned_paths = sorted([x.get("path") for x in freeze_compare.get("missing_or_cleaned", []) if x.get("path")])

        actual_delta_paths = sorted(set(changed_paths + new_business_paths))

        if actual_delta_paths != sorted(set(controlled_delta_paths)):
            failures.append(f"actual_delta_paths_mismatch:{actual_delta_paths}!={sorted(set(controlled_delta_paths))}")

        if missing_or_cleaned_paths:
            failures.append(f"missing_or_cleaned_business_paths_present:{missing_or_cleaned_paths}")

        result = "ok" if not failures else "blocked"

        if result == "ok":
            freeze_path = FREEZE_DIR / f"dirty-freeze-controlled-generic-change-{run_stamp}.json"
            new_freeze = {
                "generated_at": now_iso(),
                "freeze_type": "generic_controlled_business_source_change_acceptance",
                "acceptance_id": ACCEPTANCE_ID,
                "accepted_controlled_delta_paths": actual_delta_paths,
                "reason": "Accept validated generic controlled source change after isolated backup-to-current verification.",
                "previous_dirty_freeze": state.get("last_dirty_freeze"),
                "source_reports": {
                    "metadata_validator": str(metadata_validator_path),
                    "generic_dry_run_runner": str(dry_runner_path),
                    "generic_policy_gate": str(policy_gate_path),
                    "generic_readiness": str(readiness_path),
                    "generic_apply": str(apply_path),
                    "generic_isolated_validator": str(isolated_path),
                },
                "freeze_compare_before_acceptance": freeze_compare,
                "business_source_blocked": business,
                "summary": {
                    "total_dirty": len(entries),
                    "business_source_blocked_count": len(business),
                    "accepted_controlled_delta_paths": actual_delta_paths,
                    "changed_business_paths": changed_paths,
                    "new_business_dirty_paths": new_business_paths,
                    "missing_or_cleaned_business_paths": missing_or_cleaned_paths,
                    "commit_allowed": False,
                    "push_allowed": False,
                    "deploy_allowed": False,
                },
                "policy": {
                    "source_written_by_acceptance": False,
                    "state_written": True,
                    "human_review_required": False,
                    "machine_policy_gate": True,
                    "git_commit": False,
                    "git_push": False,
                    "deploy": False,
                },
            }

            save_json(freeze_path, new_freeze)
            new_dirty_freeze_path = str(freeze_path)

            state["last_dirty_freeze"] = {
                "generated_at": new_freeze["generated_at"],
                "path": str(freeze_path),
                "summary": new_freeze["summary"],
            }

            state["last_controlled_business_change_acceptance"] = {
                "generated_at": new_freeze["generated_at"],
                "acceptance_id": ACCEPTANCE_ID,
                "target_files": actual_delta_paths,
                "acceptance_type": "generic_controlled_business_source_change_acceptance",
                "new_dirty_freeze_path": str(freeze_path),
                "source_written_by_acceptance": False,
                "human_review_required": False,
                "machine_policy_gate": True,
                "git_commit": False,
                "git_push": False,
                "deploy": False,
            }

            state = close_all_permissions(state)
            save_json(STATE, state)
            state_written = True

    elif args.apply and result == "ok" and not controlled_delta_paths:
        # Explicit no-op apply: close permissions defensively but do not update dirty-freeze.
        state = close_all_permissions(state)
        save_json(STATE, state)

    out_json = REPORT_DIR / f"controlled-change-generic-ledger-acceptance-{'apply' if args.apply else 'dry-run'}-{run_stamp}.json"
    out_md = SNAPSHOT_DIR / f"controlled-change-generic-ledger-acceptance-{'apply' if args.apply else 'dry-run'}-{run_stamp}.md"

    payload = {
        "generated_at": now_iso(),
        "acceptance_id": ACCEPTANCE_ID,
        "result": result,
        "apply": args.apply,
        "acceptance_mode": acceptance_mode,
        "metadata_file_count": metadata_file_count,
        "validation_result_count": len(validation_results),
        "acceptance_result_count": len(acceptance_results),
        "blocked_acceptance_result_count": len(blocked_acceptance_results),
        "controlled_delta_paths": sorted(set(controlled_delta_paths)),
        "acceptance_results": acceptance_results,
        "new_dirty_freeze_path": new_dirty_freeze_path,
        "metadata_validator_report": str(metadata_validator_path) if metadata_validator_path else None,
        "generic_dry_run_runner_report": str(dry_runner_path) if dry_runner_path else None,
        "generic_policy_gate_report": str(policy_gate_path) if policy_gate_path else None,
        "generic_readiness_report": str(readiness_path) if readiness_path else None,
        "generic_apply_report": str(apply_path) if apply_path else None,
        "generic_isolated_validator_report": str(isolated_path) if isolated_path else None,
        "integrity_report": str(integrity_path) if integrity_path else None,
        "source_written_by_acceptance": False,
        "state_written": state_written,
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
            "ledger_acceptance_only": True,
            "source_written_by_acceptance": False,
            "state_written": state_written,
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
    lines.append("# Learning V2 Controlled Change Generic Ledger Acceptance")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- acceptance_id: `{ACCEPTANCE_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- apply: `{str(args.apply).lower()}`")
    lines.append(f"- acceptance_mode: `{acceptance_mode}`")
    lines.append(f"- metadata_file_count: `{metadata_file_count}`")
    lines.append(f"- validation_result_count: `{len(validation_results)}`")
    lines.append(f"- acceptance_result_count: `{len(acceptance_results)}`")
    lines.append(f"- blocked_acceptance_result_count: `{len(blocked_acceptance_results)}`")
    lines.append(f"- controlled_delta_paths: `{sorted(set(controlled_delta_paths))}`")
    lines.append(f"- new_dirty_freeze_path: `{new_dirty_freeze_path}`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")
    lines.append("- ledger_acceptance_only: `true`")
    lines.append("- source_written_by_acceptance: `false`")
    lines.append(f"- state_written: `{str(state_written).lower()}`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- fourth_loop_started: `false`")
    lines.append("- human_review_required: `false`")
    lines.append("- machine_policy_gate: `true`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")

    if acceptance_results:
        lines.append("")
        lines.append("## Acceptance Results")
        for item in acceptance_results:
            lines.append(f"- `{item.get('target_file')}` result=`{item.get('result')}`")

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

    print("controlled_change_generic_ledger_acceptance =", result)
    print("apply =", args.apply)
    print("acceptance_mode =", acceptance_mode)
    print("metadata_file_count =", metadata_file_count)
    print("validation_result_count =", len(validation_results))
    print("acceptance_result_count =", len(acceptance_results))
    print("blocked_acceptance_result_count =", len(blocked_acceptance_results))
    print("controlled_delta_paths =", sorted(set(controlled_delta_paths)))
    print("new_dirty_freeze_path =", new_dirty_freeze_path)
    print("source_written_by_acceptance = False")
    print("state_written =", state_written)
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
