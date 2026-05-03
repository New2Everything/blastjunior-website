#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

READINESS_ID = "learning-v2-gallery-next-action-gate-readiness-v0"
TARGET_FILE = "public/gallery.html"

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
    reports = sorted(REPORT_DIR.glob(pattern))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    gate_path, gate = latest_report("autonomous-change-policy-gate-*.json")
    dry_path, dry = latest_report("gallery-next-action-source-change-dry-run-*.json")

    failures = []
    warnings = []

    gate_summary = integrity.get("gate_summary") or {}
    business_freeze_stable = (
        integrity.get("business_freeze_stable")
        if integrity.get("business_freeze_stable") is not None
        else gate_summary.get("business_freeze_stable")
    )

    dry_policy = dry.get("policy") or {}
    dry_source_written = (
        dry.get("source_written")
        if dry.get("source_written") is not None
        else dry_policy.get("source_written")
    )

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if integrity.get("drift_count") != 0:
        failures.append(f"drift_count_not_zero:{integrity.get('drift_count')}")

    if business_freeze_stable is not True:
        failures.append(f"business_freeze_not_stable:{business_freeze_stable}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if not gate_path:
        failures.append("missing_autonomous_change_policy_gate")

    if gate.get("result") != "ok":
        failures.append(f"autonomous_gate_not_ok:{gate.get('result')}")

    if gate.get("autonomous_decision") != "allow_next_dry_apply_gate":
        failures.append(f"autonomous_gate_decision_not_allow:{gate.get('autonomous_decision')}")

    if gate.get("decision_basis", {}).get("human_review_required") is not False:
        failures.append("autonomous_gate_requires_human_review")

    if not dry_path:
        failures.append("missing_gallery_dry_run_report")

    if dry.get("result") != "ok":
        failures.append(f"gallery_dry_run_not_ok:{dry.get('result')}")

    if dry.get("target_file") != TARGET_FILE:
        failures.append(f"unexpected_dry_run_target:{dry.get('target_file')}")

    if dry.get("changed_in_dry_run") is not True:
        failures.append(f"gallery_dry_run_not_changed:{dry.get('changed_in_dry_run')}")

    if dry.get("already_present") is True:
        failures.append("gallery_next_action_already_present")

    if dry_source_written is not False:
        failures.append(f"dry_run_source_written_not_false:{dry_source_written}")

    if dry.get("diff_line_count", 0) <= 0:
        failures.append(f"empty_gallery_diff:{dry.get('diff_line_count')}")

    target = WORKSPACE / TARGET_FILE
    if not target.exists():
        failures.append(f"target_missing:{TARGET_FILE}")
    else:
        text = target.read_text(encoding="utf-8", errors="ignore")
        if "gallery-next-action" in text or "gallery-next-action-title" in text:
            failures.append("target_already_contains_gallery_next_action")

    ready = not failures

    payload = {
        "generated_at": now_iso(),
        "readiness_id": READINESS_ID,
        "result": "ok" if ready else "blocked",
        "target_file": TARGET_FILE,
        "autonomous_gate_report": str(gate_path) if gate_path else None,
        "dry_run_report": str(dry_path) if dry_path else None,
        "ready_to_open_source_change_gate": ready,
        "recommended_gate": {
            "allow_source_changes": True,
            "allow_git_commit": False,
            "allow_deploy": False,
            "single_target_file": TARGET_FILE,
            "single_change_executor": "learning-v2-gallery-next-action-source-change-apply.py",
            "must_backup_before_write": True,
            "must_run_post_apply_validation": True,
            "must_run_isolated_backup_validation": True,
            "must_run_controlled_ledger_acceptance": True,
            "must_run_system_integrity": True,
            "human_review_required": False,
            "machine_policy_gate": True
        },
        "policy": {
            "state_written": False,
            "source_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "readiness_only": True
        },
        "warnings": warnings,
        "failures": failures
    }

    out_json = REPORT_DIR / f"gallery-next-action-gate-readiness-{stamp()}.json"
    out_md = REPORT_DIR / f"gallery-next-action-gate-readiness-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Gallery Next Action Gate Readiness")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- readiness_id: `{READINESS_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- target_file: `{TARGET_FILE}`")
    lines.append(f"- ready_to_open_source_change_gate: `{str(ready).lower()}`")
    lines.append("- human_review_required: `false`")
    lines.append("- machine_policy_gate: `true`")
    lines.append("- source_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Recommended gate")
    lines.append("")
    for k, v in payload["recommended_gate"].items():
        lines.append(f"- {k}: `{v}`")
    if failures:
        lines.append("")
        lines.append("## Failures")
        for f in failures:
            lines.append(f"- {f}")
    if warnings:
        lines.append("")
        lines.append("## Warnings")
        for w in warnings:
            lines.append(f"- {w}")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("gallery_next_action_gate_readiness =", payload["result"])
    print("readiness_id =", READINESS_ID)
    print("target_file =", TARGET_FILE)
    print("autonomous_gate_report =", gate_path)
    print("dry_run_report =", dry_path)
    print("readiness_json =", out_json)
    print("readiness_md =", out_md)
    print("ready_to_open_source_change_gate =", str(ready).lower())
    print("allow_source_changes_recommended = true")
    print("allow_git_commit_recommended = false")
    print("allow_deploy_recommended = false")
    print("human_review_required = false")
    print("machine_policy_gate = true")
    print("state_written = false")
    print("source_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

    if warnings:
        print()
        print("warnings:")
        for w in warnings:
            print(" ", w)

if __name__ == "__main__":
    main()
