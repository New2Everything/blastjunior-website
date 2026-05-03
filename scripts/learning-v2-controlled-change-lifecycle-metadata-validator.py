#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
METADATA_DIR = BASE / "controlled-changes"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
METADATA_DIR.mkdir(parents=True, exist_ok=True)

VALIDATOR_ID = "learning-v2-controlled-change-lifecycle-metadata-validator-v0"

REQUIRED_METADATA_KEYS = [
    "change_unit_id",
    "target_family",
    "target_file",
    "risk",
    "change_type",
    "change_goal",
    "allowed_stage",
    "markers",
    "insertion",
    "safety",
    "acceptance",
]

REQUIRED_MARKER_KEYS = [
    "primary_marker",
    "title_marker",
    "required_text_markers",
]

REQUIRED_INSERTION_KEYS = [
    "mode",
    "anchor",
    "block",
]

REQUIRED_SAFETY_KEYS = [
    "max_added_lines",
    "allow_removed_lines",
    "blocked_added_markers",
    "forbidden_target_files",
    "git_commit",
    "git_push",
    "deploy",
]

REQUIRED_ACCEPTANCE_KEYS = [
    "expected_target_file",
    "required_markers",
    "isolated_delta_must_be_only_target",
    "ledger_acceptance_required",
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

def validate_metadata_obj(obj):
    failures = []
    warnings = []

    for key in REQUIRED_METADATA_KEYS:
        if key not in obj:
            failures.append(f"missing_required_key:{key}")

    markers = obj.get("markers") or {}
    insertion = obj.get("insertion") or {}
    safety = obj.get("safety") or {}
    acceptance = obj.get("acceptance") or {}

    for key in REQUIRED_MARKER_KEYS:
        if key not in markers:
            failures.append(f"missing_markers_key:{key}")

    for key in REQUIRED_INSERTION_KEYS:
        if key not in insertion:
            failures.append(f"missing_insertion_key:{key}")

    for key in REQUIRED_SAFETY_KEYS:
        if key not in safety:
            failures.append(f"missing_safety_key:{key}")

    for key in REQUIRED_ACCEPTANCE_KEYS:
        if key not in acceptance:
            failures.append(f"missing_acceptance_key:{key}")

    target_file = obj.get("target_file")
    expected_target_file = acceptance.get("expected_target_file")

    if target_file and expected_target_file and target_file != expected_target_file:
        failures.append(f"target_file_acceptance_mismatch:{target_file}!={expected_target_file}")

    if obj.get("risk") != "low":
        failures.append(f"risk_not_low:{obj.get('risk')}")

    if obj.get("allowed_stage") not in ["metadata_only", "dry_run_only"]:
        failures.append(f"allowed_stage_invalid:{obj.get('allowed_stage')}")

    if safety.get("git_commit") is not False:
        failures.append(f"safety_git_commit_not_false:{safety.get('git_commit')}")

    if safety.get("git_push") is not False:
        failures.append(f"safety_git_push_not_false:{safety.get('git_push')}")

    if safety.get("deploy") is not False:
        failures.append(f"safety_deploy_not_false:{safety.get('deploy')}")

    if safety.get("allow_removed_lines") is not False:
        failures.append(f"safety_allow_removed_lines_not_false:{safety.get('allow_removed_lines')}")

    if not isinstance(safety.get("max_added_lines"), int):
        failures.append("safety_max_added_lines_not_integer")
    elif safety.get("max_added_lines") > 30:
        warnings.append(f"safety_max_added_lines_high:{safety.get('max_added_lines')}")

    required_text_markers = markers.get("required_text_markers")
    if not isinstance(required_text_markers, list) or not required_text_markers:
        failures.append("markers_required_text_markers_empty_or_not_list")

    required_markers = acceptance.get("required_markers")
    if not isinstance(required_markers, list) or not required_markers:
        failures.append("acceptance_required_markers_empty_or_not_list")

    if acceptance.get("isolated_delta_must_be_only_target") is not True:
        failures.append("acceptance_isolated_delta_must_be_only_target_not_true")

    if acceptance.get("ledger_acceptance_required") is not True:
        failures.append("acceptance_ledger_acceptance_required_not_true")

    anchor = insertion.get("anchor")
    block = insertion.get("block")
    if anchor and block and anchor in block:
        warnings.append("insertion_anchor_appears_inside_block_check_if_intentional")

    return failures, warnings

def build_schema_example():
    return {
        "change_unit_id": "example-low-risk-page-cta",
        "target_family": "example.target_family",
        "target_file": "public/example.html",
        "risk": "low",
        "change_type": "minimal_existing_html_cta_insert_or_edit",
        "change_goal": "Add a compact CTA block to improve a specific user path.",
        "allowed_stage": "metadata_only",
        "markers": {
            "primary_marker": "example-primary-marker",
            "title_marker": "example-title-marker",
            "required_text_markers": [
                "Example title",
                "Example CTA"
            ]
        },
        "insertion": {
            "mode": "insert_after_anchor_once",
            "anchor": "<div id=\"exampleAnchor\"></div>",
            "block": "<section class=\"example-primary-marker\">Example CTA</section>"
        },
        "safety": {
            "max_added_lines": 20,
            "allow_removed_lines": False,
            "blocked_added_markers": [
                "<script",
                "fetch(",
                "localStorage",
                "onclick=",
                "onsubmit="
            ],
            "forbidden_target_files": [
                "wrangler.toml",
                "package.json",
                "components/nav.html",
                "components/nav.css"
            ],
            "git_commit": False,
            "git_push": False,
            "deploy": False
        },
        "acceptance": {
            "expected_target_file": "public/example.html",
            "required_markers": [
                "example-primary-marker",
                "example-title-marker"
            ],
            "isolated_delta_must_be_only_target": True,
            "ledger_acceptance_required": True
        }
    }

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    registry_path, registry = latest_report("controlled-change-registry-*.json")
    checker_path, checker = latest_report("controlled-change-template-checker-*.json")
    guard_path, guard = latest_report("controlled-change-duplication-guard-*.json")
    readiness_path, readiness = latest_report("next-loop-readiness-auditor-*.json")
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

    if not registry_path:
        failures.append("missing_controlled_change_registry_report")
    elif registry.get("result") != "ok":
        failures.append(f"registry_not_ok:{registry.get('result')}")

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

    if not readiness_path:
        failures.append("missing_next_loop_readiness_auditor_report")
    elif readiness.get("result") != "ok":
        failures.append(f"next_loop_readiness_not_ok:{readiness.get('result')}")

    if readiness.get("fourth_loop_allowed_now") is not False:
        failures.append(f"fourth_loop_allowed_unexpected:{readiness.get('fourth_loop_allowed_now')}")

    if not integrity_path:
        failures.append("missing_system_integrity_report")
    elif integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    metadata_files = sorted(METADATA_DIR.glob("*.json"))
    metadata_results = []

    for p in metadata_files:
        data = load_json(p, default={})
        f, w = validate_metadata_obj(data)
        metadata_results.append({
            "metadata_file": str(p),
            "result": "ok" if not f else "blocked",
            "change_unit_id": data.get("change_unit_id"),
            "target_family": data.get("target_family"),
            "target_file": data.get("target_file"),
            "failures": f,
            "warnings": w,
        })

    schema_example = build_schema_example()
    schema_example_failures, schema_example_warnings = validate_metadata_obj(schema_example)

    if schema_example_failures:
        failures.append(f"internal_schema_example_invalid:{schema_example_failures}")

    result = "ok" if not failures else "blocked"

    recommended_next_step = (
        "build_controlled_change_generic_dry_run_runner"
        if result == "ok"
        else "fix_controlled_change_lifecycle_metadata_validator_blockers"
    )

    out_json = REPORT_DIR / f"controlled-change-lifecycle-metadata-validator-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"controlled-change-lifecycle-metadata-validator-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "validator_id": VALIDATOR_ID,
        "result": result,
        "metadata_dir": str(METADATA_DIR),
        "metadata_file_count": len(metadata_files),
        "metadata_results": metadata_results,
        "schema_contract": {
            "required_metadata_keys": REQUIRED_METADATA_KEYS,
            "required_marker_keys": REQUIRED_MARKER_KEYS,
            "required_insertion_keys": REQUIRED_INSERTION_KEYS,
            "required_safety_keys": REQUIRED_SAFETY_KEYS,
            "required_acceptance_keys": REQUIRED_ACCEPTANCE_KEYS,
        },
        "schema_example": schema_example,
        "schema_example_warnings": schema_example_warnings,
        "registry_report": str(registry_path) if registry_path else None,
        "template_checker_report": str(checker_path) if checker_path else None,
        "duplication_guard_report": str(guard_path) if guard_path else None,
        "next_loop_readiness_auditor": str(readiness_path) if readiness_path else None,
        "integrity_report": str(integrity_path) if integrity_path else None,
        "recommended_next_step": recommended_next_step,
        "policy": {
            "validator_only": True,
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
    lines.append("# Learning V2 Controlled Change Lifecycle Metadata Validator")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- validator_id: `{VALIDATOR_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- metadata_file_count: `{len(metadata_files)}`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")
    lines.append("- validator_only: `true`")
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

    print("controlled_change_lifecycle_metadata_validator =", result)
    print("metadata_file_count =", len(metadata_files))
    print("recommended_next_step =", recommended_next_step)
    print("validator_only = True")
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
