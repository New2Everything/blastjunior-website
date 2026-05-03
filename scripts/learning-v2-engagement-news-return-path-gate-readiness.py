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

READINESS_ID = "learning-v2-engagement-news-return-path-gate-readiness-v0"
TARGET_FAMILY = "community.engagement_path"
TARGET_FILE = "public/news.html"
CHANGE_PLAN_ID = "controlled-change-engagement-news-return-path-cta-v0"

REQUIRED_MARKERS = [
    "news-engagement-return-path",
    "news-engagement-return-path-title",
    "看完俱乐部动态",
    "下一步可以很简单",
    "看看 HADO 精彩瞬间",
    "回到首页了解如何开始",
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

def latest_integrity_report():
    reports = sorted(REPORT_DIR.glob("system-integrity-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    dry_path, dry = latest_report("engagement-news-return-path-source-change-dry-run-*.json")
    gate_path, gate = latest_report("engagement-news-return-path-autonomous-policy-gate-*.json")
    plan_path, plan = latest_report("community-engagement-path-controlled-source-change-plan-*.json")
    integrity_path, integrity = latest_integrity_report()

    failures = []
    warnings = []

    target_path = WORKSPACE / TARGET_FILE
    current_text = target_path.read_text(encoding="utf-8", errors="ignore") if target_path.exists() else ""

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

    if not integrity_path:
        failures.append("missing_latest_system_integrity_report")
    elif integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if not plan_path:
        failures.append("missing_controlled_source_change_plan")
    elif plan.get("result") != "ok":
        failures.append(f"controlled_source_change_plan_not_ok:{plan.get('result')}")

    recommended = plan.get("recommended_first_change") or {}
    if recommended.get("change_plan_id") != CHANGE_PLAN_ID:
        failures.append(f"recommended_change_plan_id_mismatch:{recommended.get('change_plan_id')}")

    if recommended.get("target_file") != TARGET_FILE:
        failures.append(f"recommended_target_file_mismatch:{recommended.get('target_file')}")

    if recommended.get("risk") != "low":
        failures.append(f"recommended_risk_not_low:{recommended.get('risk')}")

    if not dry_path:
        failures.append("missing_engagement_news_return_path_dry_run_report")
    elif dry.get("result") != "ok":
        failures.append(f"dry_run_not_ok:{dry.get('result')}")

    if dry.get("target_family") != TARGET_FAMILY:
        failures.append(f"dry_run_target_family_mismatch:{dry.get('target_family')}")

    if dry.get("target_file") != TARGET_FILE:
        failures.append(f"dry_run_target_file_mismatch:{dry.get('target_file')}")

    if dry.get("change_plan_id") != CHANGE_PLAN_ID:
        failures.append(f"dry_run_change_plan_id_mismatch:{dry.get('change_plan_id')}")

    if dry.get("changed_in_dry_run") is not True:
        failures.append(f"dry_run_changed_in_dry_run_not_true:{dry.get('changed_in_dry_run')}")

    if dry.get("source_written") is not False:
        failures.append(f"dry_run_source_written_not_false:{dry.get('source_written')}")

    if dry.get("state_written") is not False:
        failures.append(f"dry_run_state_written_not_false:{dry.get('state_written')}")

    if dry.get("business_source_written") is not False:
        failures.append(f"dry_run_business_source_written_not_false:{dry.get('business_source_written')}")

    if dry.get("removed_line_count") != 0:
        failures.append(f"dry_run_removed_line_count_not_zero:{dry.get('removed_line_count')}")

    if dry.get("added_line_count", 999) > 20:
        failures.append(f"dry_run_added_line_count_too_large:{dry.get('added_line_count')}")

    if dry.get("proposed_contains_required_markers") is not True:
        failures.append(f"dry_run_required_markers_not_true:{dry.get('proposed_contains_required_markers')}")

    if not gate_path:
        failures.append("missing_engagement_autonomous_policy_gate_report")
    elif gate.get("result") != "ok":
        failures.append(f"autonomous_gate_not_ok:{gate.get('result')}")

    if gate.get("autonomous_decision") != "allow_next_dry_apply_gate":
        failures.append(f"autonomous_decision_not_allow:{gate.get('autonomous_decision')}")

    if gate.get("target_file") != TARGET_FILE:
        failures.append(f"autonomous_gate_target_file_mismatch:{gate.get('target_file')}")

    if gate.get("target_family") != TARGET_FAMILY:
        failures.append(f"autonomous_gate_target_family_mismatch:{gate.get('target_family')}")

    if not target_path.exists():
        failures.append(f"target_file_missing:{TARGET_FILE}")

    if "news-engagement-return-path" in current_text:
        failures.append("target_already_contains_news_engagement_return_path")

    if "const API =" not in current_text:
        warnings.append("target_api_constant_not_found_unexpectedly")

    ready_to_open_source_change_gate = not failures

    result = "ok" if not failures else "blocked"
    recommended_next_step = (
        "build_engagement_news_return_path_apply_executor"
        if ready_to_open_source_change_gate
        else "fix_engagement_news_return_path_gate_readiness_blockers"
    )

    out_json = REPORT_DIR / f"engagement-news-return-path-gate-readiness-{stamp()}.json"
    out_md = REPORT_DIR / f"engagement-news-return-path-gate-readiness-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "readiness_id": READINESS_ID,
        "result": result,
        "target_family": TARGET_FAMILY,
        "target_file": TARGET_FILE,
        "change_plan_id": CHANGE_PLAN_ID,
        "controlled_source_change_plan": str(plan_path) if plan_path else None,
        "dry_run_report": str(dry_path) if dry_path else None,
        "autonomous_policy_gate": str(gate_path) if gate_path else None,
        "integrity_report": str(integrity_path) if integrity_path else None,
        "ready_to_open_source_change_gate": ready_to_open_source_change_gate,
        "recommended_next_step": recommended_next_step,
        "required_markers": REQUIRED_MARKERS,
        "policy": {
            "readiness_only": True,
            "state_written": False,
            "source_written": False,
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
    lines.append("# Learning V2 Engagement News Return Path Gate Readiness")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- readiness_id: `{READINESS_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- target_file: `{TARGET_FILE}`")
    lines.append(f"- ready_to_open_source_change_gate: `{str(ready_to_open_source_change_gate).lower()}`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")
    lines.append("- readiness_only: `true`")
    lines.append("- source_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- human_review_required: `false`")
    lines.append("- machine_policy_gate: `true`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
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

    print("engagement_news_return_path_gate_readiness =", result)
    print("target_family =", TARGET_FAMILY)
    print("target_file =", TARGET_FILE)
    print("ready_to_open_source_change_gate =", ready_to_open_source_change_gate)
    print("recommended_next_step =", recommended_next_step)
    print("readiness_only = True")
    print("source_written = False")
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

    if failures:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
