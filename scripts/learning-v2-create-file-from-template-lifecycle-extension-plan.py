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

PLAN_ID = "learning-v2-create-file-from-template-lifecycle-extension-plan-v0"

NEW_FILE_EXTENSION_COMPONENTS = [
    {
        "script": "scripts/learning-v2-controlled-change-new-file-template-validator.py",
        "purpose": "Validate create-file metadata and template contract before any dry-run.",
        "allowed_to_write_business_source": False,
        "allowed_to_write_metadata": False,
    },
    {
        "script": "scripts/learning-v2-controlled-change-generic-create-file-dry-run-runner.py",
        "purpose": "Preview creation of a missing target file from a declared template without writing it.",
        "allowed_to_write_business_source": False,
        "allowed_to_write_metadata": False,
    },
    {
        "script": "scripts/learning-v2-controlled-change-generic-create-file-policy-gate.py",
        "purpose": "Machine policy gate for create-file dry-run results.",
        "allowed_to_write_business_source": False,
        "allowed_to_write_metadata": False,
    },
    {
        "script": "scripts/learning-v2-controlled-change-generic-create-file-readiness.py",
        "purpose": "Confirm create-file operation is ready for apply self-check.",
        "allowed_to_write_business_source": False,
        "allowed_to_write_metadata": False,
    },
    {
        "script": "scripts/learning-v2-controlled-change-generic-create-file-apply.py",
        "purpose": "Self-check first; only later support controlled create-file apply with gate open/close.",
        "allowed_to_write_business_source": "only_with_explicit_apply_and_prior_gates",
        "allowed_to_write_metadata": False,
    },
    {
        "script": "scripts/learning-v2-controlled-change-generic-create-file-isolated-validator.py",
        "purpose": "Validate missing-to-current file creation delta in isolation.",
        "allowed_to_write_business_source": False,
        "allowed_to_write_metadata": False,
    },
    {
        "script": "scripts/learning-v2-controlled-change-generic-create-file-ledger-acceptance.py",
        "purpose": "Accept validated create-file delta into dirty-freeze.",
        "allowed_to_write_business_source": False,
        "allowed_to_write_metadata": False,
    },
]

