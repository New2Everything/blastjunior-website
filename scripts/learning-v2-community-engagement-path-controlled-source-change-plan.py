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

PLANNER_ID = "learning-v2-community-engagement-path-controlled-source-change-plan-v0"
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

def latest_proposal_planner_report():
    reports = sorted(REPORT_DIR.glob("community-engagement-path-proposal-planner-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def file_info(rel):
    p = WORKSPACE / rel
    return {
        "path": rel,
        "exists": p.exists(),
        "is_file": p.is_file(),
        "size_bytes": p.stat().st_size if p.exists() and p.is_file() else None,
    }

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    proposal_path, proposal_report = latest_proposal_planner_report()

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

    if not proposal_path:
        failures.append("missing_community_engagement_path_proposal_planner_report")

    if proposal_report.get("result") != "ok":
        failures.append(f"proposal_planner_not_ok:{proposal_report.get('result')}")

    if proposal_report.get("target_family") != TARGET_FAMILY:
        failures.append(f"proposal_target_family_mismatch:{proposal_report.get('target_family')}")

    proposal_policy = proposal_report.get("policy") or {}
    if proposal_policy.get("planner_only") is not True:
        failures.append(f"proposal_planner_only_not_true:{proposal_policy.get('planner_only')}")

    if proposal_policy.get("source_change_allowed_now") is not False:
        failures.append(f"proposal_source_change_allowed_now_not_false:{proposal_policy.get('source_change_allowed_now')}")

    if proposal_policy.get("business_source_written") is not False:
        failures.append(f"proposal_business_source_written_not_false:{proposal_policy.get('business_source_written')}")

    proposals = proposal_report.get("proposals") or []
    if not proposals:
        failures.append("proposal_list_empty")

    change_plans = []

    for proposal in sorted(proposals, key=lambda x: x.get("priority", 999)):
        target_file = proposal.get("file")
        info = file_info(target_file) if target_file else {}

        plan_id = f"controlled-change-{proposal.get('proposal_id')}-v0"

        execution_status = "candidate_change"
        if proposal.get("priority") == 1:
            execution_status = "recommended_first_change"

        if not target_file:
            warnings.append(f"proposal_missing_file:{proposal.get('proposal_id')}")
        elif not info.get("exists"):
            warnings.append(f"proposal_target_missing:{target_file}")

        change_plans.append({
            "change_plan_id": plan_id,
            "proposal_id": proposal.get("proposal_id"),
            "target_file": target_file,
            "file_info": info,
            "execution_priority": proposal.get("priority"),
            "execution_status": execution_status,
            "risk": proposal.get("risk"),
            "allowed_future_change_type": proposal.get("change_type"),
            "source_change_allowed_now": False,
            "why_this_change": proposal.get("why_priority") or [],
            "future_change_goal": proposal.get("summary"),
            "intended_effect": proposal.get("intended_effect"),
            "future_safe_change_shape": proposal.get("safe_change_shape") or [],
            "future_acceptance_checks": proposal.get("acceptance_checks") or [],
            "blocked_until": [
                "controlled source-change dry-run executor exists",
                "dry-run confirms source_written=false",
                "autonomous machine policy gate allows next dry apply gate",
                "gate readiness confirms exactly one target file and low-risk edit shape",
                "apply executor performs backup and closes source-change gate immediately after write",
                "isolated backup-to-current validator confirms only intended delta",
                "controlled ledger acceptance updates dirty-freeze",
            ],
            "forbidden_actions": [
                "do not change source in this planner",
                "do not open source-change gate in this planner",
                "do not commit",
                "do not push",
                "do not deploy",
                "do not create public/about.html as first engagement-path source change",
                "do not touch auth, APIs, database, workers, deployment config, or gallery logic",
            ],
        })

    recommended_first_change = None
    for plan in change_plans:
        if plan.get("execution_status") == "recommended_first_change":
            recommended_first_change = plan
            break

    if not recommended_first_change:
        failures.append("missing_recommended_first_change")

    if recommended_first_change:
        if recommended_first_change.get("target_file") != "public/news.html":
            failures.append(f"recommended_first_target_not_news:{recommended_first_change.get('target_file')}")
        if recommended_first_change.get("risk") != "low":
            failures.append(f"recommended_first_risk_not_low:{recommended_first_change.get('risk')}")
        if not recommended_first_change.get("file_info", {}).get("exists"):
            failures.append(f"recommended_first_target_missing:{recommended_first_change.get('target_file')}")

    result = "ok" if not failures else "blocked"

    out_json = REPORT_DIR / f"community-engagement-path-controlled-source-change-plan-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"community-engagement-path-controlled-source-change-plan-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "planner_id": PLANNER_ID,
        "result": result,
        "target_family": TARGET_FAMILY,
        "proposal_report": str(proposal_path) if proposal_path else None,
        "proposal_count": len(proposals),
        "change_plan_count": len(change_plans),
        "recommended_first_change": recommended_first_change,
        "change_plans": change_plans,
        "tracked_deferred_items": proposal_report.get("tracked_deferred_items") or [],
        "recommended_next_step": "build_engagement_news_return_path_source_change_dry_run_executor" if result == "ok" else "fix_engagement_path_controlled_source_change_plan_blockers",
        "policy": {
            "plan_only": True,
            "source_change_allowed_now": False,
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
    lines.append("# Learning V2 Community Engagement Path Controlled Source Change Plan")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- planner_id: `{PLANNER_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- proposal_count: `{len(proposals)}`")
    lines.append(f"- change_plan_count: `{len(change_plans)}`")
    lines.append(f"- recommended_next_step: `{payload['recommended_next_step']}`")
    lines.append("- plan_only: `true`")
    lines.append("- source_change_allowed_now: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- human_review_required: `false`")
    lines.append("- machine_policy_gate: `true`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Recommended First Change")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(recommended_first_change, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Change Plans")
    for plan in change_plans:
        lines.append(
            f"- `{plan['change_plan_id']}` target=`{plan.get('target_file')}` "
            f"priority=`{plan.get('execution_priority')}` status=`{plan.get('execution_status')}` risk=`{plan.get('risk')}`"
        )
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

    print("community_engagement_path_controlled_source_change_plan =", result)
    print("target_family =", TARGET_FAMILY)
    print("proposal_report =", str(proposal_path) if proposal_path else None)
    print("proposal_count =", len(proposals))
    print("change_plan_count =", len(change_plans))
    print("recommended_first_change_plan_id =", recommended_first_change.get("change_plan_id") if recommended_first_change else None)
    print("recommended_first_proposal_id =", recommended_first_change.get("proposal_id") if recommended_first_change else None)
    print("recommended_first_target_file =", recommended_first_change.get("target_file") if recommended_first_change else None)
    print("recommended_next_step =", payload["recommended_next_step"])
    print("plan_only = True")
    print("source_change_allowed_now = False")
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
