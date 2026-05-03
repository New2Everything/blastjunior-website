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

SELECTOR_ID = "learning-v2-next-target-selector-with-duplication-guard-v0"

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

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    readiness_path, readiness = latest_report("next-loop-readiness-auditor-*.json")
    guard_path, guard = latest_report("controlled-change-duplication-guard-*.json")
    registry_path, registry = latest_report("controlled-change-registry-*.json")
    checker_path, checker = latest_report("controlled-change-template-checker-*.json")
    generic_ledger_path, generic_ledger = latest_report("controlled-change-generic-ledger-acceptance-*.json")
    integrity_path, integrity = latest_report("system-integrity-*.json")

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

    if readiness.get("next_loop_status") != "ready_for_planning_only":
        failures.append(f"next_loop_status_not_ready_for_planning_only:{readiness.get('next_loop_status')}")

    if readiness.get("fourth_loop_allowed_now") is not False:
        failures.append(f"fourth_loop_allowed_now_not_false:{readiness.get('fourth_loop_allowed_now')}")

    if readiness.get("missing_generic_scaffold"):
        failures.append(f"missing_generic_scaffold_not_empty:{readiness.get('missing_generic_scaffold')}")

    if checker.get("template_gap_count") not in (0, None):
        failures.append(f"template_gap_count_not_zero:{checker.get('template_gap_count')}")

    if registry.get("registered_units_with_failures_count") not in (0, None):
        failures.append(f"registry_units_with_failures_not_zero:{registry.get('registered_units_with_failures_count')}")

    if generic_ledger.get("acceptance_mode") != "no_metadata_safe_noop":
        warnings.append(f"generic_ledger_acceptance_mode_not_noop:{generic_ledger.get('acceptance_mode')}")

    closed_files = set(guard.get("closed_target_files") or [])
    closed_units = set(guard.get("closed_change_units") or [])

    candidate_decisions = readiness.get("candidate_decisions") or []
    deferred_item_decisions = readiness.get("deferred_item_decisions") or []

    planning_candidates = []

    for item in candidate_decisions:
        if item.get("status") == "candidate_family_available_but_requires_next_loop_plan":
            planning_candidates.append({
                "candidate_type": "target_family",
                "candidate_id": item.get("candidate_id"),
                "target_family": item.get("target_family"),
                "target_file": None,
                "reason": "Family is available for planning only, but must be tied to unresolved/deferred item before source change.",
                "risk": item.get("risk"),
                "blockers": item.get("blockers") or [],
                "warnings": item.get("warnings") or [],
            })

    for item in deferred_item_decisions:
        if item.get("status") == "readiness_candidate_after_scaffold":
            target_file = item.get("target_file")
            blockers = list(item.get("blockers") or [])
            warnings_for_item = list(item.get("warnings") or [])

            if target_file in closed_files:
                blockers.append("target_file_already_closed")

            if target_file and (WORKSPACE / target_file).exists():
                warnings_for_item.append("target_file_exists_verify_before_planning")
            else:
                warnings_for_item.append("target_file_missing_creation_requires_extra_planning_gate")

            planning_candidates.append({
                "candidate_type": "deferred_item",
                "candidate_id": item.get("candidate_id"),
                "target_family": item.get("target_family"),
                "target_file": target_file,
                "reason": item.get("reason"),
                "risk": "higher_than_existing_page_refinement",
                "blockers": blockers,
                "warnings": warnings_for_item,
            })

    selectable_candidates = [
        x for x in planning_candidates
        if not x.get("blockers")
    ]

    selected = None
    if selectable_candidates:
        deferred = [x for x in selectable_candidates if x.get("candidate_type") == "deferred_item"]
        selected = deferred[0] if deferred else selectable_candidates[0]

    if selected and selected.get("target_file") in closed_files:
        failures.append(f"selected_target_file_already_closed:{selected.get('target_file')}")

    if selected and selected.get("candidate_id") in closed_units:
        failures.append(f"selected_change_unit_already_closed:{selected.get('candidate_id')}")

    result = "ok" if not failures else "blocked"

    recommended_next_step = (
        "build_fourth_loop_planning_brief_no_source_write"
        if result == "ok" and selected
        else "fix_next_target_selector_or_wait_for_new_candidate"
    )

    out_json = REPORT_DIR / f"next-target-selector-with-duplication-guard-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"next-target-selector-with-duplication-guard-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "selector_id": SELECTOR_ID,
        "result": result,
        "selector_mode": "planning_only",
        "planning_candidate_count": len(planning_candidates),
        "selectable_candidate_count": len(selectable_candidates),
        "selected_candidate": selected,
        "closed_target_files": sorted(closed_files),
        "closed_change_units": sorted(closed_units),
        "next_loop_readiness_report": str(readiness_path) if readiness_path else None,
        "duplication_guard_report": str(guard_path) if guard_path else None,
        "registry_report": str(registry_path) if registry_path else None,
        "template_checker_report": str(checker_path) if checker_path else None,
        "generic_ledger_acceptance_report": str(generic_ledger_path) if generic_ledger_path else None,
        "integrity_report": str(integrity_path) if integrity_path else None,
        "fourth_loop_allowed_now": False,
        "source_written": False,
        "state_written": False,
        "business_source_written": False,
        "source_change_gate_opened": False,
        "metadata_written": False,
        "fourth_loop_started": False,
        "human_review_required": False,
        "machine_policy_gate": True,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "recommended_next_step": recommended_next_step,
        "policy": {
            "selector_only": True,
            "planning_only": True,
            "state_written": False,
            "business_source_written": False,
            "source_change_gate_opened": False,
            "metadata_written": False,
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
    lines.append("# Learning V2 Next Target Selector With Duplication Guard")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- selector_id: `{SELECTOR_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append("- selector_mode: `planning_only`")
    lines.append(f"- planning_candidate_count: `{len(planning_candidates)}`")
    lines.append(f"- selectable_candidate_count: `{len(selectable_candidates)}`")
    lines.append(f"- selected_candidate: `{selected}`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")
    lines.append("- fourth_loop_allowed_now: `false`")
    lines.append("- source_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- metadata_written: `false`")
    lines.append("- fourth_loop_started: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Planning Candidates")
    for item in planning_candidates:
        lines.append(
            f"- `{item.get('candidate_type')}` `{item.get('candidate_id')}` "
            f"family=`{item.get('target_family')}` target=`{item.get('target_file')}` "
            f"blockers=`{item.get('blockers')}` warnings=`{item.get('warnings')}`"
        )

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

    print("next_target_selector_with_duplication_guard =", result)
    print("selector_mode = planning_only")
    print("planning_candidate_count =", len(planning_candidates))
    print("selectable_candidate_count =", len(selectable_candidates))
    print("selected_candidate =", json.dumps(selected, ensure_ascii=False, indent=2))
    print("fourth_loop_allowed_now = False")
    print("source_written = False")
    print("state_written = False")
    print("business_source_written = False")
    print("source_change_gate_opened = False")
    print("metadata_written = False")
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
