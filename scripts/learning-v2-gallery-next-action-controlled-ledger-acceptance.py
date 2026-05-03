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

ACCEPTANCE_ID = "learning-v2-gallery-next-action-controlled-ledger-acceptance-v0"
TARGET_FILE = "public/gallery.html"

REQUIRED_MARKERS = [
    "gallery-next-action",
    "gallery-next-action-title",
]

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
    Path(path).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

def latest_report(pattern):
    reports = sorted(REPORT_DIR.glob(pattern))
    if not reports:
        return None, {}
    p = reports[-1]
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

def report_flag(report, key):
    return find_key(report, key)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--apply",
        action="store_true",
        help="write new dirty freeze and update state.last_dirty_freeze",
    )
    args = ap.parse_args()

    run_stamp = stamp()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    isolated_path, isolated = latest_report("gallery-next-action-isolated-post-apply-validator-*.json")
    apply_path, apply_report = latest_report("gallery-next-action-source-change-apply-apply-*.json")
    gate_path, gate_report = latest_report("autonomous-change-policy-gate-*.json")
    readiness_path, readiness_report = latest_report("gallery-next-action-gate-readiness-*.json")

    failures = []
    warnings = []

    # Core mode / permission checks.
    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_closed:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    for key in [
        "source_changes_allowed",
        "git_commit_allowed",
        "git_push_allowed",
        "deploy_allowed",
    ]:
        if policy.get(key) is not False:
            failures.append(f"policy_{key}_not_false:{policy.get(key)}")

    # Isolated validator checks.
    if not isolated_path:
        failures.append("missing_gallery_isolated_post_apply_validator")

    if isolated.get("result") != "ok":
        failures.append(f"isolated_validator_not_ok:{isolated.get('result')}")

    if isolated.get("target_file") != TARGET_FILE:
        failures.append(f"isolated_target_not_gallery:{isolated.get('target_file')}")

    if isolated.get("required_markers_present") is not True:
        failures.append("isolated_required_markers_not_present")

    if isolated.get("backup_had_gallery_next_action") is not False:
        failures.append(f"backup_had_gallery_next_action_not_false:{isolated.get('backup_had_gallery_next_action')}")

    if isolated.get("isolated_delta_interpretation") != "backup_to_current_delta_is_gallery_next_action_only":
        failures.append(f"isolated_delta_not_clean:{isolated.get('isolated_delta_interpretation')}")

    if isolated.get("unexpected_removed_line_count") not in (0, None):
        failures.append(f"unexpected_removed_lines:{isolated.get('unexpected_removed_line_count')}")

    # Apply report checks.
    if not apply_path:
        failures.append("missing_gallery_apply_report")

    if apply_report.get("result") != "ok":
        failures.append(f"apply_report_not_ok:{apply_report.get('result')}")

    if apply_report.get("apply") is not True:
        failures.append(f"apply_report_apply_not_true:{apply_report.get('apply')}")

    if apply_report.get("source_written") is not True:
        failures.append("apply_report_source_written_not_true")

    if apply_report.get("target_file") != TARGET_FILE:
        failures.append(f"apply_target_not_gallery:{apply_report.get('target_file')}")

    if apply_report.get("post_contains_gallery_next_action") is not True:
        failures.append("apply_report_missing_gallery_next_action_marker")

    if apply_report.get("post_contains_gallery_next_action_title") is not True:
        failures.append("apply_report_missing_gallery_next_action_title_marker")

    backup_path = apply_report.get("backup_path")
    if not backup_path or not Path(backup_path).exists():
        failures.append(f"backup_missing:{backup_path}")

    # Autonomous policy gate checks.
    if not gate_path:
        failures.append("missing_autonomous_policy_gate_report")

    if gate_report.get("result") != "ok":
        failures.append(f"autonomous_gate_not_ok:{gate_report.get('result')}")

    if gate_report.get("target_file") != TARGET_FILE:
        failures.append(f"autonomous_gate_target_not_gallery:{gate_report.get('target_file')}")

    if gate_report.get("autonomous_decision") != "allow_next_dry_apply_gate":
        failures.append(f"autonomous_decision_not_allow:{gate_report.get('autonomous_decision')}")

    # Gate readiness checks.
    if not readiness_path:
        failures.append("missing_gallery_gate_readiness_report")

    if readiness_report.get("result") != "ok":
        failures.append(f"readiness_not_ok:{readiness_report.get('result')}")

    if readiness_report.get("target_file") != TARGET_FILE:
        failures.append(f"readiness_target_not_gallery:{readiness_report.get('target_file')}")

    if readiness_report.get("ready_to_open_source_change_gate") is not True:
        failures.append(f"readiness_not_ready:{readiness_report.get('ready_to_open_source_change_gate')}")

    # Machine gate / no-human-review semantics.
    source_reports = [isolated, apply_report, gate_report, readiness_report]
    human_flags = [report_flag(r, "human_review_required") for r in source_reports]
    human_flags = [x for x in human_flags if x is not None]

    machine_flags = [report_flag(r, "machine_policy_gate") for r in source_reports]
    machine_flags = [x for x in machine_flags if x is not None]

    if any(x is not False for x in human_flags):
        failures.append(f"human_review_required_not_false:{human_flags}")

    if machine_flags and any(x is not True for x in machine_flags):
        failures.append(f"machine_policy_gate_not_true:{machine_flags}")

    if not human_flags:
        warnings.append("human_review_required_field_missing_in_source_reports; acceptance keeps human_review_required=false based on autonomous gate flow")

    if not machine_flags:
        warnings.append("machine_policy_gate_field_missing_in_source_reports; acceptance keeps machine_policy_gate=true based on autonomous gate flow")

    human_review_required = False
    machine_policy_gate = True

    # Target marker checks.
    target_text = (WORKSPACE / TARGET_FILE).read_text(encoding="utf-8", errors="ignore")
    for marker in REQUIRED_MARKERS:
        if marker not in target_text:
            failures.append(f"target_missing_marker:{marker}")

    # Dirty-freeze comparison.
    release_gate = load_release_gate_module()
    entries = release_gate.current_dirty_entries()
    business = [x for x in entries if x.get("class") == "business_source_blocked"]

    freeze_compare = release_gate.compare_business_freeze(state, business)

    changed_paths = sorted([
        x.get("path")
        for x in freeze_compare.get("changed", [])
        if x.get("path")
    ])

    new_business_paths = sorted([
        x.get("path")
        for x in freeze_compare.get("new_business_dirty", [])
        if x.get("path")
    ])

    missing_or_cleaned_paths = sorted([
        x.get("path")
        for x in freeze_compare.get("missing_or_cleaned", [])
        if x.get("path")
    ])

    controlled_delta_paths = sorted(set(changed_paths + new_business_paths))
    unexpected_changed_paths = [x for x in changed_paths if x != TARGET_FILE]
    unexpected_new_business_paths = [x for x in new_business_paths if x != TARGET_FILE]

    if controlled_delta_paths != [TARGET_FILE]:
        failures.append(f"controlled_delta_paths_not_exact_gallery:{controlled_delta_paths}")

    if unexpected_changed_paths:
        failures.append(f"unexpected_changed_business_paths:{unexpected_changed_paths}")

    if unexpected_new_business_paths:
        failures.append(f"unexpected_new_business_paths:{unexpected_new_business_paths}")

    if missing_or_cleaned_paths:
        failures.append(f"missing_or_cleaned_business_paths_present:{missing_or_cleaned_paths}")

    if not freeze_compare.get("freeze_exists"):
        failures.append("previous_dirty_freeze_missing")

    result = "ok" if not failures else "blocked"

    freeze_path = FREEZE_DIR / f"dirty-freeze-controlled-gallery-next-action-{run_stamp}.json"
    out_json = REPORT_DIR / f"gallery-next-action-controlled-ledger-acceptance-{'apply' if args.apply else 'dry-run'}-{run_stamp}.json"
    out_md = REPORT_DIR / f"gallery-next-action-controlled-ledger-acceptance-{'apply' if args.apply else 'dry-run'}-{run_stamp}.md"
    ledger_md = SNAPSHOT_DIR / f"gallery-next-action-controlled-ledger-acceptance-{'apply' if args.apply else 'dry-run'}-{run_stamp}.md"

    new_freeze = {
        "generated_at": now_iso(),
        "freeze_type": "controlled_business_source_change_acceptance",
        "acceptance_id": ACCEPTANCE_ID,
        "accepted_target_file": TARGET_FILE,
        "reason": "Accept validated gallery next-action source change after isolated backup-to-current verification.",
        "previous_dirty_freeze": state.get("last_dirty_freeze"),
        "source_reports": {
            "apply_report": str(apply_path) if apply_path else None,
            "isolated_post_apply_validator": str(isolated_path) if isolated_path else None,
            "autonomous_policy_gate": str(gate_path) if gate_path else None,
            "gate_readiness": str(readiness_path) if readiness_path else None,
        },
        "freeze_compare_before_acceptance": freeze_compare,
        "business_source_blocked": business,
        "summary": {
            "total_dirty": len(entries),
            "business_source_blocked_count": len(business),
            "system_engineering_allowed_count": len([
                x for x in entries
                if x.get("class") == "system_engineering_allowed"
            ]),
            "other_existing_dirty_count": len([
                x for x in entries
                if x.get("class") == "other_existing_dirty"
            ]),
            "accepted_changed_business_paths": changed_paths,
            "accepted_new_business_dirty_paths": new_business_paths,
            "accepted_controlled_delta_paths": controlled_delta_paths,
            "new_business_dirty_paths": new_business_paths,
            "missing_or_cleaned_business_paths": missing_or_cleaned_paths,
            "commit_allowed": False,
            "push_allowed": False,
            "deploy_allowed": False,
        },
        "policy": {
            "source_written_by_acceptance": False,
            "state_written": bool(args.apply and result == "ok"),
            "human_review_required": human_review_required,
            "machine_policy_gate": machine_policy_gate,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
    }

    payload = {
        "generated_at": now_iso(),
        "acceptance_id": ACCEPTANCE_ID,
        "result": result,
        "apply": args.apply,
        "target_file": TARGET_FILE,
        "apply_report": str(apply_path) if apply_path else None,
        "isolated_post_apply_validator": str(isolated_path) if isolated_path else None,
        "autonomous_policy_gate": str(gate_path) if gate_path else None,
        "gate_readiness": str(readiness_path) if readiness_path else None,
        "previous_dirty_freeze": state.get("last_dirty_freeze"),
        "new_dirty_freeze_path": str(freeze_path) if args.apply and result == "ok" else None,
        "changed_business_paths": changed_paths,
        "new_business_dirty_paths": new_business_paths,
        "controlled_delta_paths": controlled_delta_paths,
        "missing_or_cleaned_business_paths": missing_or_cleaned_paths,
        "business_source_dirty_count": len(business),
        "ready_to_accept": result == "ok",
        "human_review_required": human_review_required,
        "machine_policy_gate": machine_policy_gate,
        "policy": {
            "source_written_by_acceptance": False,
            "state_written": bool(args.apply and result == "ok"),
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
        "warnings": warnings,
        "failures": failures,
    }

    save_json(out_json, payload)

    lines = []
    lines.append("# Learning V2 Gallery Next Action Controlled Ledger Acceptance")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- acceptance_id: `{ACCEPTANCE_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- apply: `{str(args.apply).lower()}`")
    lines.append(f"- target_file: `{TARGET_FILE}`")
    lines.append(f"- changed_business_paths: `{changed_paths}`")
    lines.append(f"- new_business_dirty_paths: `{new_business_paths}`")
    lines.append(f"- controlled_delta_paths: `{controlled_delta_paths}`")
    lines.append(f"- missing_or_cleaned_business_paths: `{missing_or_cleaned_paths}`")
    lines.append(f"- business_source_dirty_count: `{len(business)}`")
    lines.append(f"- ready_to_accept: `{str(result == 'ok').lower()}`")
    lines.append(f"- human_review_required: `{str(human_review_required).lower()}`")
    lines.append(f"- machine_policy_gate: `{str(machine_policy_gate).lower()}`")
    lines.append(f"- new_dirty_freeze_path: `{payload['new_dirty_freeze_path']}`")
    lines.append("- source_written_by_acceptance: `false`")
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

    md_text = "\n".join(lines) + "\n"
    out_md.write_text(md_text, encoding="utf-8")
    ledger_md.write_text(md_text, encoding="utf-8")

    if args.apply and result == "ok":
        save_json(freeze_path, new_freeze)

        state["last_dirty_freeze"] = {
            "generated_at": new_freeze["generated_at"],
            "path": str(freeze_path),
            "summary": new_freeze["summary"],
        }

        state["last_controlled_business_change_acceptance"] = {
            "generated_at": payload["generated_at"],
            "acceptance_id": ACCEPTANCE_ID,
            "target_file": TARGET_FILE,
            "acceptance_json": str(out_json),
            "acceptance_md": str(out_md),
            "ledger_md": str(ledger_md),
            "new_dirty_freeze_path": str(freeze_path),
            "source_written_by_acceptance": False,
            "human_review_required": human_review_required,
            "machine_policy_gate": machine_policy_gate,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        }

        state["allow_source_changes"] = False
        state["allow_git_commit"] = False
        state["allow_deploy"] = False

        policy = state.get("self_evolution_policy") or {}
        policy["source_changes_allowed"] = False
        policy["git_commit_allowed"] = False
        policy["git_push_allowed"] = False
        policy["deploy_allowed"] = False
        state["self_evolution_policy"] = policy

        save_json(STATE, state)

    print("gallery_next_action_controlled_ledger_acceptance =", result)
    print("apply =", args.apply)
    print("target_file =", TARGET_FILE)
    print("changed_business_paths =", changed_paths)
    print("new_business_dirty_paths =", new_business_paths)
    print("controlled_delta_paths =", controlled_delta_paths)
    print("missing_or_cleaned_business_paths =", missing_or_cleaned_paths)
    print("ready_to_accept =", result == "ok")
    print("human_review_required =", human_review_required)
    print("machine_policy_gate =", machine_policy_gate)
    print("state_written =", bool(args.apply and result == "ok"))
    print("source_written_by_acceptance = False")
    print("git_commit = False")
    print("git_push = False")
    print("deploy = False")
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("ledger_md =", ledger_md)
    print("new_dirty_freeze_path =", str(freeze_path) if args.apply and result == "ok" else None)
    if warnings:
        print("warnings =", json.dumps(warnings, ensure_ascii=False))
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
