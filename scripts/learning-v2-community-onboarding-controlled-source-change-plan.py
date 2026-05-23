#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FAMILY = "community.onboarding_experience"
PLANNER_ID = "learning-v2-community-onboarding-controlled-source-change-plan-v0"

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

def latest_proposal_report():
    reports = sorted(REPORT_DIR.glob("community-onboarding-proposal-planner-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def file_info(rel_path):
    p = WORKSPACE / rel_path
    return {
        "path": rel_path,
        "exists": p.exists(),
        "size_bytes": p.stat().st_size if p.exists() else None,
        "is_file": p.is_file() if p.exists() else False,
    }

def build_change_plan(proposals):
    plans = []

    for p in proposals:
        proposal_id = p.get("proposal_id")
        rel_file = p.get("file")
        info = file_info(rel_file) if rel_file else {}

        if proposal_id == "homepage-onboarding-sequence":
            plans.append({
                "change_plan_id": "controlled-change-homepage-onboarding-sequence-v0",
                "proposal_id": proposal_id,
                "target_file": rel_file,
                "file_info": info,
                "execution_priority": 1,
                "execution_status": "recommended_first_change",
                "risk": "low",
                "allowed_future_change_type": "minimal_html_content_insert_or_edit",
                "source_change_allowed_now": False,
                "why_first": [
                    "Highest priority proposal.",
                    "Low risk because it targets homepage content structure rather than shared navigation behavior.",
                    "Directly addresses the strongest onboarding problem: first-time visitor sequence."
                ],
                "future_change_goal": "Add or clarify a compact onboarding block on the homepage so new parents and players know what HADO is, why it matters, and what to do next.",
                "future_safe_change_shape": [
                    "Prefer one small section, not a redesign.",
                    "Do not touch login/auth/user/session code.",
                    "Do not touch API fetches or dynamic data loading.",
                    "Do not change navigation JavaScript.",
                    "Do not delete existing content.",
                    "Keep copy short and parent/player oriented.",
                    "After change, run homepage smoke checks and system integrity."
                ],
                "future_acceptance_checks": [
                    "public/index.html still exists.",
                    "Homepage contains a clear first action such as learn / try / join / contact.",
                    "Homepage explains a simple sequence: understand HADO → try/join → participate in community.",
                    "No backend, D1, KV, Worker, login, gallery data, or deploy file is changed.",
                    "system_integrity remains ok.",
                    "drift_count remains 0 after re-baseline if a system script is added, or after controlled source-change validation if source edits are allowed later."
                ],
                "blocked_until": [
                    "source_changes_allowed is explicitly opened by a controlled gate.",
                    "A source-change executor creates a dry-run diff first.",
                    "Diff is reviewed before apply."
                ],
            })

        elif proposal_id == "nav-onboarding-entry-point":
            plans.append({
                "change_plan_id": "controlled-change-nav-onboarding-entry-point-v0",
                "proposal_id": proposal_id,
                "target_file": rel_file,
                "file_info": info,
                "execution_priority": 3,
                "execution_status": "defer_until_homepage_change_validated",
                "risk": "medium",
                "allowed_future_change_type": "navigation_label_review",
                "source_change_allowed_now": False,
                "why_deferred": [
                    "components/nav.html is shared across pages.",
                    "A navigation change may affect global UX.",
                    "Better to validate homepage onboarding copy first."
                ],
                "future_safe_change_shape": [
                    "Review existing nav links before any change.",
                    "Avoid removing links.",
                    "Avoid changing mobile nav behavior.",
                    "Only consider label or single-link addition after homepage plan is validated."
                ],
            })

        elif proposal_id == "gallery-next-action":
            plans.append({
                "change_plan_id": "controlled-change-gallery-next-action-v0",
                "proposal_id": proposal_id,
                "target_file": rel_file,
                "file_info": info,
                "execution_priority": 2,
                "execution_status": "second_candidate_after_homepage",
                "risk": "low",
                "allowed_future_change_type": "gallery_context_or_cta_copy",
                "source_change_allowed_now": False,
                "why_second": [
                    "Gallery visitors already show interest.",
                    "A lightweight CTA can convert curiosity into action.",
                    "Risk is lower than nav because it is page-local."
                ],
                "future_safe_change_shape": [
                    "Add a small CTA or context block near gallery intro or bottom.",
                    "Do not touch gallery data loading.",
                    "Do not touch media paths.",
                    "Do not change upload or R2 paths."
                ],
            })

        elif proposal_id == "about-page-presence-review":
            plans.append({
                "change_plan_id": "controlled-change-about-page-presence-review-v0",
                "proposal_id": proposal_id,
                "target_file": rel_file,
                "file_info": info,
                "execution_priority": 4,
                "execution_status": "review_only_not_first_change",
                "risk": "low",
                "allowed_future_change_type": "route_presence_review",
                "source_change_allowed_now": False,
                "why_deferred": [
                    "Missing public/about.html may or may not be intentional.",
                    "Need to confirm whether anything links to it before creating a new page.",
                    "Creating a new page is broader than improving existing onboarding sequence."
                ],
                "future_safe_change_shape": [
                    "Search references to about.html first.",
                    "If no link references exist, keep as review-only.",
                    "If links exist, decide between creating a simple page or changing links later."
                ],
            })

        else:
            plans.append({
                "change_plan_id": f"controlled-change-{proposal_id}",
                "proposal_id": proposal_id,
                "target_file": rel_file,
                "file_info": info,
                "execution_priority": 99,
                "execution_status": "autonomous_policy_required",
                "risk": p.get("risk") or "unknown",
                "source_change_allowed_now": False,
            })

    return sorted(plans, key=lambda x: x.get("execution_priority", 99))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write autonomous-policy waiting state only; never modifies website source")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    proposal_path, proposal = latest_proposal_report()
    proposals = proposal.get("proposals") or []

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("current_topic") != "community-experience":
        failures.append(f"current_topic_not_community_experience:{state.get('current_topic')}")

    if state.get("current_stage") != "community_onboarding_plan_ready":
        failures.append(f"current_stage_not_community_onboarding_plan_ready:{state.get('current_stage')}")

    if state.get("current_target_family") != TARGET_FAMILY:
        failures.append(f"target_family_mismatch:{state.get('current_target_family')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if not proposal_path:
        failures.append("missing_community_onboarding_proposal_planner_report")

    if proposal.get("result") != "ok":
        failures.append(f"proposal_planner_not_ok:{proposal.get('result')}")

    if not proposals:
        failures.append("no_proposals_to_plan")

    change_plans = build_change_plan(proposals)

    first_change = next(
        (p for p in change_plans if p.get("execution_status") == "recommended_first_change"),
        None
    )

    payload = {
        "generated_at": now_iso(),
        "planner_id": PLANNER_ID,
        "result": "ok" if not failures else "blocked",
        "target_family": TARGET_FAMILY,
        "proposal_report": str(proposal_path) if proposal_path else None,
        "proposal_count": len(proposals),
        "change_plan_count": len(change_plans),
        "recommended_first_change": first_change,
        "change_plans": change_plans,
        "recommended_next_step": "build_homepage_onboarding_source_change_dry_run_executor" if first_change else "autonomous_policy_required",
        "policy": {
            "source_change_allowed_now": False,
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "plan_only": True
        },
        "failures": failures
    }

    out_json = REPORT_DIR / f"community-onboarding-controlled-source-change-plan-{stamp()}.json"
    out_md = REPORT_DIR / f"community-onboarding-controlled-source-change-plan-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Community Onboarding Controlled Source Change Plan")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- planner_id: `{PLANNER_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- proposal_report: `{payload['proposal_report']}`")
    lines.append(f"- proposal_count: `{payload['proposal_count']}`")
    lines.append(f"- change_plan_count: `{payload['change_plan_count']}`")
    lines.append(f"- recommended_next_step: `{payload['recommended_next_step']}`")
    lines.append("- source_change_allowed_now: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Recommended first change")
    lines.append("")
    if first_change:
        lines.append(f"- change_plan_id: `{first_change.get('change_plan_id')}`")
        lines.append(f"- target_file: `{first_change.get('target_file')}`")
        lines.append(f"- risk: `{first_change.get('risk')}`")
        lines.append(f"- status: `{first_change.get('execution_status')}`")
        lines.append("")
        lines.append("Why first:")
        for x in first_change.get("why_first") or []:
            lines.append(f"- {x}")
        lines.append("")
    else:
        lines.append("- none")
        lines.append("")
    lines.append("## All change plans")
    lines.append("")
    for p in change_plans:
        lines.append(f"### `{p.get('change_plan_id')}`")
        lines.append("")
        lines.append(f"- proposal_id: `{p.get('proposal_id')}`")
        lines.append(f"- target_file: `{p.get('target_file')}`")
        lines.append(f"- execution_priority: `{p.get('execution_priority')}`")
        lines.append(f"- execution_status: `{p.get('execution_status')}`")
        lines.append(f"- risk: `{p.get('risk')}`")
        lines.append(f"- file_exists: `{str((p.get('file_info') or {}).get('exists')).lower()}`")
        lines.append(f"- source_change_allowed_now: `false`")
        lines.append("")
    if failures:
        lines.append("## Failures")
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("community_onboarding_controlled_source_change_plan =", payload["result"])
    print("planner_id =", PLANNER_ID)
    print("target_family =", TARGET_FAMILY)
    print("proposal_report =", proposal_path)
    print("plan_json =", out_json)
    print("plan_md =", out_md)
    print("proposal_count =", len(proposals))
    print("change_plan_count =", len(change_plans))
    print("recommended_next_step =", payload["recommended_next_step"])
    print("source_change_allowed_now = false")
    print("state_written =", "true" if args.apply and not failures else "false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    print()
    print("change_plan_preview =")
    for p in change_plans:
        info = p.get("file_info") or {}
        print(
            f"- priority={p.get('execution_priority')} "
            f"id={p.get('change_plan_id')} "
            f"file={p.get('target_file')} "
            f"exists={info.get('exists')} "
            f"status={p.get('execution_status')} "
            f"risk={p.get('risk')}"
        )


    if args.apply and not failures:
        state.setdefault("history", [])
        state["history"].append({
            "at": now_iso(),
            "executor": "community_onboarding_controlled_source_change_plan",
            "stage_before": "community_onboarding_plan_ready",
            "stage_after": "community_onboarding_autonomous_policy_required",
            "target_family": TARGET_FAMILY,
            "proposal_report": str(proposal_path),
            "plan_report": str(out_json),
            "proposal_count": len(proposals),
            "change_plan_count": len(change_plans),
            "recommended_next_step": payload["recommended_next_step"],
            "source_changed": False,
            "source_change_allowed_now": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        })
        state["last_community_onboarding_controlled_source_change_plan"] = {
            "at": now_iso(),
            "result": "community_onboarding_autonomous_policy_required",
            "target_family": TARGET_FAMILY,
            "proposal_report": str(proposal_path),
            "plan_report": str(out_json),
            "proposal_count": len(proposals),
            "change_plan_count": len(change_plans),
            "recommended_next_step": payload["recommended_next_step"],
            "source_changed": False,
            "source_change_allowed_now": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        }
        state["current_stage"] = "community_onboarding_autonomous_policy_required"
        state["next_action"] = (
            "Manual review required before opening source_change_gate. "
            "Do not modify website source, commit, push, or deploy."
        )
        state["updated_at"] = now_iso()
        save_json(STATE, state)

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
