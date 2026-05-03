#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

GATE_ID = "learning-v2-autonomous-change-policy-gate-v0"

LOW_RISK_ALLOWED_FILES = {
    "public/gallery.html",
    "public/index.html",
}

BLOCKED_TARGETS = [
    "components/nav.html",
    "components/nav.css",
    "workers/",
    "functions/",
    "src/",
    "api/",
    "wrangler.toml",
    "package.json",
    "package-lock.json",
]

BLOCKED_DIFF_MARKERS = [
    "fetch(",
    "addEventListener",
    "localStorage",
    "blxst_token",
    "D1",
    "KV",
    "R2",
    "wrangler",
    "Worker",
    "login",
    "logout",
    "register",
    "verify",
    "heartbeat",
    "online",
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
    reports = sorted(REPORT_DIR.glob(pattern))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    dry_path, dry = latest_report("gallery-next-action-source-change-dry-run-*.json")
    milestone = state.get("last_controlled_learning_source_change_closed") or {}

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

    target_file = dry.get("target_file")
    diff_preview = "\n".join(dry.get("diff_preview") or [])

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if integrity.get("drift_count") != 0:
        failures.append(f"drift_count_not_zero:{integrity.get('drift_count')}")

    if business_freeze_stable is not True:
        failures.append(f"business_freeze_not_stable:{business_freeze_stable}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_closed:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if milestone.get("target_file") != "public/index.html":
        failures.append("first_controlled_learning_source_change_not_closed")

    if not dry_path:
        failures.append("missing_gallery_dry_run_report")

    if dry.get("result") != "ok":
        failures.append(f"gallery_dry_run_not_ok:{dry.get('result')}")

    if dry_source_written is not False:
        failures.append(f"dry_run_claims_source_written:{dry_source_written}")

    if dry.get("changed_in_dry_run") is not True:
        failures.append(f"dry_run_not_changed:{dry.get('changed_in_dry_run')}")

    if target_file not in LOW_RISK_ALLOWED_FILES:
        failures.append(f"target_file_not_low_risk_allowed:{target_file}")

    for blocked in BLOCKED_TARGETS:
        if target_file and target_file.startswith(blocked):
            failures.append(f"target_file_blocked:{target_file}")

    if dry.get("already_present") is True:
        failures.append("target_block_already_present")

    if dry.get("diff_line_count", 0) <= 0:
        failures.append("empty_or_missing_diff")

    for marker in BLOCKED_DIFF_MARKERS:
        if marker.lower() in diff_preview.lower():
            failures.append(f"blocked_diff_marker_found:{marker}")

    if target_file == "public/gallery.html":
        if "gallery-next-action" not in diff_preview:
            failures.append("gallery_diff_missing_gallery_next_action_marker")
        if "/join.html" not in diff_preview:
            failures.append("gallery_diff_missing_join_link")
        if "fetch(" in diff_preview:
            failures.append("gallery_diff_touches_fetch_logic")

    autonomous_decision = "allow_next_dry_apply_gate" if not failures else "blocked"
    recommended_next_step = (
        "build_gallery_next_action_gate_readiness"
        if autonomous_decision == "allow_next_dry_apply_gate"
        else "stop_and_generate_autonomous_block_report"
    )

    payload = {
        "generated_at": now_iso(),
        "gate_id": GATE_ID,
        "result": "ok" if not failures else "blocked",
        "autonomous_decision": autonomous_decision,
        "recommended_next_step": recommended_next_step,
        "target_file": target_file,
        "dry_run_report": str(dry_path) if dry_path else None,
        "decision_basis": {
            "human_review_required": False,
            "machine_policy_gate": True,
            "single_target_file": target_file,
            "page_local_change": target_file in LOW_RISK_ALLOWED_FILES,
            "source_written": dry_source_written,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
        "policy": {
            "state_written": False,
            "source_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "autonomous_gate_only": True,
        },
        "warnings": warnings,
        "failures": failures,
    }

    out_json = REPORT_DIR / f"autonomous-change-policy-gate-{stamp()}.json"
    out_md = REPORT_DIR / f"autonomous-change-policy-gate-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Autonomous Change Policy Gate")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- gate_id: `{GATE_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- autonomous_decision: `{autonomous_decision}`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")
    lines.append(f"- target_file: `{target_file}`")
    lines.append("- human_review_required: `false`")
    lines.append("- machine_policy_gate: `true`")
    lines.append("- source_written: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    if failures:
        lines.append("")
        lines.append("## Failures")
        for f in failures:
            lines.append(f"- {f}")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("autonomous_change_policy_gate =", payload["result"])
    print("gate_id =", GATE_ID)
    print("target_file =", target_file)
    print("dry_run_report =", dry_path)
    print("autonomous_decision =", autonomous_decision)
    print("recommended_next_step =", recommended_next_step)
    print("human_review_required = false")
    print("machine_policy_gate = true")
    print("source_written = false")
    print("state_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("gate_json =", out_json)
    print("gate_md =", out_md)

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
