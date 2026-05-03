#!/usr/bin/env python3
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FAMILY = "community.onboarding_experience"
RESOLVER_ID = "learning-v2-community-onboarding-probe-resolver-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def latest_probe_report():
    reports = sorted(REPORT_DIR.glob("community-onboarding-experience-probe-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    probe_path, probe = latest_probe_report()
    findings = probe.get("findings") or []

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if not probe_path:
        failures.append("missing_community_onboarding_probe_report")

    if probe.get("result") != "ok":
        failures.append(f"probe_result_not_ok:{probe.get('result')}")

    status_counts = Counter(f.get("status") for f in findings)
    severity_counts = Counter(f.get("severity") for f in findings)
    dimension_counts = Counter(f.get("dimension") for f in findings if f.get("status") in ("review", "missing"))
    file_counts = Counter(f.get("file") for f in findings if f.get("status") in ("review", "missing"))

    high_or_medium = [
        f for f in findings
        if f.get("severity") in ("high", "medium")
    ]

    review_or_missing = [
        f for f in findings
        if f.get("status") in ("review", "missing")
    ]

    grouped = defaultdict(list)
    for f in review_or_missing:
        grouped[f.get("file")].append(f)

    if failures:
        decision = "blocked"
        next_step = "fix_resolver_or_probe_failures"
    elif high_or_medium:
        decision = "proposal_ready"
        next_step = "build_community_onboarding_proposal_planner"
    elif review_or_missing:
        decision = "review_ready"
        next_step = "human_review_or_low_risk_proposal_planner"
    else:
        decision = "no_action_needed"
        next_step = "mark_target_family_complete_or_monitor"

    prioritized_findings = sorted(
        review_or_missing,
        key=lambda x: (
            {"high": 0, "medium": 1, "low": 2}.get(x.get("severity"), 3),
            x.get("file") or "",
            x.get("dimension") or "",
        )
    )

    payload = {
        "generated_at": now_iso(),
        "resolver_id": RESOLVER_ID,
        "result": "ok" if not failures else "blocked",
        "target_family": TARGET_FAMILY,
        "probe_report": str(probe_path) if probe_path else None,
        "finding_count": len(findings),
        "review_or_missing_count": len(review_or_missing),
        "high_or_medium_count": len(high_or_medium),
        "status_counts": dict(status_counts),
        "severity_counts": dict(severity_counts),
        "dimension_counts": dict(dimension_counts),
        "file_counts": dict(file_counts),
        "decision": decision,
        "next_step": next_step,
        "prioritized_findings": prioritized_findings,
        "recommended_scope": {
            "must_not_change_source_now": True,
            "proposal_should_focus_on": [
                "homepage onboarding sequence",
                "clear first successful action",
                "parent/player motivation to next step",
                "gallery page next action",
                "missing or absent about page handling"
            ],
            "source_change_allowed_now": False
        },
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "resolver_only": True
        },
        "failures": failures
    }

    out_json = REPORT_DIR / f"community-onboarding-probe-resolver-{stamp()}.json"
    out_md = REPORT_DIR / f"community-onboarding-probe-resolver-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Community Onboarding Probe Resolver")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- resolver_id: `{RESOLVER_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- probe_report: `{payload['probe_report']}`")
    lines.append(f"- finding_count: `{payload['finding_count']}`")
    lines.append(f"- review_or_missing_count: `{payload['review_or_missing_count']}`")
    lines.append(f"- high_or_medium_count: `{payload['high_or_medium_count']}`")
    lines.append(f"- decision: `{decision}`")
    lines.append(f"- next_step: `{next_step}`")
    lines.append("- source_change_allowed_now: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Prioritized findings")
    lines.append("")
    for f in prioritized_findings:
        lines.append(f"### `{f.get('file')}` / `{f.get('dimension')}`")
        lines.append("")
        lines.append(f"- status: `{f.get('status')}`")
        lines.append(f"- severity: `{f.get('severity')}`")
        lines.append(f"- evidence: {f.get('evidence')}")
        lines.append(f"- recommendation: {f.get('recommendation')}")
        if f.get("missing"):
            lines.append(f"- missing: `{f.get('missing')}`")
        lines.append("")
    if failures:
        lines.append("## Failures")
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("community_onboarding_probe_resolver =", payload["result"])
    print("resolver_id =", RESOLVER_ID)
    print("target_family =", TARGET_FAMILY)
    print("probe_report =", probe_path)
    print("resolver_json =", out_json)
    print("resolver_md =", out_md)
    print("finding_count =", len(findings))
    print("review_or_missing_count =", len(review_or_missing))
    print("high_or_medium_count =", len(high_or_medium))
    print("decision =", decision)
    print("next_step =", next_step)
    print("source_change_allowed_now = false")
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    print()
    print("prioritized_preview =")
    for f in prioritized_findings[:10]:
        print(f"- {f.get('file')} {f.get('dimension')} {f.get('status')} severity={f.get('severity')}")

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
