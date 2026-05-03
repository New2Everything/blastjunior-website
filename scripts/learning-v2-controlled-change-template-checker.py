#!/usr/bin/env python3
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

CHECKER_ID = "learning-v2-controlled-change-template-checker-v0"

STAGE_CONTRACTS = {
    "source_change_dry_run": {
        "required_keys": [
            "result",
            "target_family",
            "target_file",
            "changed_in_dry_run",
            "source_written",
            "failures",
        ],
        "recommended_keys": [
            "change_plan_id",
            "diff_path",
            "added_line_count",
            "removed_line_count",
            "human_review_required",
            "machine_policy_gate",
            "git_commit",
            "git_push",
            "deploy",
            "recommended_next_step",
        ],
        "must_values": {
            "result": "ok",
            "source_written": False,
        },
    },
    "autonomous_policy_gate": {
        "required_keys": [
            "result",
            "target_file",
            "autonomous_decision",
            "failures",
        ],
        "recommended_keys": [
            "target_family",
            "change_plan_id",
            "dry_run_report",
            "decision_basis",
            "policy",
            "recommended_next_step",
        ],
        "must_values": {
            "result": "ok",
            "autonomous_decision": "allow_next_dry_apply_gate",
        },
    },
    "gate_readiness": {
        "required_keys": [
            "result",
            "target_file",
            "ready_to_open_source_change_gate",
            "failures",
        ],
        "recommended_keys": [
            "target_family",
            "change_plan_id",
            "dry_run_report",
            "autonomous_policy_gate",
            "policy",
            "recommended_next_step",
        ],
        "must_values": {
            "result": "ok",
            "ready_to_open_source_change_gate": True,
        },
    },
    "apply_executor": {
        "required_keys": [
            "result",
            "apply",
            "target_file",
            "source_written",
            "backup_path",
            "failures",
        ],
        "recommended_keys": [
            "target_family",
            "change_plan_id",
            "gate_opened_during_apply",
            "gate_closed_after_apply",
            "state_written",
            "business_source_written",
            "human_review_required",
            "machine_policy_gate",
            "git_commit",
            "git_push",
            "deploy",
            "recommended_next_step",
        ],
        "must_values": {
            "result": "ok",
            "apply": True,
            "source_written": True,
        },
    },
    "isolated_post_apply_validator": {
        "required_keys": [
            "result",
            "target_file",
            "backup_path",
            "isolated_delta_interpretation",
            "failures",
        ],
        "recommended_keys": [
            "required_markers_present",
            "added_line_count",
            "removed_line_count",
            "diff_path",
            "policy",
        ],
        "must_values": {
            "result": "ok",
        },
    },
    "controlled_ledger_acceptance": {
        "required_keys": [
            "result",
            "apply",
            "target_file",
            "controlled_delta_paths",
            "new_dirty_freeze_path",
            "failures",
        ],
        "recommended_keys": [
            "target_family",
            "ready_to_accept",
            "changed_business_paths",
            "new_business_dirty_paths",
            "missing_or_cleaned_business_paths",
            "policy",
        ],
        "must_values": {
            "result": "ok",
            "apply": True,
        },
    },
}

