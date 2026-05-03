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

GUARD_ID = "learning-v2-fifth-loop-target-planning-guard-v0"

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

    duplication_path, duplication = latest_report("controlled-change-duplication-guard-*.json")
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

    for label, path, report in [
        ("duplication_guard", duplication_path, duplication),
        ("next_loop_readiness", readiness_path, readiness),
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

    closed_files = duplication.get("closed_target_files") or []
    closed_units = duplication.get("closed_change_units") or []

    if "public/about.html" not in closed_files:
        failures.append("public_about_not_closed")

    if "create-public-about-page-v0" not in closed_units:
        failures.append("create_public_about_unit_not_closed")

    bad_closed_items = [
        x for x in closed_files + closed_units
        if ":" in str(x) or "<" in str(x) or ">" in str(x)
    ]
    if bad_closed_items:
        failures.append(f"legacy_strings_still_in_closed_lists:{bad_closed_items}")

    if readiness.get("next_loop_status") != "ready_for_planning_only":
        failures.append(f"next_loop_status_not_ready_for_planning_only:{readiness.get('next_loop_status')}")

    if readiness.get("fourth_loop_allowed_now") is not False:
        failures.append(f"fourth_loop_allowed_now_not_false:{readiness.get('fourth_loop_allowed_now')}")

    deferred_items = readiness.get("deferred_item_decisions") or []
    candidate_decisions = readiness.get("candidate_decisions") or []

    concrete_candidates = [
        x for x in deferred_items
        if x.get("target_file") and not x.get("blockers")
    ]

    family_only_candidates = [
        x for x in candidate_decisions
        if x.get("status") == "candidate_family_available_but_requires_next_loop_plan"
    ]

    selected_target = None
    planning_status = "blocked"

    if failures:
        planning_status = "blocked"
    elif concrete_candidates:
        selected_target = concrete_candidates[0]
        planning_status = "concrete_target_available_for_planning_only"
    elif family_only_candidates:
        planning_status = "family_available_but_no_concrete_target"
    else:
        planning_status = "no_candidate_available"

    result = "ok" if not failures else "blocked"

    recommended_next_step = (
        "run_community_engagement_path_probe_refresh_no_source_write"
        if result == "ok" and planning_status == "family_available_but_no_concrete_target"
        else "run_next_target_selector_with_duplication_guard"
        if result == "ok" and planning_status == "concrete_target_available_for_planning_only"
        else "fix_fifth_loop_target_planning_guard_blockers"
    )

    out_json = REPORT_DIR / f"fifth-loop-target-planning-guard-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"fifth-loop-target-planning-guard-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "guard_id": GUARD_ID,
        "result": result,
        "planning_status": planning_status,
        "selected_target": selected_target,
        "concrete_candidate_count": len(concrete_candidates),
        "family_only_candidate_count": len(family_only_candidates),
        "closed_target_files": closed_files,
        "closed_change_units": closed_units,
        "applied_targets_count": state.get("applied_targets") and len(state.get("applied_targets")) or 0,
        "duplication_guard_report": str(duplication_path) if duplication_path else None,
        "next_loop_readiness_report": str(readiness_path) if readiness_path else None,
        "integrity_report": str(integrity_path) if integrity_path else None,
        "source_written": False,
        "metadata_written": False,
        "state_written": False,
        "business_source_written": False,
        "source_change_gate_opened": False,
        "fifth_loop_started": False,
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
    lines.append("# Learning V2 Fifth Loop Target Planning Guard")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- guard_id: `{GUARD_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- planning_status: `{planning_status}`")
    lines.append(f"- concrete_candidate_count: `{len(concrete_candidates)}`")
    lines.append(f"- family_only_candidate_count: `{len(family_only_candidates)}`")
    lines.append(f"- selected_target: `{selected_target}`")
    lines.append(f"- applied_targets_count: `{payload['applied_targets_count']}`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")
    lines.append("- source_written: `false`")
    lines.append("- metadata_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- fifth_loop_started: `false`")
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

    print("fifth_loop_target_planning_guard =", result)
    print("planning_status =", planning_status)
    print("concrete_candidate_count =", len(concrete_candidates))
    print("family_only_candidate_count =", len(family_only_candidates))
    print("selected_target =", json.dumps(selected_target, ensure_ascii=False, indent=2))
    print("applied_targets_count =", payload["applied_targets_count"])
    print("source_written = False")
    print("metadata_written = False")
    print("state_written = False")
    print("business_source_written = False")
    print("source_change_gate_opened = False")
    print("fifth_loop_started = False")
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
