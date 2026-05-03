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

AUDITOR_ID = "learning-v2-fourth-loop-closure-accounting-auditor-v0"

TARGET_FILE = "public/about.html"
TARGET_FAMILY = "community.engagement_path"
CHANGE_UNIT_ID = "create-public-about-page-v0"

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

def latest_snapshot(pattern):
    files = sorted(SNAPSHOT_DIR.glob(pattern))
    if not files:
        return None
    return files[-1]

def normalize_applied_item(item):
    if isinstance(item, str):
        return {
            "raw": item,
            "target_file": item,
            "change_unit_id": item,
            "target_family": None,
        }
    if isinstance(item, dict):
        return {
            "raw": item,
            "target_file": item.get("target_file") or item.get("path") or item.get("file"),
            "change_unit_id": item.get("change_unit_id") or item.get("id") or item.get("target_id"),
            "target_family": item.get("target_family") or item.get("family"),
        }
    return {
        "raw": item,
        "target_file": None,
        "change_unit_id": None,
        "target_family": None,
    }

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

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    closed_snapshot = latest_snapshot("learning-v2-public-about-create-file-controlled-change-closed-*.md")

    ledger_path, ledger = latest_report("controlled-change-generic-create-file-ledger-acceptance-apply-*.json")
    isolated_path, isolated = latest_report("controlled-change-generic-create-file-isolated-validator-*.json")
    apply_path, apply_report = latest_report("controlled-change-generic-create-file-apply-apply-*.json")
    integrity_path, integrity = latest_report("system-integrity-*.json")
    drift_path, drift = latest_report("system-drift-audit-*.json")

    failures = []
    warnings = []
    accounting_gaps = []

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

    if not closed_snapshot:
        failures.append("missing_fourth_loop_closed_snapshot")

    for label, path, report in [
        ("create_file_ledger_acceptance_apply", ledger_path, ledger),
        ("create_file_isolated_validator", isolated_path, isolated),
        ("create_file_apply", apply_path, apply_report),
        ("system_integrity", integrity_path, integrity),
    ]:
        if not path:
            failures.append(f"missing_{label}_report")
        elif report.get("result") != "ok":
            failures.append(f"{label}_not_ok:{report.get('result')}")

    if not (WORKSPACE / TARGET_FILE).exists():
        failures.append(f"target_file_missing_on_disk:{TARGET_FILE}")

    if ledger.get("controlled_delta_paths") != [TARGET_FILE]:
        failures.append(f"ledger_controlled_delta_paths_unexpected:{ledger.get('controlled_delta_paths')}")

    if not ledger.get("new_dirty_freeze_path"):
        failures.append("ledger_new_dirty_freeze_path_missing")

    last_dirty_freeze = state.get("last_dirty_freeze") or {}
    last_freeze_summary = last_dirty_freeze.get("summary") or {}
    accepted_paths = last_freeze_summary.get("accepted_controlled_delta_paths") or []

    if TARGET_FILE not in accepted_paths:
        failures.append(f"last_dirty_freeze_missing_target:{accepted_paths}")

    last_acceptance = state.get("last_controlled_business_change_acceptance") or {}
    last_acceptance_targets = last_acceptance.get("target_files") or []

    if TARGET_FILE not in last_acceptance_targets:
        failures.append(f"last_controlled_business_change_acceptance_missing_target:{last_acceptance_targets}")

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

    applied_targets = state.get("applied_targets") or []
    normalized_applied_targets = [normalize_applied_item(x) for x in applied_targets]

    applied_target_files = sorted(set(
        x.get("target_file") for x in normalized_applied_targets if x.get("target_file")
    ))
    applied_change_units = sorted(set(
        x.get("change_unit_id") for x in normalized_applied_targets if x.get("change_unit_id")
    ))

    target_registered_in_applied_targets = TARGET_FILE in applied_target_files
    change_unit_registered_in_applied_targets = CHANGE_UNIT_ID in applied_change_units

    if not target_registered_in_applied_targets and not change_unit_registered_in_applied_targets:
        accounting_gaps.append("public_about_not_registered_in_state_applied_targets")

    disabled_families = state.get("disabled_target_families") or []
    if TARGET_FAMILY in disabled_families:
        warnings.append(f"target_family_disabled:{TARGET_FAMILY}")

    applied_targets_count = len(applied_targets)

    result = "ok" if not failures else "blocked"

    recommended_next_step = (
        "build_fourth_loop_accounting_repair_no_source_write"
        if result == "ok" and accounting_gaps
        else "build_four_controlled_loops_capability_summary"
        if result == "ok"
        else "fix_fourth_loop_closure_accounting_blockers"
    )

    out_json = REPORT_DIR / f"fourth-loop-closure-accounting-auditor-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"fourth-loop-closure-accounting-auditor-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "auditor_id": AUDITOR_ID,
        "result": result,
        "target_file": TARGET_FILE,
        "target_family": TARGET_FAMILY,
        "change_unit_id": CHANGE_UNIT_ID,
        "target_file_exists": (WORKSPACE / TARGET_FILE).exists(),
        "applied_targets_count": applied_targets_count,
        "target_registered_in_applied_targets": target_registered_in_applied_targets,
        "change_unit_registered_in_applied_targets": change_unit_registered_in_applied_targets,
        "accounting_gaps": accounting_gaps,
        "last_dirty_freeze": last_dirty_freeze,
        "last_controlled_business_change_acceptance": last_acceptance,
        "closed_snapshot": str(closed_snapshot) if closed_snapshot else None,
        "ledger_acceptance_apply_report": str(ledger_path) if ledger_path else None,
        "isolated_validator_report": str(isolated_path) if isolated_path else None,
        "create_file_apply_report": str(apply_path) if apply_path else None,
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
        "warnings": warnings,
        "failures": failures,
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Fourth Loop Closure Accounting Auditor")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- auditor_id: `{AUDITOR_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- target_file: `{TARGET_FILE}`")
    lines.append(f"- target_file_exists: `{str(payload['target_file_exists']).lower()}`")
    lines.append(f"- applied_targets_count: `{applied_targets_count}`")
    lines.append(f"- target_registered_in_applied_targets: `{str(target_registered_in_applied_targets).lower()}`")
    lines.append(f"- change_unit_registered_in_applied_targets: `{str(change_unit_registered_in_applied_targets).lower()}`")
    lines.append(f"- accounting_gaps: `{accounting_gaps}`")
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

    print("fourth_loop_closure_accounting_auditor =", result)
    print("target_file =", TARGET_FILE)
    print("target_file_exists =", payload["target_file_exists"])
    print("applied_targets_count =", applied_targets_count)
    print("target_registered_in_applied_targets =", target_registered_in_applied_targets)
    print("change_unit_registered_in_applied_targets =", change_unit_registered_in_applied_targets)
    print("accounting_gaps =", json.dumps(accounting_gaps, ensure_ascii=False))
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
