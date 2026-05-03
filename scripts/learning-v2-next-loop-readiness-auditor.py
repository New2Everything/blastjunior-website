#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
RESEARCH = BASE / "research"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

AUDITOR_ID = "learning-v2-next-loop-readiness-auditor-v0"
CANDIDATE_FILE = RESEARCH / "target-family-candidates.jsonl"

REQUIRED_SYSTEM_SCRIPTS = [
    "scripts/learning-v2-controlled-change-registry.py",
    "scripts/learning-v2-controlled-change-template-checker.py",
    "scripts/learning-v2-controlled-change-duplication-guard.py",
]

RECOMMENDED_GENERIC_SCAFFOLD = [
    "scripts/learning-v2-controlled-change-lifecycle-metadata-validator.py",
    "scripts/learning-v2-controlled-change-generic-dry-run-runner.py",
    "scripts/learning-v2-controlled-change-generic-policy-gate.py",
    "scripts/learning-v2-controlled-change-generic-readiness.py",
    "scripts/learning-v2-controlled-change-generic-apply.py",
    "scripts/learning-v2-controlled-change-generic-isolated-validator.py",
    "scripts/learning-v2-controlled-change-generic-ledger-acceptance.py",
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

def read_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            obj["_jsonl_line"] = i
            rows.append(obj)
        except Exception as e:
            rows.append({"_jsonl_line": i, "_parse_error": str(e), "_raw": line[:300]})
    return rows

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

def path_status(rel):
    p = WORKSPACE / rel
    return {
        "path": rel,
        "exists": p.exists(),
        "is_file": p.is_file() if p.exists() else False,
        "size_bytes": p.stat().st_size if p.exists() and p.is_file() else None,
    }

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    registry_path, registry = latest_report("controlled-change-registry-*.json")
    checker_path, checker = latest_report("controlled-change-template-checker-*.json")
    guard_path, guard = latest_report("controlled-change-duplication-guard-*.json")
    integrity_path, integrity = latest_report("system-integrity-*.json")

    candidates = read_jsonl(CANDIDATE_FILE)

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

    if not integrity_path:
        failures.append("missing_system_integrity_report")
    elif integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    integrity_drift_count = integrity.get("drift_count")
    if integrity_drift_count is None:
        integrity_drift_count = find_key(integrity, "drift_count")

    integrity_business_freeze_stable = integrity.get("business_freeze_stable")
    if integrity_business_freeze_stable is None:
        integrity_business_freeze_stable = find_key(integrity, "business_freeze_stable")

    if integrity_drift_count is None or integrity_business_freeze_stable is None:
        drift_path, drift = latest_report("system-drift-audit-*.json")
        if integrity_drift_count is None:
            integrity_drift_count = drift.get("drift_count")
        if integrity_business_freeze_stable is None:
            integrity_business_freeze_stable = drift.get("business_freeze_stable")

    if integrity_drift_count != 0:
        failures.append(f"drift_count_not_zero:{integrity_drift_count}")

    if integrity_business_freeze_stable is not True:
        failures.append(f"business_freeze_not_stable:{integrity_business_freeze_stable}")

    if not registry_path:
        failures.append("missing_controlled_change_registry_report")
    elif registry.get("result") != "ok":
        failures.append(f"registry_not_ok:{registry.get('result')}")

    if registry.get("registered_unit_count", 0) < 3:
        failures.append(f"registered_unit_count_too_low:{registry.get('registered_unit_count')}")

    if registry.get("registered_units_with_failures_count") not in (0, None):
        failures.append(f"registered_units_with_failures_not_zero:{registry.get('registered_units_with_failures_count')}")

    if not checker_path:
        failures.append("missing_template_checker_report")
    elif checker.get("result") != "ok":
        failures.append(f"template_checker_not_ok:{checker.get('result')}")

    if checker.get("template_gap_count") not in (0, None):
        failures.append(f"template_gap_count_not_zero:{checker.get('template_gap_count')}")

    if not guard_path:
        failures.append("missing_duplication_guard_report")
    elif guard.get("result") != "ok":
        failures.append(f"duplication_guard_not_ok:{guard.get('result')}")

    guard_recommendation = guard.get("recommendation") or {}
    if guard_recommendation.get("fourth_loop_allowed_now") is not False:
        failures.append(f"duplication_guard_fourth_loop_allowed_unexpected:{guard_recommendation.get('fourth_loop_allowed_now')}")

    required_script_status = [path_status(x) for x in REQUIRED_SYSTEM_SCRIPTS]
    missing_required_scripts = [x["path"] for x in required_script_status if not x["exists"]]
    if missing_required_scripts:
        failures.append(f"missing_required_system_scripts:{missing_required_scripts}")

    generic_scaffold_status = [path_status(x) for x in RECOMMENDED_GENERIC_SCAFFOLD]
    missing_generic_scaffold = [x["path"] for x in generic_scaffold_status if not x["exists"]]

    closed_target_files = set(guard.get("closed_target_files") or [])
    closed_change_units = set(guard.get("closed_change_units") or [])
    deferred_items = guard.get("deferred_item_candidates") or []

    candidate_decisions = []
    for c in candidates:
        if "_parse_error" in c:
            candidate_decisions.append({
                "jsonl_line": c.get("_jsonl_line"),
                "status": "invalid_jsonl",
                "blockers": [c.get("_parse_error")],
            })
            continue

        target_family = c.get("target_family")
        blockers = []
        warnings_for_candidate = []

        if target_family == "community.onboarding_experience":
            blockers.append("blocked_by_duplication_guard_onboarding_saturated")

        if target_family == "community.engagement_path":
            warnings_for_candidate.append("family_has_closed_loop_requires_unresolved_or_deferred_item")

        if c.get("risk") != "low":
            blockers.append(f"risk_not_low:{c.get('risk')}")

        if c.get("activation_allowed_now") is not True:
            blockers.append(f"activation_allowed_now_not_true:{c.get('activation_allowed_now')}")

        probe = c.get("recommended_probe_script")
        probe_exists = bool(probe and (WORKSPACE / "scripts" / probe).exists())
        if probe and not probe_exists:
            blockers.append(f"recommended_probe_missing:{probe}")

        candidate_decisions.append({
            "candidate_id": c.get("candidate_id"),
            "target_family": target_family,
            "topic": c.get("topic"),
            "risk": c.get("risk"),
            "activation_allowed_now": c.get("activation_allowed_now"),
            "recommended_probe_script": probe,
            "recommended_probe_script_exists": probe_exists,
            "status": "blocked" if blockers else "candidate_family_available_but_requires_next_loop_plan",
            "blockers": blockers,
            "warnings": warnings_for_candidate,
        })

    deferred_item_decisions = []
    for item in deferred_items:
        target_file = item.get("target_file")
        blockers = []
        warnings_for_item = []

        if target_file in closed_target_files:
            blockers.append("deferred_target_file_already_closed")

        if not target_file:
            blockers.append("missing_target_file")

        if target_file and (WORKSPACE / target_file).exists():
            warnings_for_item.append("target_file_already_exists_verify_before_any_future_change")
        else:
            warnings_for_item.append("target_file_missing_future_creation_is_higher_risk_than_existing_page_refinement")

        deferred_item_decisions.append({
            **item,
            "status": "not_ready_for_fourth_loop" if blockers or missing_generic_scaffold else "readiness_candidate_after_scaffold",
            "blockers": blockers + (["generic_lifecycle_scaffold_missing"] if missing_generic_scaffold else []),
            "warnings": warnings_for_item,
        })

    reusable_lifecycle_ready = not missing_generic_scaffold

    next_loop_status = "not_ready"
    next_loop_blockers = []

    if missing_generic_scaffold:
        next_loop_blockers.append("generic_lifecycle_scaffold_missing")

    if failures:
        next_loop_blockers.append("system_or_registry_precondition_failed")

    if reusable_lifecycle_ready and not failures:
        next_loop_status = "ready_for_planning_only"

    fourth_loop_allowed_now = False

    recommended_next_step = (
        "build_controlled_change_lifecycle_metadata_validator"
        if missing_generic_scaffold
        else "run_next_target_selector_with_duplication_guard"
    )

    result = "ok" if not failures else "blocked"

    out_json = REPORT_DIR / f"next-loop-readiness-auditor-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"next-loop-readiness-auditor-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "auditor_id": AUDITOR_ID,
        "result": result,
        "next_loop_status": next_loop_status,
        "fourth_loop_allowed_now": fourth_loop_allowed_now,
        "next_loop_blockers": next_loop_blockers,
        "registry_report": str(registry_path) if registry_path else None,
        "template_checker_report": str(checker_path) if checker_path else None,
        "duplication_guard_report": str(guard_path) if guard_path else None,
        "integrity_report": str(integrity_path) if integrity_path else None,
        "required_script_status": required_script_status,
        "generic_scaffold_status": generic_scaffold_status,
        "missing_generic_scaffold": missing_generic_scaffold,
        "closed_change_units": sorted(closed_change_units),
        "closed_target_files": sorted(closed_target_files),
        "candidate_decisions": candidate_decisions,
        "deferred_item_decisions": deferred_item_decisions,
        "recommended_next_step": recommended_next_step,
        "policy": {
            "auditor_only": True,
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
    lines.append("# Learning V2 Next Loop Readiness Auditor")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- auditor_id: `{AUDITOR_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- next_loop_status: `{next_loop_status}`")
    lines.append(f"- fourth_loop_allowed_now: `{str(fourth_loop_allowed_now).lower()}`")
    lines.append(f"- missing_generic_scaffold_count: `{len(missing_generic_scaffold)}`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")
    lines.append("- auditor_only: `true`")
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
    lines.append("## Missing Generic Scaffold")
    if missing_generic_scaffold:
        for item in missing_generic_scaffold:
            lines.append(f"- `{item}`")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Candidate Decisions")
    for item in candidate_decisions:
        lines.append(
            f"- `{item.get('target_family')}` status=`{item.get('status')}` "
            f"blockers=`{item.get('blockers')}` warnings=`{item.get('warnings')}`"
        )
    lines.append("")
    lines.append("## Deferred Item Decisions")
    for item in deferred_item_decisions:
        lines.append(
            f"- `{item.get('target_file')}` status=`{item.get('status')}` "
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

    print("next_loop_readiness_auditor =", result)
    print("next_loop_status =", next_loop_status)
    print("fourth_loop_allowed_now =", fourth_loop_allowed_now)
    print("missing_generic_scaffold_count =", len(missing_generic_scaffold))
    print("recommended_next_step =", recommended_next_step)
    print("auditor_only = True")
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
