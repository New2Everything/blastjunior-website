#!/usr/bin/env python3
import argparse
import json
from copy import deepcopy
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

PROMOTION_ID = "learning-v2-public-about-create-file-metadata-stage-promotion-v0"

TARGET_CANDIDATE_ID = "deferred-public-about-page"
TARGET_FAMILY = "community.engagement_path"
TARGET_FILE = "public/about.html"
METADATA_PATH = CREATE_FILE_METADATA_DIR / "public-about-create-file-v0.json"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="promote metadata allowed_stage to dry_run_only")
    args = ap.parse_args()

    run_stamp = stamp()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    metadata_apply_path, metadata_apply = latest_report("public-about-create-file-metadata-draft-apply-*.json")
    template_validator_path, template_validator = latest_report("controlled-change-new-file-template-validator-*.json")
    readiness_path, readiness = latest_report("create-file-metadata-draft-readiness-*.json")
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
        ("metadata_draft_apply", metadata_apply_path, metadata_apply),
        ("new_file_template_validator", template_validator_path, template_validator),
        ("metadata_draft_readiness", readiness_path, readiness),
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

    if metadata_apply.get("metadata_written") is not True:
        failures.append(f"metadata_apply_metadata_written_not_true:{metadata_apply.get('metadata_written')}")

    if metadata_apply.get("source_written") is not False:
        failures.append(f"metadata_apply_source_written_not_false:{metadata_apply.get('source_written')}")

    if not METADATA_PATH.exists():
        failures.append(f"metadata_file_missing:{METADATA_PATH}")

    if (WORKSPACE / TARGET_FILE).exists():
        failures.append(f"target_file_already_exists:{TARGET_FILE}")

    metadata = load_json(METADATA_PATH, default={})
    promoted = deepcopy(metadata)

    if metadata:
        if metadata.get("target_candidate_id") != TARGET_CANDIDATE_ID:
            failures.append(f"target_candidate_id_unexpected:{metadata.get('target_candidate_id')}")

        if metadata.get("target_family") != TARGET_FAMILY:
            failures.append(f"target_family_unexpected:{metadata.get('target_family')}")

        if metadata.get("target_file") != TARGET_FILE:
            failures.append(f"target_file_unexpected:{metadata.get('target_file')}")

        if metadata.get("change_type") != "create_file_from_template":
            failures.append(f"change_type_unexpected:{metadata.get('change_type')}")

        if metadata.get("allowed_stage") != "metadata_draft_only":
            failures.append(f"allowed_stage_not_metadata_draft_only:{metadata.get('allowed_stage')}")

        promoted["allowed_stage"] = "dry_run_only"
        promoted["stage_promoted_at"] = now_iso()
        promoted["stage_promotion_id"] = PROMOTION_ID
        promoted["stage_promotion_reason"] = "Template validator passed; allow generic create-file dry-run runner to consume metadata."

        safety = promoted.get("safety") or {}
        for key in ["git_commit", "git_push", "deploy"]:
            if safety.get(key) is not False:
                failures.append(f"safety_{key}_not_false:{safety.get(key)}")

    metadata_written = False
    written_metadata_path = None

    if args.apply and not failures:
        save_json(METADATA_PATH, promoted)
        metadata_written = True
        written_metadata_path = str(METADATA_PATH)

    result = "ok" if not failures else "blocked"

    recommended_next_step = (
        "run_generic_create_file_dry_run_runner_for_public_about"
        if metadata_written
        else "apply_public_about_metadata_stage_promotion_to_dry_run_only"
        if result == "ok"
        else "fix_public_about_metadata_stage_promotion_blockers"
    )

    out_json = REPORT_DIR / f"public-about-create-file-metadata-stage-promotion-{'apply' if args.apply else 'dry-run'}-{run_stamp}.json"
    out_md = SNAPSHOT_DIR / f"public-about-create-file-metadata-stage-promotion-{'apply' if args.apply else 'dry-run'}-{run_stamp}.md"
    preview_json = SNAPSHOT_DIR / f"public-about-create-file-metadata-stage-promotion-preview-{run_stamp}.json"

    save_json(preview_json, promoted)

    payload = {
        "generated_at": now_iso(),
        "promotion_id": PROMOTION_ID,
        "result": result,
        "apply": args.apply,
        "promotion_mode": "metadata_stage_promotion_apply" if args.apply else "metadata_stage_promotion_preview_only",
        "target_candidate_id": TARGET_CANDIDATE_ID,
        "target_family": TARGET_FAMILY,
        "target_file": TARGET_FILE,
        "target_file_exists": (WORKSPACE / TARGET_FILE).exists(),
        "metadata_path": str(METADATA_PATH),
        "metadata_preview_path": str(preview_json),
        "from_allowed_stage": metadata.get("allowed_stage"),
        "to_allowed_stage": promoted.get("allowed_stage"),
        "metadata_written": metadata_written,
        "written_metadata_path": written_metadata_path,
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
        "metadata_draft_apply_report": str(metadata_apply_path) if metadata_apply_path else None,
        "new_file_template_validator_report": str(template_validator_path) if template_validator_path else None,
        "metadata_draft_readiness_report": str(readiness_path) if readiness_path else None,
        "integrity_report": str(integrity_path) if integrity_path else None,
        "recommended_next_step": recommended_next_step,
        "policy": {
            "metadata_stage_promotion_only": True,
            "metadata_written": metadata_written,
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

    save_json(out_json, payload)

    lines = []
    lines.append("# Learning V2 Public About Create File Metadata Stage Promotion")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- promotion_id: `{PROMOTION_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- apply: `{str(args.apply).lower()}`")
    lines.append(f"- promotion_mode: `{payload['promotion_mode']}`")
    lines.append(f"- target_file: `{TARGET_FILE}`")
    lines.append(f"- target_file_exists: `{str(payload['target_file_exists']).lower()}`")
    lines.append(f"- from_allowed_stage: `{payload['from_allowed_stage']}`")
    lines.append(f"- to_allowed_stage: `{payload['to_allowed_stage']}`")
    lines.append(f"- metadata_written: `{str(metadata_written).lower()}`")
    lines.append("- source_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- fourth_loop_started: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")

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

    print("public_about_create_file_metadata_stage_promotion =", result)
    print("apply =", args.apply)
    print("promotion_mode =", payload["promotion_mode"])
    print("target_file =", TARGET_FILE)
    print("target_file_exists =", payload["target_file_exists"])
    print("metadata_path =", METADATA_PATH)
    print("metadata_preview_path =", preview_json)
    print("from_allowed_stage =", payload["from_allowed_stage"])
    print("to_allowed_stage =", payload["to_allowed_stage"])
    print("metadata_written =", metadata_written)
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
