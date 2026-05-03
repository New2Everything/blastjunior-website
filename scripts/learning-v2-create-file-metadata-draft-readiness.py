#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
CREATE_FILE_METADATA_DIR = BASE / "controlled-create-files"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
CREATE_FILE_METADATA_DIR.mkdir(parents=True, exist_ok=True)

READINESS_ID = "learning-v2-create-file-metadata-draft-readiness-v0"

TARGET_CANDIDATE_ID = "deferred-public-about-page"
TARGET_FAMILY = "community.engagement_path"
TARGET_FILE = "public/about.html"

REQUIRED_CREATE_FILE_COMPONENTS = [
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

def latest_snapshot(pattern):
    files = sorted(SNAPSHOT_DIR.glob(pattern))
    if not files:
        return None
    return files[-1]

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

    extension_closed_snapshot = latest_snapshot("learning-v2-create-file-lifecycle-extension-closed-*.md")

    template_validator_path, template_validator = latest_report("controlled-change-new-file-template-validator-*.json")
    dry_runner_path, dry_runner = latest_report("controlled-change-generic-create-file-dry-run-runner-*.json")
    policy_gate_path, policy_gate = latest_report("controlled-change-generic-create-file-policy-gate-*.json")
    readiness_path, readiness = latest_report("controlled-change-generic-create-file-readiness-*.json")
    apply_path, apply_report = latest_report("controlled-change-generic-create-file-apply-*.json")
    isolated_path, isolated = latest_report("controlled-change-generic-create-file-isolated-validator-*.json")
    ledger_path, ledger = latest_report("controlled-change-generic-create-file-ledger-acceptance-*.json")

    extension_plan_path, extension_plan = latest_report("create-file-from-template-lifecycle-extension-plan-*.json")
    new_file_guard_path, new_file_guard = latest_report("new-file-creation-lifecycle-readiness-guard-*.json")
    planning_brief_path, planning_brief = latest_report("fourth-loop-planning-brief-*.json")
    selector_path, selector = latest_report("next-target-selector-with-duplication-guard-*.json")
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

    if not extension_closed_snapshot:
        failures.append("missing_create_file_lifecycle_extension_closed_snapshot")

    for label, path, report in [
        ("new_file_template_validator", template_validator_path, template_validator),
        ("generic_create_file_dry_run_runner", dry_runner_path, dry_runner),
        ("generic_create_file_policy_gate", policy_gate_path, policy_gate),
        ("generic_create_file_readiness", readiness_path, readiness),
        ("generic_create_file_apply", apply_path, apply_report),
        ("generic_create_file_isolated_validator", isolated_path, isolated),
        ("generic_create_file_ledger_acceptance", ledger_path, ledger),
        ("create_file_extension_plan", extension_plan_path, extension_plan),
        ("new_file_readiness_guard", new_file_guard_path, new_file_guard),
        ("fourth_loop_planning_brief", planning_brief_path, planning_brief),
        ("next_target_selector", selector_path, selector),
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

    component_status = [path_status(x) for x in REQUIRED_CREATE_FILE_COMPONENTS]
    missing_components = [x["path"] for x in component_status if not x["exists"]]
    if missing_components:
        failures.append(f"missing_create_file_components:{missing_components}")

    for key, report in [
        ("blocked_dry_run_count", dry_runner),
        ("blocked_gate_result_count", policy_gate),
        ("blocked_readiness_result_count", readiness),
        ("blocked_apply_result_count", apply_report),
        ("blocked_validation_result_count", isolated),
        ("blocked_acceptance_result_count", ledger),
    ]:
        if report.get(key) not in (0, None):
            failures.append(f"{key}_not_zero:{report.get(key)}")

    if ledger.get("acceptance_mode") != "no_metadata_safe_noop":
        warnings.append(f"ledger_acceptance_mode_not_noop:{ledger.get('acceptance_mode')}")

    if ledger.get("recommended_next_step") != "close_create_file_lifecycle_extension_summary":
        warnings.append(f"ledger_recommended_next_step_unexpected:{ledger.get('recommended_next_step')}")

    for key in [
        "fourth_loop_allowed_now",
        "metadata_written",
        "source_written",
        "state_written",
        "business_source_written",
        "source_change_gate_opened",
        "fourth_loop_started",
    ]:
        for label, report in [
            ("template_validator", template_validator),
            ("dry_runner", dry_runner),
            ("policy_gate", policy_gate),
            ("readiness", readiness),
            ("apply", apply_report),
            ("isolated", isolated),
            ("ledger", ledger),
        ]:
            if key in report and report.get(key) is not False:
                failures.append(f"{label}_{key}_not_false:{report.get(key)}")

    selected = selector.get("selected_candidate") or {}
    if selected.get("candidate_id") != TARGET_CANDIDATE_ID:
        failures.append(f"selector_candidate_id_unexpected:{selected.get('candidate_id')}")

    if selected.get("target_family") != TARGET_FAMILY:
        failures.append(f"selector_target_family_unexpected:{selected.get('target_family')}")

    if selected.get("target_file") != TARGET_FILE:
        failures.append(f"selector_target_file_unexpected:{selected.get('target_file')}")

    if new_file_guard.get("target_file") != TARGET_FILE:
        failures.append(f"new_file_guard_target_file_unexpected:{new_file_guard.get('target_file')}")

    if new_file_guard.get("target_file_exists") is not False:
        failures.append(f"new_file_guard_target_file_exists_not_false:{new_file_guard.get('target_file_exists')}")

    if (WORKSPACE / TARGET_FILE).exists():
        failures.append(f"target_file_already_exists:{TARGET_FILE}")

    existing_metadata_files = sorted(CREATE_FILE_METADATA_DIR.glob("*.json"))
    existing_about_metadata = [
        str(p) for p in existing_metadata_files
        if "about" in p.name.lower() or TARGET_FILE in p.read_text(encoding="utf-8", errors="ignore")
    ]

    if existing_about_metadata:
        warnings.append(f"about_metadata_already_exists:{existing_about_metadata}")

    metadata_draft_requirements = {
        "target_candidate_id": TARGET_CANDIDATE_ID,
        "target_family": TARGET_FAMILY,
        "target_file": TARGET_FILE,
        "target_file_must_not_exist": True,
        "allowed_stage_for_new_metadata": "metadata_draft_only",
        "metadata_dir": str(CREATE_FILE_METADATA_DIR),
        "required_change_type": "create_file_from_template",
        "must_use_new_file_template_contract": True,
        "must_not_write_source": True,
        "must_not_open_source_gate": True,
        "must_not_commit_push_deploy": True,
    }

    readiness_status = "ready_for_metadata_draft_only" if not failures else "blocked"

    result = "ok" if not failures else "blocked"

    recommended_next_step = (
        "build_public_about_create_file_metadata_draft_no_source_write"
        if result == "ok"
        else "fix_create_file_metadata_draft_readiness_blockers"
    )

    out_json = REPORT_DIR / f"create-file-metadata-draft-readiness-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"create-file-metadata-draft-readiness-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "readiness_id": READINESS_ID,
        "result": result,
        "readiness_status": readiness_status,
        "target_candidate_id": TARGET_CANDIDATE_ID,
        "target_family": TARGET_FAMILY,
        "target_file": TARGET_FILE,
        "target_file_exists": (WORKSPACE / TARGET_FILE).exists(),
        "metadata_dir": str(CREATE_FILE_METADATA_DIR),
        "existing_metadata_file_count": len(existing_metadata_files),
        "existing_about_metadata": existing_about_metadata,
        "component_status": component_status,
        "missing_components": missing_components,
        "metadata_draft_requirements": metadata_draft_requirements,
        "extension_closed_snapshot": str(extension_closed_snapshot) if extension_closed_snapshot else None,
        "new_file_template_validator_report": str(template_validator_path) if template_validator_path else None,
        "generic_create_file_dry_run_runner_report": str(dry_runner_path) if dry_runner_path else None,
        "generic_create_file_policy_gate_report": str(policy_gate_path) if policy_gate_path else None,
        "generic_create_file_readiness_report": str(readiness_path) if readiness_path else None,
        "generic_create_file_apply_report": str(apply_path) if apply_path else None,
        "generic_create_file_isolated_validator_report": str(isolated_path) if isolated_path else None,
        "generic_create_file_ledger_acceptance_report": str(ledger_path) if ledger_path else None,
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
            "readiness_only": True,
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
    lines.append("# Learning V2 Create File Metadata Draft Readiness")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- readiness_id: `{READINESS_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- readiness_status: `{readiness_status}`")
    lines.append(f"- target_candidate_id: `{TARGET_CANDIDATE_ID}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- target_file: `{TARGET_FILE}`")
    lines.append(f"- target_file_exists: `{str(payload['target_file_exists']).lower()}`")
    lines.append(f"- existing_metadata_file_count: `{len(existing_metadata_files)}`")
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
    lines.append("## Metadata Draft Requirements")
    for k, v in metadata_draft_requirements.items():
        lines.append(f"- `{k}`: `{v}`")

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

    print("create_file_metadata_draft_readiness =", result)
    print("readiness_status =", readiness_status)
    print("target_candidate_id =", TARGET_CANDIDATE_ID)
    print("target_family =", TARGET_FAMILY)
    print("target_file =", TARGET_FILE)
    print("target_file_exists =", (WORKSPACE / TARGET_FILE).exists())
    print("existing_metadata_file_count =", len(existing_metadata_files))
    print("missing_components =", json.dumps(missing_components, ensure_ascii=False))
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
