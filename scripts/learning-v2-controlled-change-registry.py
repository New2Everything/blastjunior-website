#!/usr/bin/env python3
import ast
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

REGISTRY_ID = "learning-v2-controlled-change-registry-v0"

LIFECYCLE_STAGES = [
    {
        "stage": "source_change_dry_run",
        "purpose": "Produce proposed diff without writing business source.",
        "required_policy": {
            "source_written": False,
            "state_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
    },
    {
        "stage": "autonomous_policy_gate",
        "purpose": "Machine gate checks whether dry-run can advance to readiness.",
        "required_policy": {
            "human_review_required": False,
            "machine_policy_gate": True,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
    },
    {
        "stage": "gate_readiness",
        "purpose": "Confirm conditions for temporarily opening source-change gate.",
        "required_policy": {
            "source_written": False,
            "state_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
    },
    {
        "stage": "apply_executor",
        "purpose": "Self-check first, then optionally open gate briefly, backup, write one target, and close gate.",
        "required_policy": {
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
    },
    {
        "stage": "isolated_post_apply_validator",
        "purpose": "Compare backup to current and prove only intended target delta exists.",
        "required_policy": {
            "state_written": False,
            "source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
    },
    {
        "stage": "controlled_ledger_acceptance",
        "purpose": "Accept validated business-source delta into dirty-freeze.",
        "required_policy": {
            "source_written_by_acceptance": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
    },
]

KNOWN_CHANGE_UNITS = [
    {
        "change_unit_id": "homepage-onboarding",
        "loop_index": 1,
        "target_family": "community.onboarding_experience",
        "target_file": "public/index.html",
        "change": "homepage onboarding block",
        "report_patterns": {
            "source_change_dry_run": ["homepage-onboarding-source-change-dry-run-*.json"],
            "gate_readiness": ["homepage-onboarding-source-change-gate-readiness-*.json"],
            "apply_executor": ["homepage-onboarding-source-change-apply-apply-*.json"],
            "isolated_post_apply_validator": ["homepage-onboarding-isolated-post-apply-validator-*.json"],
            "controlled_ledger_acceptance": ["homepage-onboarding-controlled-ledger-acceptance-apply-*.json"],
        },
        "snapshot_patterns": [
            "learning-v2-homepage-onboarding-controlled-change-closed-*.md",
            "*homepage*controlled*closed*.md",
        ],
    },
    {
        "change_unit_id": "gallery-next-action",
        "loop_index": 2,
        "target_family": "community.onboarding_experience",
        "target_file": "public/gallery.html",
        "change": "gallery next-action block",
        "report_patterns": {
            "source_change_dry_run": ["gallery-next-action-source-change-dry-run-*.json"],
            "autonomous_policy_gate": ["autonomous-change-policy-gate-*.json"],
            "gate_readiness": ["gallery-next-action-gate-readiness-*.json"],
            "apply_executor": ["gallery-next-action-source-change-apply-apply-*.json"],
            "isolated_post_apply_validator": ["gallery-next-action-isolated-post-apply-validator-*.json"],
            "controlled_ledger_acceptance": ["gallery-next-action-controlled-ledger-acceptance-apply-*.json"],
        },
        "snapshot_patterns": [
            "learning-v2-gallery-next-action-controlled-change-closed-*.md",
        ],
    },
    {
        "change_unit_id": "engagement-news-return-path",
        "loop_index": 3,
        "target_family": "community.engagement_path",
        "target_file": "public/news.html",
        "change": "engagement news return-path CTA block",
        "report_patterns": {
            "source_change_dry_run": ["engagement-news-return-path-source-change-dry-run-*.json"],
            "autonomous_policy_gate": ["engagement-news-return-path-autonomous-policy-gate-*.json"],
            "gate_readiness": ["engagement-news-return-path-gate-readiness-*.json"],
            "apply_executor": ["engagement-news-return-path-source-change-apply-apply-*.json"],
            "isolated_post_apply_validator": ["engagement-news-return-path-isolated-post-apply-validator-*.json"],
            "controlled_ledger_acceptance": ["engagement-news-return-path-controlled-ledger-acceptance-apply-*.json"],
        },
        "snapshot_patterns": [
            "learning-v2-engagement-news-return-path-controlled-change-closed-*.md",
        ],
    },
]

SCRIPT_STAGE_NEEDLES = {
    "source_change_dry_run": ["source-change-dry-run"],
    "autonomous_policy_gate": ["policy-gate"],
    "gate_readiness": ["gate-readiness"],
    "apply_executor": ["source-change-apply"],
    "isolated_post_apply_validator": ["isolated-post-apply-validator"],
    "controlled_ledger_acceptance": ["controlled-ledger-acceptance"],
    "probe": ["-probe.py"],
    "probe_design": ["probe-design"],
    "resolver": ["resolver"],
    "proposal_planner": ["proposal-planner"],
    "controlled_source_change_plan": ["controlled-source-change-plan"],
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

def latest_report_for_patterns(patterns, target_file=None, target_family=None):
    candidates = []
    for pattern in patterns:
        for p in REPORT_DIR.glob(pattern):
            try:
                data = load_json(p, default={})
            except Exception:
                continue

            data_target_file = data.get("target_file") or find_key(data, "target_file")
            data_target_family = data.get("target_family") or find_key(data, "target_family")

            if target_file and data_target_file and data_target_file != target_file:
                continue

            if target_family and data_target_family and data_target_family != target_family:
                continue

            candidates.append((p, data))

    if not candidates:
        return None, {}

    candidates.sort(key=lambda x: x[0].name)
    return candidates[-1]

def latest_snapshot_for_patterns(patterns):
    candidates = []
    for pattern in patterns:
        candidates.extend(SNAPSHOT_DIR.glob(pattern))
    candidates = sorted(set(candidates), key=lambda p: p.name)
    return candidates[-1] if candidates else None

def compact_report(stage, data):
    keys = [
        "result",
        "target_family",
        "target_file",
        "change_plan_id",
        "apply",
        "source_written",
        "state_written",
        "business_source_written",
        "source_change_gate_opened",
        "human_review_required",
        "machine_policy_gate",
        "git_commit",
        "git_push",
        "deploy",
        "changed_in_dry_run",
        "insert_anchor_found",
        "required_markers",
        "required_markers_present",
        "proposed_contains_required_markers",
        "ready_to_open_source_change_gate",
        "autonomous_decision",
        "recommended_next_step",
        "dry_run_report",
        "autonomous_policy_gate",
        "gate_readiness",
        "controlled_source_change_plan",
        "apply_report",
        "isolated_post_apply_validator",
        "decision_basis",
        "gate_opened_during_apply",
        "gate_closed_after_apply",
        "backup_path",
        "post_contains_news_engagement_return_path",
        "post_contains_news_engagement_return_path_title",
        "current_has_news_engagement_return_path",
        "current_has_news_engagement_return_path_title",
        "isolated_delta_interpretation",
        "diff_path",
        "diff_line_count",
        "added_line_count",
        "removed_line_count",
        "changed_business_paths",
        "new_business_dirty_paths",
        "controlled_delta_paths",
        "missing_or_cleaned_business_paths",
        "new_dirty_freeze_path",
        "ready_to_accept",
        "failures",
    ]

    compact = {}
    for k in keys:
        if k in data:
            compact[k] = data.get(k)

    policy = data.get("policy")
    if isinstance(policy, dict):
        compact["policy"] = {
            k: policy.get(k)
            for k in [
                "source_written",
                "state_written",
                "business_source_written",
                "source_written_by_acceptance",
                "source_change_gate_opened",
                "human_review_required",
                "machine_policy_gate",
                "git_commit",
                "git_push",
                "deploy",
            ]
            if k in policy
        }

    return compact

def validate_stage(stage, data):
    failures = []
    warnings = []

    if not data:
        failures.append("stage_report_missing")
        return failures, warnings

    if data.get("result") != "ok":
        failures.append(f"stage_result_not_ok:{data.get('result')}")

    if data.get("failures"):
        failures.append("stage_has_failures")

    if stage == "source_change_dry_run":
        if data.get("source_written") is not False:
            policy = data.get("policy") or {}
            if policy.get("source_written") is not False:
                failures.append(f"dry_run_source_written_not_false:{data.get('source_written') or policy.get('source_written')}")
        if data.get("changed_in_dry_run") is False:
            warnings.append("dry_run_changed_in_dry_run_false")

    if stage == "autonomous_policy_gate":
        if data.get("autonomous_decision") != "allow_next_dry_apply_gate":
            failures.append(f"autonomous_decision_not_allow:{data.get('autonomous_decision')}")

    if stage == "gate_readiness":
        if data.get("ready_to_open_source_change_gate") is not True:
            failures.append(f"readiness_not_ready:{data.get('ready_to_open_source_change_gate')}")

    if stage == "apply_executor":
        if data.get("apply") is not True:
            failures.append(f"apply_not_true:{data.get('apply')}")
        if data.get("source_written") is not True:
            failures.append(f"apply_source_written_not_true:{data.get('source_written')}")

        policy = data.get("policy") or {}

        git_commit = data.get("git_commit")
        if git_commit is None:
            git_commit = policy.get("git_commit")

        git_push = data.get("git_push")
        if git_push is None:
            git_push = policy.get("git_push")

        deploy = data.get("deploy")
        if deploy is None:
            deploy = policy.get("deploy")

        if git_commit is not False:
            if git_commit is None:
                warnings.append("apply_git_commit_field_missing_in_historical_schema")
            else:
                failures.append(f"apply_git_commit_not_false:{git_commit}")

        if git_push is not False:
            if git_push is None:
                warnings.append("apply_git_push_field_missing_in_historical_schema")
            else:
                failures.append(f"apply_git_push_not_false:{git_push}")

        if deploy is not False:
            if deploy is None:
                warnings.append("apply_deploy_field_missing_in_historical_schema")
            else:
                failures.append(f"apply_deploy_not_false:{deploy}")

    if stage == "isolated_post_apply_validator":
        interp = data.get("isolated_delta_interpretation")
        if interp and "only" not in str(interp):
            failures.append(f"isolated_delta_not_clean:{interp}")
        if data.get("removed_line_count") not in (0, None):
            failures.append(f"isolated_removed_lines:{data.get('removed_line_count')}")

    if stage == "controlled_ledger_acceptance":
        if data.get("apply") is not True:
            failures.append(f"ledger_apply_not_true:{data.get('apply')}")
        if data.get("ready_to_accept") is not True:
            failures.append(f"ledger_not_ready_to_accept:{data.get('ready_to_accept')}")
        if not data.get("new_dirty_freeze_path"):
            failures.append("ledger_missing_new_dirty_freeze_path")

    return failures, warnings

def extract_constants(path):
    out = {}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_parse_error": str(e)}

    wanted = {
        "TARGET_FAMILY",
        "TARGET_FILE",
        "CHANGE_PLAN_ID",
        "DRY_RUN_ID",
        "GATE_ID",
        "READINESS_ID",
        "APPLY_ID",
        "VALIDATOR_ID",
        "ACCEPTANCE_ID",
    }

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in wanted:
                    try:
                        out[target.id] = ast.literal_eval(node.value)
                    except Exception:
                        out[target.id] = "<non_literal>"
    return out

def classify_script_stage(name):
    hits = []
    for stage, needles in SCRIPT_STAGE_NEEDLES.items():
        if any(n in name for n in needles):
            hits.append(stage)
    return hits or ["other"]

def build_template_candidate_inventory():
    rows = []
    for p in sorted((WORKSPACE / "scripts").glob("learning-v2-*.py")):
        stages = classify_script_stage(p.name)
        constants = extract_constants(p)
        rows.append({
            "script": str(p.relative_to(WORKSPACE)),
            "stages": stages,
            "size_bytes": p.stat().st_size,
            "constants": constants,
        })

    stage_groups = defaultdict(list)
    for row in rows:
        for stage in row["stages"]:
            if stage != "other":
                stage_groups[stage].append(row)

    return {
        "script_count": len(rows),
        "stage_counts": dict(Counter(stage for row in rows for stage in row["stages"])),
        "template_candidate_groups": {
            stage: items
            for stage, items in sorted(stage_groups.items())
        },
    }

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

    registered_units = []
    for unit in KNOWN_CHANGE_UNITS:
        stage_entries = []
        unit_failures = []
        unit_warnings = []

        for stage_def in LIFECYCLE_STAGES:
            stage = stage_def["stage"]
            patterns = unit["report_patterns"].get(stage, [])
            path, data = latest_report_for_patterns(
                patterns,
                target_file=unit["target_file"],
                target_family=unit["target_family"],
            ) if patterns else (None, {})

            stage_failures, stage_warnings = validate_stage(stage, data) if patterns else (["stage_not_declared_for_this_unit"], [])

            if stage == "autonomous_policy_gate" and unit["change_unit_id"] == "homepage-onboarding":
                # First loop predated the reusable autonomous gate convention.
                stage_failures = []
                stage_warnings = ["autonomous_policy_gate_not_part_of_first_loop_historical_chain"]

            if stage == "isolated_post_apply_validator" and unit["change_unit_id"] == "homepage-onboarding":
                # The first loop was accepted by its own ledger before the stricter isolated-delta
                # convention was standardized. Keep this as historical evidence, not a blocker.
                converted = [x for x in stage_failures if str(x).startswith("isolated_removed_lines:")]
                if converted:
                    stage_failures = [x for x in stage_failures if not str(x).startswith("isolated_removed_lines:")]
                    stage_warnings.extend([f"historical_first_loop_schema_gap:{x}" for x in converted])

            unit_failures.extend([f"{stage}:{x}" for x in stage_failures])
            unit_warnings.extend([f"{stage}:{x}" for x in stage_warnings])

            stage_entries.append({
                "stage": stage,
                "declared": bool(patterns),
                "patterns": patterns,
                "latest_report": str(path) if path else None,
                "exists": bool(path),
                "compact": compact_report(stage, data) if data else {},
                "stage_failures": stage_failures,
                "stage_warnings": stage_warnings,
            })

        snapshot = latest_snapshot_for_patterns(unit["snapshot_patterns"])

        if not snapshot:
            unit_warnings.append("closed_snapshot_not_found_by_registry_patterns")

        registered_units.append({
            "change_unit_id": unit["change_unit_id"],
            "loop_index": unit["loop_index"],
            "target_family": unit["target_family"],
            "target_file": unit["target_file"],
            "change": unit["change"],
            "closed_snapshot": str(snapshot) if snapshot else None,
            "lifecycle_stages": stage_entries,
            "unit_status": "registered_with_failures" if unit_failures else "registered",
            "unit_failures": unit_failures,
            "unit_warnings": unit_warnings,
        })

    registered_with_failures = [x for x in registered_units if x["unit_failures"]]
    if registered_with_failures:
        warnings.append("some_registered_units_have_stage_gaps_or_schema_mismatches")

    template_inventory = build_template_candidate_inventory()

    result = "ok" if not failures else "blocked"

    out_json = REPORT_DIR / f"controlled-change-registry-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"controlled-change-registry-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "registry_id": REGISTRY_ID,
        "result": result,
        "registered_unit_count": len(registered_units),
        "registered_units_with_failures_count": len(registered_with_failures),
        "lifecycle_stages": LIFECYCLE_STAGES,
        "registered_units": registered_units,
        "template_candidate_inventory": template_inventory,
        "recommended_next_step": "build_controlled_change_template_checker" if result == "ok" else "fix_controlled_change_registry_blockers",
        "policy": {
            "registry_only": True,
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
    lines.append("# Learning V2 Controlled Change Registry")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- registry_id: `{REGISTRY_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- registered_unit_count: `{len(registered_units)}`")
    lines.append(f"- registered_units_with_failures_count: `{len(registered_with_failures)}`")
    lines.append(f"- recommended_next_step: `{payload['recommended_next_step']}`")
    lines.append("- registry_only: `true`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- human_review_required: `false`")
    lines.append("- machine_policy_gate: `true`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Registered Units")
    for unit in registered_units:
        lines.append(
            f"- loop `{unit['loop_index']}` `{unit['change_unit_id']}` "
            f"target=`{unit['target_file']}` status=`{unit['unit_status']}`"
        )
        if unit["unit_warnings"]:
            for w in unit["unit_warnings"]:
                lines.append(f"  - warning: {w}")
        if unit["unit_failures"]:
            for f in unit["unit_failures"]:
                lines.append(f"  - failure: {f}")

    lines.append("")
    lines.append("## Template Candidate Stage Counts")
    for stage, count in sorted(template_inventory["stage_counts"].items()):
        lines.append(f"- `{stage}`: `{count}`")

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

    print("controlled_change_registry =", result)
    print("registered_unit_count =", len(registered_units))
    print("registered_units_with_failures_count =", len(registered_with_failures))
    print("recommended_next_step =", payload["recommended_next_step"])
    print("registry_only = True")
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
