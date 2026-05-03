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

GUARD_ID = "learning-v2-new-file-creation-lifecycle-readiness-guard-v0"

REQUIRED_GENERIC_EXISTING_FILE_SCAFFOLD = [
    "scripts/learning-v2-controlled-change-lifecycle-metadata-validator.py",
    "scripts/learning-v2-controlled-change-generic-dry-run-runner.py",
    "scripts/learning-v2-controlled-change-generic-policy-gate.py",
    "scripts/learning-v2-controlled-change-generic-readiness.py",
    "scripts/learning-v2-controlled-change-generic-apply.py",
    "scripts/learning-v2-controlled-change-generic-isolated-validator.py",
    "scripts/learning-v2-controlled-change-generic-ledger-acceptance.py",
]

REQUIRED_NEW_FILE_EXTENSION_MISSING_BY_DESIGN = [
    "scripts/learning-v2-controlled-change-new-file-template-validator.py",
    "scripts/learning-v2-controlled-change-generic-create-file-dry-run-runner.py",
    "scripts/learning-v2-controlled-change-generic-create-file-policy-gate.py",
    "scripts/learning-v2-controlled-change-generic-create-file-readiness.py",
    "scripts/learning-v2-controlled-change-generic-create-file-apply.py",
    "scripts/learning-v2-controlled-change-generic-create-file-isolated-validator.py",
    "scripts/learning-v2-controlled-change-generic-create-file-ledger-acceptance.py",
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

    brief_path, brief = latest_report("fourth-loop-planning-brief-*.json")
    selector_path, selector = latest_report("next-target-selector-with-duplication-guard-*.json")
    readiness_path, readiness = latest_report("next-loop-readiness-auditor-*.json")
    guard_path, duplication_guard = latest_report("controlled-change-duplication-guard-*.json")
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
        ("fourth_loop_planning_brief", brief_path, brief),
        ("next_target_selector", selector_path, selector),
        ("next_loop_readiness", readiness_path, readiness),
        ("duplication_guard", guard_path, duplication_guard),
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

    if brief.get("brief_mode") != "planning_only":
        failures.append(f"brief_mode_not_planning_only:{brief.get('brief_mode')}")

    if brief.get("fourth_loop_allowed_now") is not False:
        failures.append(f"brief_fourth_loop_allowed_not_false:{brief.get('fourth_loop_allowed_now')}")

    for key in ["metadata_written", "source_written", "state_written", "business_source_written", "source_change_gate_opened", "fourth_loop_started"]:
        if brief.get(key) is not False:
            failures.append(f"brief_{key}_not_false:{brief.get(key)}")

    planning_brief = brief.get("planning_brief") or {}
    selected = brief.get("selected_candidate") or {}

    target_file = planning_brief.get("target_file") or selected.get("target_file")
    target_family = planning_brief.get("target_family") or selected.get("target_family")
    candidate_id = planning_brief.get("candidate_id") or selected.get("candidate_id")

    target_exists = bool(target_file and (WORKSPACE / target_file).exists())

    if target_file != "public/about.html":
        failures.append(f"unexpected_target_file:{target_file}")

    if target_family != "community.engagement_path":
        failures.append(f"unexpected_target_family:{target_family}")

    if target_exists:
        warnings.append("target_file_now_exists_recheck_if_candidate_should_shift_to_existing_file_flow")

    closed_files = set(duplication_guard.get("closed_target_files") or [])
    if target_file in closed_files:
        failures.append(f"target_file_already_closed:{target_file}")

    existing_scaffold_status = [path_status(x) for x in REQUIRED_GENERIC_EXISTING_FILE_SCAFFOLD]
    missing_existing_scaffold = [x["path"] for x in existing_scaffold_status if not x["exists"]]

    if missing_existing_scaffold:
        failures.append(f"missing_existing_file_generic_scaffold:{missing_existing_scaffold}")

    new_file_extension_status = [path_status(x) for x in REQUIRED_NEW_FILE_EXTENSION_MISSING_BY_DESIGN]
    missing_new_file_extension = [x["path"] for x in new_file_extension_status if not x["exists"]]

    new_file_creation_readiness = "not_ready"

    readiness_blockers = []

    if not target_exists:
        readiness_blockers.append("target_file_missing")
    if missing_new_file_extension:
        readiness_blockers.append("new_file_creation_lifecycle_extension_missing")
    if planning_brief.get("current_generic_lifecycle_support", {}).get("supports_new_file_creation") is not True:
        readiness_blockers.append("current_generic_lifecycle_supports_new_file_creation_false")

    if not readiness_blockers and not failures:
        new_file_creation_readiness = "ready_for_metadata_draft_only"

    result = "ok" if not failures else "blocked"

    recommended_next_step = (
        "build_create_file_from_template_lifecycle_extension_plan_no_source_write"
        if result == "ok" and readiness_blockers
        else "build_new_file_controlled_change_metadata_draft_no_source_write"
        if result == "ok"
        else "fix_new_file_creation_readiness_guard_blockers"
    )

    out_json = REPORT_DIR / f"new-file-creation-lifecycle-readiness-guard-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"new-file-creation-lifecycle-readiness-guard-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "guard_id": GUARD_ID,
        "result": result,
        "guard_mode": "new_file_creation_readiness_only",
        "candidate_id": candidate_id,
        "target_family": target_family,
        "target_file": target_file,
        "target_file_exists": target_exists,
        "new_file_creation_readiness": new_file_creation_readiness,
        "readiness_blockers": readiness_blockers,
        "existing_file_generic_scaffold_status": existing_scaffold_status,
        "missing_existing_file_generic_scaffold": missing_existing_scaffold,
        "new_file_extension_status": new_file_extension_status,
        "missing_new_file_extension": missing_new_file_extension,
        "fourth_loop_planning_brief_report": str(brief_path) if brief_path else None,
        "next_target_selector_report": str(selector_path) if selector_path else None,
        "next_loop_readiness_report": str(readiness_path) if readiness_path else None,
        "duplication_guard_report": str(guard_path) if guard_path else None,
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
            "guard_only": True,
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
    lines.append("# Learning V2 New File Creation Lifecycle Readiness Guard")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- guard_id: `{GUARD_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append("- guard_mode: `new_file_creation_readiness_only`")
    lines.append(f"- target_family: `{target_family}`")
    lines.append(f"- target_file: `{target_file}`")
    lines.append(f"- target_file_exists: `{str(target_exists).lower()}`")
    lines.append(f"- new_file_creation_readiness: `{new_file_creation_readiness}`")
    lines.append(f"- readiness_blockers: `{readiness_blockers}`")
    lines.append(f"- missing_new_file_extension_count: `{len(missing_new_file_extension)}`")
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
    lines.append("## Missing New File Extension")
    for item in missing_new_file_extension:
        lines.append(f"- `{item}`")

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

    print("new_file_creation_lifecycle_readiness_guard =", result)
    print("guard_mode = new_file_creation_readiness_only")
    print("candidate_id =", candidate_id)
    print("target_family =", target_family)
    print("target_file =", target_file)
    print("target_file_exists =", target_exists)
    print("new_file_creation_readiness =", new_file_creation_readiness)
    print("readiness_blockers =", json.dumps(readiness_blockers, ensure_ascii=False))
    print("missing_new_file_extension_count =", len(missing_new_file_extension))
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
