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

RESOLVER_ID = "learning-v2-fifth-loop-engagement-probe-resolver-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def latest_report(patterns):
    files = []
    for pattern in patterns:
        files.extend(REPORT_DIR.glob(pattern))
    files = sorted(set(files), key=lambda p: p.stat().st_mtime)
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
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    probe_path, probe = latest_report([
        "community-engagement-path-probe-*.json",
        "learning-v2-community-engagement-path-probe-*.json",
        "*engagement-path-probe*.json",
    ])
    planning_guard_path, planning_guard = latest_report(["fifth-loop-target-planning-guard-*.json"])
    duplication_path, duplication = latest_report(["controlled-change-duplication-guard-*.json"])
    readiness_path, readiness = latest_report(["next-loop-readiness-auditor-*.json"])
    integrity_path, integrity = latest_report(["system-integrity-*.json"])
    drift_path, drift = latest_report(["system-drift-audit-*.json"])

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
        ("engagement_path_probe", probe_path, probe),
        ("fifth_loop_target_planning_guard", planning_guard_path, planning_guard),
        ("duplication_guard", duplication_path, duplication),
        ("next_loop_readiness", readiness_path, readiness),
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

    if planning_guard.get("planning_status") != "family_available_but_no_concrete_target":
        failures.append(f"planning_status_unexpected:{planning_guard.get('planning_status')}")

    if probe.get("target_family") != "community.engagement_path":
        failures.append(f"probe_target_family_unexpected:{probe.get('target_family')}")

    for key in ["state_written", "business_source_written", "source_change_gate_opened", "git_commit", "git_push", "deploy"]:
        if key in probe and probe.get(key) is not False:
            failures.append(f"probe_{key}_not_false:{probe.get(key)}")

    findings = probe.get("findings") or []
    finding_count = probe.get("finding_count", len(findings))

    review_or_missing_findings = [
        x for x in findings
        if str(x.get("status")).lower() in ["review", "missing", "needs_review", "blocked"]
    ]

    high_or_medium_findings = [
        x for x in findings
        if str(x.get("severity")).lower() in ["high", "medium"]
    ]

    concrete_low_risk_targets = []
    for item in review_or_missing_findings:
        file_value = item.get("file")
        if file_value and "," not in str(file_value):
            concrete_low_risk_targets.append({
                "target_file": file_value,
                "dimension": item.get("dimension"),
                "severity": item.get("severity"),
                "recommendation": item.get("recommendation"),
            })

    if concrete_low_risk_targets:
        resolver_status = "concrete_target_found_for_planning_only"
        recommended_next_step = "run_next_target_selector_with_duplication_guard"
    elif review_or_missing_findings or high_or_medium_findings:
        resolver_status = "needs_human_review_or_expanded_probe"
        recommended_next_step = "build_expanded_engagement_probe_no_source_write"
    else:
        resolver_status = "no_concrete_target_from_probe"
        recommended_next_step = "pause_fifth_loop_and_write_handoff_summary"

    result = "ok" if not failures else "blocked"

    out_json = REPORT_DIR / f"fifth-loop-engagement-probe-resolver-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"fifth-loop-engagement-probe-resolver-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "resolver_id": RESOLVER_ID,
        "result": result,
        "resolver_status": resolver_status if result == "ok" else "blocked",
        "target_family": "community.engagement_path",
        "finding_count": finding_count,
        "review_or_missing_count": len(review_or_missing_findings),
        "high_or_medium_count": len(high_or_medium_findings),
        "concrete_low_risk_target_count": len(concrete_low_risk_targets),
        "concrete_low_risk_targets": concrete_low_risk_targets,
        "probe_report": str(probe_path) if probe_path else None,
        "planning_guard_report": str(planning_guard_path) if planning_guard_path else None,
        "duplication_guard_report": str(duplication_path) if duplication_path else None,
        "next_loop_readiness_report": str(readiness_path) if readiness_path else None,
        "integrity_report": str(integrity_path) if integrity_path else None,
        "source_written": False,
        "metadata_written": False,
        "state_written": False,
        "business_source_written": False,
        "source_change_gate_opened": False,
        "fifth_loop_started": False,
        "human_review_required": False,
        "machine_policy_gate": True,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "recommended_next_step": recommended_next_step if result == "ok" else "fix_fifth_loop_engagement_probe_resolver_blockers",
        "warnings": warnings,
        "failures": failures,
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Fifth Loop Engagement Probe Resolver")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- resolver_id: `{RESOLVER_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- resolver_status: `{payload['resolver_status']}`")
    lines.append(f"- finding_count: `{finding_count}`")
    lines.append(f"- review_or_missing_count: `{len(review_or_missing_findings)}`")
    lines.append(f"- high_or_medium_count: `{len(high_or_medium_findings)}`")
    lines.append(f"- concrete_low_risk_target_count: `{len(concrete_low_risk_targets)}`")
    lines.append(f"- recommended_next_step: `{payload['recommended_next_step']}`")
    lines.append("- source_written: `false`")
    lines.append("- metadata_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- fifth_loop_started: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")

    if concrete_low_risk_targets:
        lines.append("")
        lines.append("## Concrete Low-Risk Targets")
        for item in concrete_low_risk_targets:
            lines.append(f"- `{item}`")

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

    print("fifth_loop_engagement_probe_resolver =", result)
    print("resolver_status =", payload["resolver_status"])
    print("finding_count =", finding_count)
    print("review_or_missing_count =", len(review_or_missing_findings))
    print("high_or_medium_count =", len(high_or_medium_findings))
    print("concrete_low_risk_target_count =", len(concrete_low_risk_targets))
    print("concrete_low_risk_targets =", json.dumps(concrete_low_risk_targets, ensure_ascii=False, indent=2))
    print("source_written = False")
    print("metadata_written = False")
    print("state_written = False")
    print("business_source_written = False")
    print("source_change_gate_opened = False")
    print("fifth_loop_started = False")
    print("human_review_required = False")
    print("machine_policy_gate = True")
    print("git_commit = False")
    print("git_push = False")
    print("deploy = False")
    print("recommended_next_step =", payload["recommended_next_step"])
    print("report_json =", out_json)
    print("report_md =", out_md)

    if warnings:
        print("warnings =", json.dumps(warnings, ensure_ascii=False))
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