UNIVERSAL_SAFETY_KEYS = [
    "git_commit",
    "git_push",
    "deploy",
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

def latest_registry():
    return latest_report("controlled-change-registry-*.json")

def key_exists(data, key):
    return key in data or find_key(data, key) is not None

def value_for(data, key):
    if key in data:
        return data.get(key)
    return find_key(data, key)

def policy_value(data, key):
    if key in data:
        return data.get(key)
    policy = data.get("policy") or {}
    if key in policy:
        return policy.get(key)
    decision_basis = data.get("decision_basis") or {}
    if key in decision_basis:
        return decision_basis.get(key)
    return find_key(data, key)

def check_stage_contract(unit, stage_entry):
    stage = stage_entry.get("stage")
    contract = STAGE_CONTRACTS.get(stage)
    compact = stage_entry.get("compact") or {}

    gaps = []
    warnings = []

    if not stage_entry.get("declared"):
        warnings.append("stage_not_declared_for_unit")
        return gaps, warnings

    if not stage_entry.get("exists"):
        gaps.append("stage_report_missing")
        return gaps, warnings

    if not contract:
        warnings.append("no_contract_defined_for_stage")
        return gaps, warnings

    for key in contract["required_keys"]:
        if not key_exists(compact, key):
            gaps.append(f"missing_required_key:{key}")

    for key in contract["recommended_keys"]:
        if not key_exists(compact, key):
            warnings.append(f"missing_recommended_key:{key}")

    for key, expected in contract["must_values"].items():
        actual = value_for(compact, key)
        if actual != expected:
            gaps.append(f"must_value_mismatch:{key}:{actual}!={expected}")

    # Universal safety values may live at top-level, policy, or decision_basis.
    for key in UNIVERSAL_SAFETY_KEYS:
        actual = policy_value(compact, key)
        if actual is None:
            warnings.append(f"safety_key_missing_or_historical:{key}")
        elif actual is not False:
            gaps.append(f"safety_key_not_false:{key}:{actual}")

    if compact.get("failures"):
        gaps.append("stage_failures_not_empty")

    # Historical compatibility: first loop predates several standardized fields.
    if unit.get("change_unit_id") == "homepage-onboarding":
        historical_gaps = []
        kept_gaps = []
        for gap in gaps:
            if gap.startswith("missing_required_key:") or gap.startswith("missing_recommended_key:"):
                historical_gaps.append(gap)
            elif gap.startswith("safety_key"):
                historical_gaps.append(gap)
            else:
                kept_gaps.append(gap)

        if historical_gaps:
            warnings.extend([f"historical_schema_gap:{x}" for x in historical_gaps])

        gaps = kept_gaps

    return gaps, warnings

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

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

    for key in [
        "source_changes_allowed",
        "git_commit_allowed",
        "git_push_allowed",
        "deploy_allowed",
    ]:
        if policy.get(key) is not False:
            failures.append(f"policy_{key}_not_false:{policy.get(key)}")

    registry_path, registry = latest_registry()

    if not registry_path:
        failures.append("missing_controlled_change_registry_report")

    if registry.get("result") != "ok":
        failures.append(f"registry_not_ok:{registry.get('result')}")

    if registry.get("registered_unit_count", 0) < 3:
        failures.append(f"registered_unit_count_too_low:{registry.get('registered_unit_count')}")

    units = registry.get("registered_units") or []

    stage_results = []
    unit_results = []

    stage_gap_counter = Counter()
    stage_warning_counter = Counter()

    for unit in units:
        unit_gaps = []
        unit_warnings = []

        for stage_entry in unit.get("lifecycle_stages", []):
            stage = stage_entry.get("stage")
            gaps, stage_warnings = check_stage_contract(unit, stage_entry)

            for gap in gaps:
                stage_gap_counter[f"{stage}:{gap}"] += 1
            for warning in stage_warnings:
                stage_warning_counter[f"{stage}:{warning}"] += 1

            unit_gaps.extend([f"{stage}:{x}" for x in gaps])
            unit_warnings.extend([f"{stage}:{x}" for x in stage_warnings])

            stage_results.append({
                "change_unit_id": unit.get("change_unit_id"),
                "target_file": unit.get("target_file"),
                "stage": stage,
                "latest_report": stage_entry.get("latest_report"),
                "contract_gaps": gaps,
                "contract_warnings": stage_warnings,
            })

        unit_results.append({
            "change_unit_id": unit.get("change_unit_id"),
            "loop_index": unit.get("loop_index"),
            "target_file": unit.get("target_file"),
            "target_family": unit.get("target_family"),
            "contract_status": "template_ready" if not unit_gaps else "template_gaps_found",
            "contract_gap_count": len(unit_gaps),
            "contract_warning_count": len(unit_warnings),
            "contract_gaps": unit_gaps,
            "contract_warnings": unit_warnings,
        })

    strict_template_ready_units = [
        u for u in unit_results
        if u.get("contract_status") == "template_ready"
    ]

    recommended_template_basis = [
        u for u in unit_results
        if u.get("change_unit_id") == "engagement-news-return-path"
    ]

    template_gap_count = sum(u["contract_gap_count"] for u in unit_results)
    historical_warning_count = sum(
        1 for u in unit_results for w in u.get("contract_warnings", [])
        if "historical" in w
    )

    # Template checker is allowed to be ok with gaps because its job is to surface
    # template standardization needs, not to block the system.
    result = "ok" if not failures else "blocked"

    recommended_next_step = (
        "build_controlled_change_duplication_guard"
        if result == "ok"
        else "fix_controlled_change_template_checker_blockers"
    )

    out_json = REPORT_DIR / f"controlled-change-template-checker-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"controlled-change-template-checker-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "checker_id": CHECKER_ID,
        "result": result,
        "registry_report": str(registry_path) if registry_path else None,
        "unit_count": len(units),
        "strict_template_ready_unit_count": len(strict_template_ready_units),
        "template_gap_count": template_gap_count,
        "historical_warning_count": historical_warning_count,
        "stage_gap_counter": dict(stage_gap_counter),
        "stage_warning_counter": dict(stage_warning_counter),
        "unit_results": unit_results,
        "stage_results": stage_results,
        "recommended_template_basis": recommended_template_basis,
        "stage_contracts": STAGE_CONTRACTS,
        "recommended_next_step": recommended_next_step,
        "policy": {
            "checker_only": True,
            "state_written": False,
            "business_source_written": False,
            "source_change_gate_opened": False,
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
    lines.append("# Learning V2 Controlled Change Template Checker")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- checker_id: `{CHECKER_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- unit_count: `{len(units)}`")
    lines.append(f"- strict_template_ready_unit_count: `{len(strict_template_ready_units)}`")
    lines.append(f"- template_gap_count: `{template_gap_count}`")
    lines.append(f"- historical_warning_count: `{historical_warning_count}`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")
    lines.append("- checker_only: `true`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- human_review_required: `false`")
    lines.append("- machine_policy_gate: `true`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Unit Results")
    for unit in unit_results:
        lines.append(
            f"- `{unit['change_unit_id']}` target=`{unit['target_file']}` "
            f"status=`{unit['contract_status']}` gaps=`{unit['contract_gap_count']}` warnings=`{unit['contract_warning_count']}`"
        )
    lines.append("")
    lines.append("## Stage Gap Counter")
    if stage_gap_counter:
        for k, v in sorted(stage_gap_counter.items()):
            lines.append(f"- `{k}`: `{v}`")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Stage Warning Counter")
    if stage_warning_counter:
        for k, v in sorted(stage_warning_counter.items()):
            lines.append(f"- `{k}`: `{v}`")
    else:
        lines.append("- none")

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

    print("controlled_change_template_checker =", result)
    print("unit_count =", len(units))
    print("strict_template_ready_unit_count =", len(strict_template_ready_units))
    print("template_gap_count =", template_gap_count)
    print("historical_warning_count =", historical_warning_count)
    print("recommended_next_step =", recommended_next_step)
    print("checker_only = True")
    print("state_written = False")
    print("business_source_written = False")
    print("source_change_gate_opened = False")
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
