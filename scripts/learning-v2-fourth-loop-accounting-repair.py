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

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

REPAIR_ID = "learning-v2-fourth-loop-accounting-repair-v0"

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

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def latest_report(pattern):
    files = sorted(REPORT_DIR.glob(pattern))
    if not files:
        return None, {}
    p = files[-1]
    return p, load_json(p, default={})

def latest_snapshot(pattern):
    files = sorted(SNAPSHOT_DIR.glob(pattern))
    return files[-1] if files else None

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
    ap.add_argument("--apply", action="store_true", help="repair state.applied_targets accounting only")
    args = ap.parse_args()

    run_stamp = stamp()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    auditor_path, auditor = latest_report("fourth-loop-closure-accounting-auditor-*.json")
    ledger_path, ledger = latest_report("controlled-change-generic-create-file-ledger-acceptance-apply-*.json")
    integrity_path, integrity = latest_report("system-integrity-*.json")
    closed_snapshot = latest_snapshot("learning-v2-public-about-create-file-controlled-change-closed-*.md")

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

    if not (WORKSPACE / TARGET_FILE).exists():
        failures.append(f"target_file_missing:{TARGET_FILE}")

    if not auditor_path:
        failures.append("missing_fourth_loop_accounting_auditor_report")
    elif auditor.get("result") != "ok":
        failures.append(f"accounting_auditor_not_ok:{auditor.get('result')}")

    expected_gap = "public_about_not_registered_in_state_applied_targets"
    accounting_gaps = auditor.get("accounting_gaps") or []
    if expected_gap not in accounting_gaps:
        warnings.append(f"expected_gap_not_present:{accounting_gaps}")

    if not ledger_path:
        failures.append("missing_create_file_ledger_acceptance_apply_report")
    elif ledger.get("result") != "ok":
        failures.append(f"ledger_acceptance_apply_not_ok:{ledger.get('result')}")

    if ledger.get("controlled_delta_paths") != [TARGET_FILE]:
        failures.append(f"ledger_controlled_delta_paths_unexpected:{ledger.get('controlled_delta_paths')}")

    if not ledger.get("new_dirty_freeze_path"):
        failures.append("ledger_new_dirty_freeze_path_missing")

    if not integrity_path:
        failures.append("missing_system_integrity_report")
    elif integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if not closed_snapshot:
        failures.append("missing_fourth_loop_closed_snapshot")

    applied_targets = state.get("applied_targets") or []
    normalized = [normalize_applied_item(x) for x in applied_targets]

    already_has_target_file = any(x.get("target_file") == TARGET_FILE for x in normalized)
    already_has_change_unit = any(x.get("change_unit_id") == CHANGE_UNIT_ID for x in normalized)

    if already_has_target_file or already_has_change_unit:
        warnings.append("target_already_present_in_applied_targets")

    new_entry = {
        "generated_at": now_iso(),
        "repair_id": REPAIR_ID,
        "change_unit_id": CHANGE_UNIT_ID,
        "target_family": TARGET_FAMILY,
        "target_file": TARGET_FILE,
        "change_type": "create_file_from_template",
        "status": "closed",
        "source": "fourth_loop_accounting_repair",
        "accepted_controlled_delta_paths": [TARGET_FILE],
        "ledger_acceptance_apply_report": str(ledger_path) if ledger_path else None,
        "new_dirty_freeze_path": ledger.get("new_dirty_freeze_path"),
        "closed_snapshot": str(closed_snapshot) if closed_snapshot else None,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }

    before_count = len(applied_targets)
    after_count = before_count
    state_written = False

    if args.apply and not failures:
        if not already_has_target_file and not already_has_change_unit:
            applied_targets.append(new_entry)
            state["applied_targets"] = applied_targets
            after_count = len(applied_targets)

        state["last_fourth_loop_accounting_repair"] = {
            "generated_at": new_entry["generated_at"],
            "repair_id": REPAIR_ID,
            "target_file": TARGET_FILE,
            "change_unit_id": CHANGE_UNIT_ID,
            "state_written": True,
            "before_applied_targets_count": before_count,
            "after_applied_targets_count": after_count,
            "ledger_acceptance_apply_report": str(ledger_path) if ledger_path else None,
            "new_dirty_freeze_path": ledger.get("new_dirty_freeze_path"),
            "source_written": False,
            "metadata_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        }

        state = close_permissions(state)
        save_json(STATE, state)
        state_written = True
    else:
        after_count = before_count + (0 if already_has_target_file or already_has_change_unit else 1)

    result = "ok" if not failures else "blocked"

    recommended_next_step = (
        "rerun_fourth_loop_closure_accounting_auditor"
        if args.apply and result == "ok"
        else "apply_fourth_loop_accounting_repair_no_source_write"
        if result == "ok"
        else "fix_fourth_loop_accounting_repair_blockers"
    )

    out_json = REPORT_DIR / f"fourth-loop-accounting-repair-{'apply' if args.apply else 'dry-run'}-{run_stamp}.json"
    out_md = SNAPSHOT_DIR / f"fourth-loop-accounting-repair-{'apply' if args.apply else 'dry-run'}-{run_stamp}.md"

    payload = {
        "generated_at": now_iso(),
        "repair_id": REPAIR_ID,
        "result": result,
        "apply": args.apply,
        "target_file": TARGET_FILE,
        "target_family": TARGET_FAMILY,
        "change_unit_id": CHANGE_UNIT_ID,
        "before_applied_targets_count": before_count,
        "after_applied_targets_count": after_count,
        "already_has_target_file": already_has_target_file,
        "already_has_change_unit": already_has_change_unit,
        "new_applied_target_entry": new_entry,
        "state_written": state_written,
        "source_written": False,
        "metadata_written": False,
        "business_source_written": False,
        "source_change_gate_opened": False,
        "fourth_loop_started": False,
        "human_review_required": False,
        "machine_policy_gate": True,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "accounting_auditor_report": str(auditor_path) if auditor_path else None,
        "ledger_acceptance_apply_report": str(ledger_path) if ledger_path else None,
        "integrity_report": str(integrity_path) if integrity_path else None,
        "recommended_next_step": recommended_next_step,
        "warnings": warnings,
        "failures": failures,
    }

    save_json(out_json, payload)

    lines = []
    lines.append("# Learning V2 Fourth Loop Accounting Repair")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- repair_id: `{REPAIR_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- apply: `{str(args.apply).lower()}`")
    lines.append(f"- target_file: `{TARGET_FILE}`")
    lines.append(f"- before_applied_targets_count: `{before_count}`")
    lines.append(f"- after_applied_targets_count: `{after_count}`")
    lines.append(f"- state_written: `{str(state_written).lower()}`")
    lines.append("- source_written: `false`")
    lines.append("- metadata_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- fourth_loop_started: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")

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

    print("fourth_loop_accounting_repair =", result)
    print("apply =", args.apply)
    print("target_file =", TARGET_FILE)
    print("before_applied_targets_count =", before_count)
    print("after_applied_targets_count =", after_count)
    print("already_has_target_file =", already_has_target_file)
    print("already_has_change_unit =", already_has_change_unit)
    print("state_written =", state_written)
    print("source_written = False")
    print("metadata_written = False")
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
