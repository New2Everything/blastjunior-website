#!/usr/bin/env python3
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

RESOLVER_ID = "learning-v2-community-engagement-path-probe-resolver-v0"
TARGET_FAMILY = "community.engagement_path"

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
    reports = sorted([
        p for p in REPORT_DIR.glob("community-engagement-path-probe-*.json")
        if "probe-design" not in p.name
        and "probe-resolver" not in p.name
    ])
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def severity_rank(sev):
    return {
        "high": 0,
        "medium": 1,
        "low": 2,
        "info": 3,
    }.get(str(sev).lower(), 9)

def status_rank(status):
    return {
        "missing": 0,
        "review": 1,
        "ok": 2,
    }.get(str(status).lower(), 9)

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    probe_path, probe = latest_probe_report()

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

    if not probe_path:
        failures.append("missing_community_engagement_path_probe_report")

    if probe.get("result") != "ok":
        failures.append(f"probe_not_ok:{probe.get('result')}")

    if probe.get("target_family") != TARGET_FAMILY:
        failures.append(f"probe_target_family_mismatch:{probe.get('target_family')}")

    probe_policy = probe.get("policy") or {}
    if probe_policy.get("observe_only") is not True:
        failures.append(f"probe_not_observe_only:{probe_policy.get('observe_only')}")

    if probe_policy.get("state_written") is not False:
        failures.append(f"probe_state_written_not_false:{probe_policy.get('state_written')}")

    if probe_policy.get("business_source_written") is not False:
        failures.append(f"probe_business_source_written_not_false:{probe_policy.get('business_source_written')}")

    findings = probe.get("findings") or []

    actionable = [
        f for f in findings
        if f.get("status") in ("missing", "review")
        or f.get("severity") in ("high", "medium")
    ]

    prioritized = sorted(
        actionable,
        key=lambda f: (
            severity_rank(f.get("severity")),
            status_rank(f.get("status")),
            f.get("dimension") or "",
            f.get("file") or "",
        ),
    )

    status_counts = dict(Counter([f.get("status") for f in findings]))
    severity_counts = dict(Counter([f.get("severity") for f in findings]))
    dimension_counts = dict(Counter([f.get("dimension") for f in actionable]))
    file_counts = dict(Counter([f.get("file") for f in actionable]))

    # Resolver interpretation:
    # - Creating a whole missing about page is likely larger than the safest first engagement-path change.
    # - The safer first proposal should focus on adding or strengthening return-path CTA evidence on existing content pages.
    # - Missing about page should remain a tracked proposal candidate, but not recommended as first source change.
    recommended_scope = {
        "must_not_change_source_now": True,
        "source_change_allowed_now": False,
        "proposal_should_focus_on": [
            "Strengthen return_path_after_browsing from existing browsing pages to a clear community action.",
            "Prefer existing files before creating a new page.",
            "Use a compact low-risk CTA block or link cluster.",
            "Do not create a new about page as the first source change unless a later planner proves it is the lowest-risk option.",
            "Keep proposal output plan-only until a controlled source-change plan and dry-run executor exist."
        ],
        "defer_or_track_separately": [
            "public/about.html missing file can become a future candidate, but should not dominate the first engagement-path source change.",
        ],
        "candidate_target_files_for_future_proposal": [
            "public/news.html",
            "public/gallery.html",
            "public/index.html",
        ],
        "not_recommended_first_target_files": [
            "public/about.html"
        ],
    }

    if failures:
        decision = "blocked"
        next_step = "fix_resolver_blockers"
    elif not actionable:
        decision = "no_action_needed"
        next_step = "return_to_next_target_selector"
    else:
        decision = "proposal_ready"
        next_step = "build_community_engagement_path_proposal_planner"

    result = "ok" if not failures else "blocked"

    out_json = REPORT_DIR / f"community-engagement-path-probe-resolver-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"community-engagement-path-probe-resolver-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "resolver_id": RESOLVER_ID,
        "result": result,
        "target_family": TARGET_FAMILY,
        "probe_report": str(probe_path) if probe_path else None,
        "finding_count": len(findings),
        "review_or_missing_count": len([x for x in findings if x.get("status") in ("review", "missing")]),
        "high_or_medium_count": len([x for x in findings if x.get("severity") in ("high", "medium")]),
        "status_counts": status_counts,
        "severity_counts": severity_counts,
        "dimension_counts": dimension_counts,
        "file_counts": file_counts,
        "decision": decision,
        "next_step": next_step,
        "prioritized_findings": prioritized,
        "recommended_scope": recommended_scope,
        "policy": {
            "resolver_only": True,
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
    lines.append("# Learning V2 Community Engagement Path Probe Resolver")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- resolver_id: `{RESOLVER_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- decision: `{decision}`")
    lines.append(f"- next_step: `{next_step}`")
    lines.append(f"- finding_count: `{len(findings)}`")
    lines.append(f"- review_or_missing_count: `{payload['review_or_missing_count']}`")
    lines.append(f"- high_or_medium_count: `{payload['high_or_medium_count']}`")
    lines.append("- resolver_only: `true`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- human_review_required: `false`")
    lines.append("- machine_policy_gate: `true`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Prioritized Findings")
    for f in prioritized:
        lines.append(
            f"- `{f.get('dimension')}` file=`{f.get('file')}` "
            f"status=`{f.get('status')}` severity=`{f.get('severity')}`"
        )
    lines.append("")
    lines.append("## Recommended Scope")
    for item in recommended_scope["proposal_should_focus_on"]:
        lines.append(f"- {item}")
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

    print("community_engagement_path_probe_resolver =", result)
    print("target_family =", TARGET_FAMILY)
    print("probe_report =", str(probe_path) if probe_path else None)
    print("finding_count =", len(findings))
    print("review_or_missing_count =", payload["review_or_missing_count"])
    print("high_or_medium_count =", payload["high_or_medium_count"])
    print("decision =", decision)
    print("next_step =", next_step)
    print("prioritized_finding_count =", len(prioritized))
    print("candidate_target_files_for_future_proposal =", json.dumps(recommended_scope["candidate_target_files_for_future_proposal"], ensure_ascii=False))
    print("not_recommended_first_target_files =", json.dumps(recommended_scope["not_recommended_first_target_files"], ensure_ascii=False))
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

if __name__ == "__main__":
    main()
