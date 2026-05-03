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

BRIEF_ID = "learning-v2-fourth-loop-planning-brief-v0"

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

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    selector_path, selector = latest_report("next-target-selector-with-duplication-guard-*.json")
    readiness_path, readiness = latest_report("next-loop-readiness-auditor-*.json")
    guard_path, guard = latest_report("controlled-change-duplication-guard-*.json")
    registry_path, registry = latest_report("controlled-change-registry-*.json")
    checker_path, checker = latest_report("controlled-change-template-checker-*.json")
    generic_ledger_path, generic_ledger = latest_report("controlled-change-generic-ledger-acceptance-*.json")
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
        ("next_target_selector", selector_path, selector),
        ("next_loop_readiness", readiness_path, readiness),
        ("duplication_guard", guard_path, guard),
        ("controlled_change_registry", registry_path, registry),
        ("template_checker", checker_path, checker),
        ("generic_ledger_acceptance", generic_ledger_path, generic_ledger),
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

    if selector.get("selector_mode") != "planning_only":
        failures.append(f"selector_mode_not_planning_only:{selector.get('selector_mode')}")

    if selector.get("fourth_loop_allowed_now") is not False:
        failures.append(f"selector_fourth_loop_allowed_not_false:{selector.get('fourth_loop_allowed_now')}")

    for key in ["source_written", "state_written", "business_source_written", "source_change_gate_opened", "metadata_written", "fourth_loop_started"]:
        if selector.get(key) is not False:
            failures.append(f"selector_{key}_not_false:{selector.get(key)}")

    if readiness.get("next_loop_status") != "ready_for_planning_only":
        failures.append(f"readiness_not_ready_for_planning_only:{readiness.get('next_loop_status')}")

    if readiness.get("fourth_loop_allowed_now") is not False:
        failures.append(f"readiness_fourth_loop_allowed_not_false:{readiness.get('fourth_loop_allowed_now')}")

    selected = selector.get("selected_candidate") or {}
    selected_target_file = selected.get("target_file")
    selected_candidate_id = selected.get("candidate_id")
    selected_family = selected.get("target_family")

    closed_files = set(guard.get("closed_target_files") or [])
    closed_units = set(guard.get("closed_change_units") or [])

    planning_blockers = []
    planning_warnings = []

    if not selected:
        planning_blockers.append("no_selected_candidate")

    if selected_candidate_id in closed_units:
        planning_blockers.append(f"selected_candidate_already_closed:{selected_candidate_id}")

    if selected_target_file in closed_files:
        planning_blockers.append(f"selected_target_file_already_closed:{selected_target_file}")

    has_concrete_target_file = bool(selected_target_file)

    target_exists = False
    if has_concrete_target_file:
        target_exists = (WORKSPACE / selected_target_file).exists()
    else:
        planning_blockers.append("selected_target_file_missing")
        planning_warnings.append("selected_family_requires_unresolved_or_deferred_concrete_target")

    current_generic_lifecycle_support = {
        "metadata_validator": True,
        "generic_dry_run_runner": True,
        "generic_policy_gate": True,
        "generic_readiness": True,
        "generic_apply": True,
        "generic_isolated_validator": True,
        "generic_ledger_acceptance": True,
        "supports_existing_file_insert_after_anchor_once": True,
        "supports_new_file_creation": False,
    }

    if has_concrete_target_file and not current_generic_lifecycle_support["supports_new_file_creation"] and not target_exists:
        planning_blockers.append("current_generic_lifecycle_does_not_support_new_file_creation")

    planning_brief = {
        "candidate_id": selected_candidate_id,
        "candidate_type": selected.get("candidate_type"),
        "target_family": selected_family,
        "target_file": selected_target_file,
        "target_file_exists": target_exists,
        "risk_interpretation": (
            "no_concrete_target_file_selected"
            if not has_concrete_target_file
            else "higher_than_existing_page_refinement"
            if not target_exists
            else "existing_file_refinement_possible"
        ),
        "current_generic_lifecycle_support": current_generic_lifecycle_support,
        "planning_status": (
            "planning_only_no_concrete_target"
            if not has_concrete_target_file
            else "planning_only_not_ready_for_metadata_or_source_change"
        ),
        "source_change_allowed_now": False,
        "metadata_creation_allowed_now": False,
        "why_not_ready": (
            [
                "selector found only a target family, not a concrete target file",
                "a closed target family requires a real unresolved or deferred item before metadata or source change",
                "pause the loop or expand a no-source-write probe dimension before selecting a source target",
            ]
            if not has_concrete_target_file
            else [
                "selected candidate is a missing page",
                "generic dry-run runner currently supports existing-file insert_after_anchor_once",
                "new file creation requires separate lifecycle readiness guard before metadata can be written",
            ]
            if not target_exists
            else []
        ),
        "recommended_planning_constraints": (
            [
                "do not write controlled-change metadata yet",
                "do not open source gate",
                "do not commit, push, or deploy",
                "first identify a real unresolved or deferred concrete target, or expand a no-source-write probe dimension",
            ]
            if not has_concrete_target_file
            else [
                f"do not create {selected_target_file} yet",
                "do not write controlled-change metadata yet",
                "do not open source gate",
                "do not commit, push, or deploy",
                "first decide whether to extend generic lifecycle for create_file_from_template or select an existing page refinement instead",
            ]
            if not target_exists
            else [
                "do not write controlled-change metadata yet",
                "do not open source gate",
                "do not commit, push, or deploy",
                "first confirm the existing-file refinement has a concrete low-risk change unit",
            ]
        ),
    }

    result = "ok" if not failures else "blocked"

    recommended_next_step = (
        "pause_loop_or_expand_probe_dimension_no_source_write"
        if result == "ok" and not has_concrete_target_file
        else "build_new_file_creation_lifecycle_readiness_guard_no_source_write"
        if result == "ok" and planning_blockers
        else "build_controlled_change_metadata_draft_no_source_write"
        if result == "ok"
        else "fix_fourth_loop_planning_brief_blockers"
    )

    out_json = REPORT_DIR / f"fourth-loop-planning-brief-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"fourth-loop-planning-brief-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "brief_id": BRIEF_ID,
        "result": result,
        "brief_mode": "planning_only",
        "selected_candidate": selected,
        "planning_brief": planning_brief,
        "planning_blockers": planning_blockers,
        "planning_warnings": planning_warnings,
        "next_target_selector_report": str(selector_path) if selector_path else None,
        "next_loop_readiness_report": str(readiness_path) if readiness_path else None,
        "duplication_guard_report": str(guard_path) if guard_path else None,
        "registry_report": str(registry_path) if registry_path else None,
        "template_checker_report": str(checker_path) if checker_path else None,
        "generic_ledger_acceptance_report": str(generic_ledger_path) if generic_ledger_path else None,
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
            "brief_only": True,
            "planning_only": True,
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
    lines.append("# Learning V2 Fourth Loop Planning Brief")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- brief_id: `{BRIEF_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append("- brief_mode: `planning_only`")
    lines.append(f"- selected_candidate_id: `{selected_candidate_id}`")
    lines.append(f"- target_family: `{selected_family}`")
    lines.append(f"- target_file: `{selected_target_file}`")
    lines.append(f"- target_file_exists: `{str(target_exists).lower()}`")
    lines.append(f"- planning_blockers: `{planning_blockers}`")
    lines.append(f"- planning_warnings: `{planning_warnings}`")
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
    lines.append("## Planning Interpretation")
    lines.append("")
    if not has_concrete_target_file:
        lines.append(f"The selector found target family `{selected_family}`, but did not select a concrete target file.")
        lines.append("")
        lines.append("This means the loop is planning-only and must remain paused until a real unresolved or deferred item is identified.")
    elif not target_exists:
        lines.append(f"The selected target file `{selected_target_file}` does not exist, so this is a new-file creation candidate.")
        lines.append("")
        lines.append("The current generic lifecycle supports existing-file `insert_after_anchor_once`, but does not yet support generic new file creation.")
    else:
        lines.append(f"The selected target file `{selected_target_file}` already exists and could potentially be treated as an existing-page refinement.")
    lines.append("")
    lines.append("## Constraints")
    for item in planning_brief["recommended_planning_constraints"]:
        lines.append(f"- {item}")

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

    print("fourth_loop_planning_brief =", result)
    print("brief_mode = planning_only")
    print("selected_candidate_id =", selected_candidate_id)
    print("target_family =", selected_family)
    print("target_file =", selected_target_file)
    print("target_file_exists =", target_exists)
    print("planning_blockers =", json.dumps(planning_blockers, ensure_ascii=False))
    print("planning_warnings =", json.dumps(planning_warnings, ensure_ascii=False))
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
