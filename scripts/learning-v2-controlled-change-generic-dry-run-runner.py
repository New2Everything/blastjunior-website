#!/usr/bin/env python3
import difflib
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

RUNNER_ID = "learning-v2-controlled-change-generic-dry-run-runner-v0"

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

def validate_basic_metadata(meta):
    failures = []
    warnings = []

    required = [
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

    for key in required:
        if key not in meta:
            failures.append(f"missing_required_key:{key}")

    if meta.get("risk") != "low":
        failures.append(f"risk_not_low:{meta.get('risk')}")

    if meta.get("allowed_stage") not in ["dry_run_only"]:
        failures.append(f"allowed_stage_not_dry_run_only:{meta.get('allowed_stage')}")

    safety = meta.get("safety") or {}
    if safety.get("git_commit") is not False:
        failures.append(f"safety_git_commit_not_false:{safety.get('git_commit')}")
    if safety.get("git_push") is not False:
        failures.append(f"safety_git_push_not_false:{safety.get('git_push')}")
    if safety.get("deploy") is not False:
        failures.append(f"safety_deploy_not_false:{safety.get('deploy')}")
    if safety.get("allow_removed_lines") is not False:
        failures.append(f"safety_allow_removed_lines_not_false:{safety.get('allow_removed_lines')}")

    insertion = meta.get("insertion") or {}
    if insertion.get("mode") != "insert_after_anchor_once":
        failures.append(f"unsupported_insertion_mode:{insertion.get('mode')}")

    target_file = meta.get("target_file")
    forbidden = [str(x).lstrip("./") for x in safety.get("forbidden_target_files") or []]
    if target_file and str(target_file).lstrip("./") in forbidden:
        failures.append(f"target_file_forbidden:{target_file}")

    return failures, warnings

def dry_run_one(meta_path, meta):
    failures, warnings = validate_basic_metadata(meta)

    change_unit_id = meta.get("change_unit_id")
    target_family = meta.get("target_family")
    target_file = meta.get("target_file")
    target_path = WORKSPACE / target_file if target_file else None

    insertion = meta.get("insertion") or {}
    markers = meta.get("markers") or {}
    safety = meta.get("safety") or {}
    acceptance = meta.get("acceptance") or {}

    anchor = insertion.get("anchor") or ""
    block = insertion.get("block") or ""
    primary_marker = markers.get("primary_marker")
    title_marker = markers.get("title_marker")
    required_markers = acceptance.get("required_markers") or markers.get("required_text_markers") or []

    original = ""

    if not target_file:
        failures.append("target_file_missing")
    elif not target_path.exists():
        failures.append(f"target_file_does_not_exist:{target_file}")
    elif not target_path.is_file():
        failures.append(f"target_path_not_file:{target_file}")
    else:
        original = target_path.read_text(encoding="utf-8", errors="ignore")

    if original:
        if primary_marker and primary_marker in original:
            failures.append(f"primary_marker_already_present:{primary_marker}")

        if anchor not in original:
            failures.append("insertion_anchor_not_found")

    if block:
        for marker in safety.get("blocked_added_markers") or []:
            if marker.lower() in block.lower():
                failures.append(f"blocked_added_marker_in_block:{marker}")
    else:
        failures.append("insertion_block_empty")

    proposed = original
    changed_in_dry_run = False

    if not failures:
        proposed = original.replace(anchor, anchor + block, 1)
        changed_in_dry_run = proposed != original

        if not changed_in_dry_run:
            failures.append("proposed_no_change")

        for marker in required_markers:
            if marker not in proposed:
                failures.append(f"proposed_missing_required_marker:{marker}")

        if primary_marker:
            count = proposed.count(primary_marker)
            if count != 1:
                failures.append(f"primary_marker_count_not_one:{count}")

        if title_marker:
            count = proposed.count(title_marker)
            if count != 1:
                failures.append(f"title_marker_count_not_one:{count}")

    diff_lines = list(difflib.unified_diff(
        original.splitlines(),
        proposed.splitlines(),
        fromfile=f"{target_file}:before",
        tofile=f"{target_file}:after-generic-dry-run",
        lineterm="",
    ))

    added_line_count = len([x for x in diff_lines if x.startswith("+") and not x.startswith("+++")])
    removed_line_count = len([x for x in diff_lines if x.startswith("-") and not x.startswith("---")])

    if removed_line_count != 0:
        failures.append(f"removed_line_count_not_zero:{removed_line_count}")

    max_added = safety.get("max_added_lines")
    if isinstance(max_added, int) and added_line_count > max_added:
        failures.append(f"added_line_count_exceeds_max:{added_line_count}>{max_added}")

    result = "ok" if not failures else "blocked"

    run_stamp = stamp()
    safe_id = str(change_unit_id or meta_path.stem).replace("/", "-")
    out_json = REPORT_DIR / f"generic-dry-run-{safe_id}-{run_stamp}.json"
    out_diff = REPORT_DIR / f"generic-dry-run-{safe_id}-{run_stamp}.diff"

    payload = {
        "generated_at": now_iso(),
        "runner_id": RUNNER_ID,
        "result": result,
        "metadata_file": str(meta_path),
        "change_unit_id": change_unit_id,
        "target_family": target_family,
        "target_file": target_file,
        "changed_in_dry_run": changed_in_dry_run,
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
        "added_line_count": added_line_count,
        "removed_line_count": removed_line_count,
        "diff_path": str(out_diff),
        "recommended_next_step": "build_controlled_change_generic_policy_gate" if result == "ok" else "fix_generic_dry_run_metadata_or_anchor",
        "warnings": warnings,
        "failures": failures,
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_diff.write_text("\n".join(diff_lines) + "\n", encoding="utf-8")

    return payload

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    metadata_validator_path, metadata_validator = latest_report("controlled-change-lifecycle-metadata-validator-*.json")
    readiness_path, readiness = latest_report("next-loop-readiness-auditor-*.json")

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

    if not metadata_validator_path:
        failures.append("missing_lifecycle_metadata_validator_report")
    elif metadata_validator.get("result") != "ok":
        failures.append(f"metadata_validator_not_ok:{metadata_validator.get('result')}")

    if not readiness_path:
        failures.append("missing_next_loop_readiness_auditor_report")
    elif readiness.get("result") != "ok":
        failures.append(f"next_loop_readiness_not_ok:{readiness.get('result')}")

    if readiness.get("fourth_loop_allowed_now") is not False:
        failures.append(f"fourth_loop_allowed_unexpected:{readiness.get('fourth_loop_allowed_now')}")

    metadata_files = sorted(METADATA_DIR.glob("*.json"))
    dry_run_results = []

    if not failures:
        for meta_path in metadata_files:
            meta = load_json(meta_path, default={})
            dry_run_results.append(dry_run_one(meta_path, meta))

    blocked_results = [x for x in dry_run_results if x.get("result") != "ok"]

    result = "ok" if not failures and not blocked_results else "blocked"

    recommended_next_step = (
        "build_controlled_change_generic_policy_gate"
        if result == "ok"
        else "fix_controlled_change_generic_dry_run_runner_blockers"
    )

    out_json = REPORT_DIR / f"controlled-change-generic-dry-run-runner-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"controlled-change-generic-dry-run-runner-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "runner_id": RUNNER_ID,
        "result": result,
        "metadata_file_count": len(metadata_files),
        "dry_run_result_count": len(dry_run_results),
        "blocked_dry_run_count": len(blocked_results),
        "dry_run_results": dry_run_results,
        "metadata_validator_report": str(metadata_validator_path) if metadata_validator_path else None,
        "next_loop_readiness_auditor": str(readiness_path) if readiness_path else None,
        "recommended_next_step": recommended_next_step,
        "policy": {
            "runner_only": True,
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
        "failures": failures + [f"blocked_dry_run:{x.get('metadata_file')}" for x in blocked_results],
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Controlled Change Generic Dry Run Runner")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- runner_id: `{RUNNER_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- metadata_file_count: `{len(metadata_files)}`")
    lines.append(f"- dry_run_result_count: `{len(dry_run_results)}`")
    lines.append(f"- blocked_dry_run_count: `{len(blocked_results)}`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")
    lines.append("- runner_only: `true`")
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
    lines.append("## Dry Run Results")
    if dry_run_results:
        for item in dry_run_results:
            lines.append(
                f"- `{item.get('change_unit_id')}` target=`{item.get('target_file')}` "
                f"result=`{item.get('result')}` added=`{item.get('added_line_count')}` removed=`{item.get('removed_line_count')}`"
            )
    else:
        lines.append("- none; no controlled-change metadata files yet")

    if warnings:
        lines.append("")
        lines.append("## Warnings")
        for w in warnings:
            lines.append(f"- {w}")

    if payload["failures"]:
        lines.append("")
        lines.append("## Failures")
        for f in payload["failures"]:
            lines.append(f"- {f}")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("controlled_change_generic_dry_run_runner =", result)
    print("metadata_file_count =", len(metadata_files))
    print("dry_run_result_count =", len(dry_run_results))
    print("blocked_dry_run_count =", len(blocked_results))
    print("recommended_next_step =", recommended_next_step)
    print("runner_only = True")
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
    if payload["failures"]:
        print("failures =", json.dumps(payload["failures"], ensure_ascii=False, indent=2))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