CREATE_FILE_METADATA_CONTRACT = {
    "required_metadata_keys": [
        "change_unit_id",
        "target_family",
        "target_file",
        "risk",
        "change_type",
        "change_goal",
        "allowed_stage",
        "template",
        "safety",
        "acceptance",
    ],
    "required_template_keys": [
        "mode",
        "template_name",
        "template_source",
        "body",
        "required_sections",
    ],
    "required_safety_keys": [
        "target_file_must_not_exist",
        "allowed_target_prefixes",
        "forbidden_target_files",
        "max_total_lines",
        "blocked_content_markers",
        "git_commit",
        "git_push",
        "deploy",
    ],
    "required_acceptance_keys": [
        "expected_target_file",
        "required_markers",
        "created_file_must_be_only_delta",
        "ledger_acceptance_required",
    ],
}

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

    readiness_guard_path, readiness_guard = latest_report("new-file-creation-lifecycle-readiness-guard-*.json")
    planning_brief_path, planning_brief = latest_report("fourth-loop-planning-brief-*.json")
    selector_path, selector = latest_report("next-target-selector-with-duplication-guard-*.json")
    next_loop_path, next_loop = latest_report("next-loop-readiness-auditor-*.json")
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
        ("new_file_creation_readiness_guard", readiness_guard_path, readiness_guard),
        ("fourth_loop_planning_brief", planning_brief_path, planning_brief),
        ("next_target_selector", selector_path, selector),
        ("next_loop_readiness", next_loop_path, next_loop),
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

    target_file = readiness_guard.get("target_file")
    target_family = readiness_guard.get("target_family")
    candidate_id = readiness_guard.get("candidate_id")
    target_file_exists = readiness_guard.get("target_file_exists")

    if target_file != "public/about.html":
        failures.append(f"unexpected_target_file:{target_file}")

    if target_family != "community.engagement_path":
        failures.append(f"unexpected_target_family:{target_family}")

    if target_file_exists is not False:
        failures.append(f"target_file_exists_not_false:{target_file_exists}")

    if readiness_guard.get("new_file_creation_readiness") != "not_ready":
        failures.append(f"new_file_creation_readiness_not_not_ready:{readiness_guard.get('new_file_creation_readiness')}")

    readiness_blockers = readiness_guard.get("readiness_blockers") or []
    expected_blockers = [
        "target_file_missing",
        "new_file_creation_lifecycle_extension_missing",
        "current_generic_lifecycle_supports_new_file_creation_false",
    ]
    for blocker in expected_blockers:
        if blocker not in readiness_blockers:
            failures.append(f"expected_readiness_blocker_missing:{blocker}")

    for key in [
        "fourth_loop_allowed_now",
        "metadata_written",
        "source_written",
        "state_written",
        "business_source_written",
        "source_change_gate_opened",
        "fourth_loop_started",
    ]:
        if readiness_guard.get(key) is not False:
            failures.append(f"readiness_guard_{key}_not_false:{readiness_guard.get(key)}")

    component_status = [path_status(x["script"]) for x in NEW_FILE_EXTENSION_COMPONENTS]
    existing_components = [x for x in component_status if x["exists"]]
    missing_components = [x["path"] for x in component_status if not x["exists"]]

    if existing_components:
        warnings.append(f"some_new_file_extension_components_already_exist:{[x['path'] for x in existing_components]}")

    extension_plan = {
        "candidate_id": candidate_id,
        "target_family": target_family,
        "target_file": target_file,
        "target_file_exists": target_file_exists,
        "extension_status": "plan_only_not_built",
        "why_extension_is_needed": [
            "public/about.html is missing",
            "existing generic lifecycle only supports existing-file insert_after_anchor_once",
            "new file creation needs a separate template and acceptance model",
        ],
        "components_to_build": NEW_FILE_EXTENSION_COMPONENTS,
        "metadata_contract": CREATE_FILE_METADATA_CONTRACT,
        "initial_allowed_stage": "plan_only",
        "future_allowed_stage_after_extension": "metadata_draft_only",
        "source_change_allowed_now": False,
        "metadata_creation_allowed_now": False,
        "fourth_loop_allowed_now": False,
    }

    result = "ok" if not failures else "blocked"

    recommended_next_step = (
        "build_new_file_template_validator_no_source_write"
        if result == "ok"
        else "fix_create_file_from_template_lifecycle_extension_plan_blockers"
    )

    out_json = REPORT_DIR / f"create-file-from-template-lifecycle-extension-plan-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"create-file-from-template-lifecycle-extension-plan-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "plan_id": PLAN_ID,
        "result": result,
        "plan_mode": "no_source_write_extension_plan",
        "candidate_id": candidate_id,
        "target_family": target_family,
        "target_file": target_file,
        "target_file_exists": target_file_exists,
        "component_count": len(NEW_FILE_EXTENSION_COMPONENTS),
        "missing_component_count": len(missing_components),
        "missing_components": missing_components,
        "extension_plan": extension_plan,
        "new_file_creation_readiness_guard_report": str(readiness_guard_path) if readiness_guard_path else None,
        "fourth_loop_planning_brief_report": str(planning_brief_path) if planning_brief_path else None,
        "next_target_selector_report": str(selector_path) if selector_path else None,
        "next_loop_readiness_report": str(next_loop_path) if next_loop_path else None,
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
            "plan_only": True,
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
    lines.append("# Learning V2 Create File From Template Lifecycle Extension Plan")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- plan_id: `{PLAN_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append("- plan_mode: `no_source_write_extension_plan`")
    lines.append(f"- candidate_id: `{candidate_id}`")
    lines.append(f"- target_family: `{target_family}`")
    lines.append(f"- target_file: `{target_file}`")
    lines.append(f"- target_file_exists: `{str(target_file_exists).lower()}`")
    lines.append(f"- component_count: `{len(NEW_FILE_EXTENSION_COMPONENTS)}`")
    lines.append(f"- missing_component_count: `{len(missing_components)}`")
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
    lines.append("## Components To Build")
    for item in NEW_FILE_EXTENSION_COMPONENTS:
        lines.append(f"- `{item['script']}` — {item['purpose']}")
    lines.append("")
    lines.append("## Metadata Contract")
    for key, value in CREATE_FILE_METADATA_CONTRACT.items():
        lines.append(f"- `{key}`: `{value}`")

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

    print("create_file_from_template_lifecycle_extension_plan =", result)
    print("plan_mode = no_source_write_extension_plan")
    print("candidate_id =", candidate_id)
    print("target_family =", target_family)
    print("target_file =", target_file)
    print("target_file_exists =", target_file_exists)
    print("component_count =", len(NEW_FILE_EXTENSION_COMPONENTS))
    print("missing_component_count =", len(missing_components))
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
