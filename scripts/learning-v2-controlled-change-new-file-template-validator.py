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

VALIDATOR_ID = "learning-v2-controlled-change-new-file-template-validator-v0"

REQUIRED_METADATA_KEYS = [
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
]

REQUIRED_TEMPLATE_KEYS = [
    "mode",
    "template_name",
    "template_source",
    "body",
    "required_sections",
]

REQUIRED_SAFETY_KEYS = [
    "target_file_must_not_exist",
    "allowed_target_prefixes",
    "forbidden_target_files",
    "max_total_lines",
    "blocked_content_markers",
    "git_commit",
    "git_push",
    "deploy",
]

REQUIRED_ACCEPTANCE_KEYS = [
    "expected_target_file",
    "required_markers",
    "created_file_must_be_only_delta",
    "ledger_acceptance_required",
]

FORBIDDEN_TARGET_FILES = {
    "wrangler.toml",
    "package.json",
    "components/nav.html",
    "components/nav.css",
    "public/index.html",
    "public/gallery.html",
    "public/news.html",
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

def validate_create_file_metadata(meta):
    failures = []
    warnings = []

    for key in REQUIRED_METADATA_KEYS:
        if key not in meta:
            failures.append(f"missing_metadata_key:{key}")

    template = meta.get("template") or {}
    safety = meta.get("safety") or {}
    acceptance = meta.get("acceptance") or {}

    for key in REQUIRED_TEMPLATE_KEYS:
        if key not in template:
            failures.append(f"missing_template_key:{key}")

    for key in REQUIRED_SAFETY_KEYS:
        if key not in safety:
            failures.append(f"missing_safety_key:{key}")

    for key in REQUIRED_ACCEPTANCE_KEYS:
        if key not in acceptance:
            failures.append(f"missing_acceptance_key:{key}")

    target_file = str(meta.get("target_file") or "").lstrip("./")
    expected_target_file = str(acceptance.get("expected_target_file") or "").lstrip("./")

    if not target_file:
        failures.append("target_file_empty")

    if target_file and expected_target_file and target_file != expected_target_file:
        failures.append(f"target_file_acceptance_mismatch:{target_file}!={expected_target_file}")

    if target_file in FORBIDDEN_TARGET_FILES:
        failures.append(f"target_file_forbidden:{target_file}")

    allowed_prefixes = safety.get("allowed_target_prefixes") or []
    if target_file and allowed_prefixes:
        if not any(target_file.startswith(str(prefix).lstrip("./")) for prefix in allowed_prefixes):
            failures.append(f"target_file_not_under_allowed_prefix:{target_file}")

    if target_file and (WORKSPACE / target_file).exists():
        failures.append(f"target_file_already_exists:{target_file}")

    if meta.get("risk") != "low":
        failures.append(f"risk_not_low:{meta.get('risk')}")

    if meta.get("change_type") != "create_file_from_template":
        failures.append(f"change_type_not_create_file_from_template:{meta.get('change_type')}")

    if meta.get("allowed_stage") not in ["metadata_draft_only", "dry_run_only"]:
        failures.append(f"allowed_stage_invalid:{meta.get('allowed_stage')}")

    if template.get("mode") != "create_file_from_template":
        failures.append(f"template_mode_invalid:{template.get('mode')}")

    body = template.get("body")
    if not isinstance(body, str) or not body.strip():
        failures.append("template_body_empty_or_not_string")

    required_sections = template.get("required_sections")
    if not isinstance(required_sections, list) or not required_sections:
        failures.append("template_required_sections_empty_or_not_list")
    elif isinstance(body, str):
        for section in required_sections:
            if section not in body:
                failures.append(f"template_body_missing_required_section:{section}")

    if safety.get("target_file_must_not_exist") is not True:
        failures.append(f"safety_target_file_must_not_exist_not_true:{safety.get('target_file_must_not_exist')}")

    if safety.get("git_commit") is not False:
        failures.append(f"safety_git_commit_not_false:{safety.get('git_commit')}")

    if safety.get("git_push") is not False:
        failures.append(f"safety_git_push_not_false:{safety.get('git_push')}")

    if safety.get("deploy") is not False:
        failures.append(f"safety_deploy_not_false:{safety.get('deploy')}")

    max_total_lines = safety.get("max_total_lines")
    if not isinstance(max_total_lines, int):
        failures.append("safety_max_total_lines_not_integer")
    elif max_total_lines > 240:
        warnings.append(f"safety_max_total_lines_high:{max_total_lines}")

    blocked_markers = safety.get("blocked_content_markers") or []
    if isinstance(body, str):
        for marker in blocked_markers:
            if str(marker).lower() in body.lower():
                failures.append(f"blocked_content_marker_found:{marker}")

    required_markers = acceptance.get("required_markers")
    if not isinstance(required_markers, list) or not required_markers:
        failures.append("acceptance_required_markers_empty_or_not_list")
    elif isinstance(body, str):
        for marker in required_markers:
            if marker not in body:
                failures.append(f"template_body_missing_acceptance_marker:{marker}")

    if acceptance.get("created_file_must_be_only_delta") is not True:
        failures.append("acceptance_created_file_must_be_only_delta_not_true")

    if acceptance.get("ledger_acceptance_required") is not True:
        failures.append("acceptance_ledger_acceptance_required_not_true")

    return failures, warnings

def build_schema_example():
    return {
        "change_unit_id": "create-public-about-page-v0",
        "target_family": "community.engagement_path",
        "target_file": "public/about.html",
        "risk": "low",
        "change_type": "create_file_from_template",
        "change_goal": "Create a simple about page that explains the community path without changing existing pages.",
        "allowed_stage": "metadata_draft_only",
        "template": {
            "mode": "create_file_from_template",
            "template_name": "simple-static-about-page",
            "template_source": "generic_create_file_lifecycle_v0",
            "body": "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n  <meta charset=\"UTF-8\" />\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />\n  <title>关于兰星少年</title>\n</head>\n<body>\n  <main class=\"about-page\" data-controlled-create-file=\"public-about-page\">\n    <h1 id=\"about-page-title\">关于兰星少年</h1>\n    <section aria-labelledby=\"about-page-title\">\n      <p>兰星少年是围绕 HADO 运动体验、训练、赛事和社区连接形成的青少年成长空间。</p>\n    </section>\n  </main>\n</body>\n</html>\n",
            "required_sections": [
                "<!DOCTYPE html>",
                "data-controlled-create-file=\"public-about-page\"",
                "id=\"about-page-title\""
            ]
        },
        "safety": {
            "target_file_must_not_exist": True,
            "allowed_target_prefixes": ["public/"],
            "forbidden_target_files": sorted(FORBIDDEN_TARGET_FILES),
            "max_total_lines": 120,
            "blocked_content_markers": [
                "<script",
                "fetch(",
                "localStorage",
                "onclick=",
                "onsubmit=",
                "wrangler",
                "D1",
                "KV",
                "R2"
            ],
            "git_commit": False,
            "git_push": False,
            "deploy": False
        },
        "acceptance": {
            "expected_target_file": "public/about.html",
            "required_markers": [
                "data-controlled-create-file=\"public-about-page\"",
                "id=\"about-page-title\"",
                "关于兰星少年"
            ],
            "created_file_must_be_only_delta": True,
            "ledger_acceptance_required": True
        }
    }

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    extension_plan_path, extension_plan = latest_report("create-file-from-template-lifecycle-extension-plan-*.json")
    readiness_guard_path, readiness_guard = latest_report("new-file-creation-lifecycle-readiness-guard-*.json")
    planning_brief_path, planning_brief = latest_report("fourth-loop-planning-brief-*.json")
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
        ("create_file_extension_plan", extension_plan_path, extension_plan),
        ("new_file_readiness_guard", readiness_guard_path, readiness_guard),
        ("fourth_loop_planning_brief", planning_brief_path, planning_brief),
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

    if extension_plan.get("recommended_next_step") != "build_new_file_template_validator_no_source_write":
        warnings.append(f"extension_plan_recommended_next_step_unexpected:{extension_plan.get('recommended_next_step')}")

    if readiness_guard.get("target_file") != "public/about.html":
        failures.append(f"readiness_guard_target_file_unexpected:{readiness_guard.get('target_file')}")

    if readiness_guard.get("target_file_exists") is not False:
        failures.append(f"target_file_exists_not_false:{readiness_guard.get('target_file_exists')}")

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

    metadata_files = sorted(CREATE_FILE_METADATA_DIR.glob("*.json"))
    metadata_results = []

    for p in metadata_files:
        meta = load_json(p, default={})
        f, w = validate_create_file_metadata(meta)
        metadata_results.append({
            "metadata_file": str(p),
            "result": "ok" if not f else "blocked",
            "change_unit_id": meta.get("change_unit_id"),
            "target_family": meta.get("target_family"),
            "target_file": meta.get("target_file"),
            "failures": f,
            "warnings": w,
        })

    schema_example = build_schema_example()
    example_failures, example_warnings = validate_create_file_metadata(schema_example)
    if example_failures:
        failures.append(f"internal_schema_example_invalid:{example_failures}")

    result = "ok" if not failures else "blocked"

    recommended_next_step = (
        "build_generic_create_file_dry_run_runner"
        if result == "ok"
        else "fix_new_file_template_validator_blockers"
    )

    out_json = REPORT_DIR / f"controlled-change-new-file-template-validator-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"controlled-change-new-file-template-validator-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "validator_id": VALIDATOR_ID,
        "result": result,
        "validator_mode": "new_file_template_contract_only",
        "metadata_dir": str(CREATE_FILE_METADATA_DIR),
        "metadata_file_count": len(metadata_files),
        "metadata_results": metadata_results,
        "schema_contract": {
            "required_metadata_keys": REQUIRED_METADATA_KEYS,
            "required_template_keys": REQUIRED_TEMPLATE_KEYS,
            "required_safety_keys": REQUIRED_SAFETY_KEYS,
            "required_acceptance_keys": REQUIRED_ACCEPTANCE_KEYS,
        },
        "schema_example": schema_example,
        "schema_example_warnings": example_warnings,
        "create_file_extension_plan_report": str(extension_plan_path) if extension_plan_path else None,
        "new_file_readiness_guard_report": str(readiness_guard_path) if readiness_guard_path else None,
        "fourth_loop_planning_brief_report": str(planning_brief_path) if planning_brief_path else None,
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
            "validator_only": True,
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
    lines.append("# Learning V2 Controlled Change New File Template Validator")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- validator_id: `{VALIDATOR_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append("- validator_mode: `new_file_template_contract_only`")
    lines.append(f"- metadata_file_count: `{len(metadata_files)}`")
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
    lines.append("## Metadata Results")
    if metadata_results:
        for item in metadata_results:
            lines.append(
                f"- `{item.get('metadata_file')}` result=`{item.get('result')}` "
                f"target=`{item.get('target_file')}` failures=`{item.get('failures')}`"
            )
    else:
        lines.append("- none yet")
    lines.append("")
    lines.append("## Schema Contract")
    for key, value in payload["schema_contract"].items():
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

    print("controlled_change_new_file_template_validator =", result)
    print("validator_mode = new_file_template_contract_only")
    print("metadata_file_count =", len(metadata_files))
    print("recommended_next_step =", recommended_next_step)
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
    print("report_json =", out_json)
    print("report_md =", out_md)

    if warnings:
        print("warnings =", json.dumps(warnings, ensure_ascii=False))
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
