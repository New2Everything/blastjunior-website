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
PLANNER_ID = "learning-v2-community-onboarding-proposal-planner-v0"

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

def latest_resolver_report():
    apply_reports = sorted(REPORT_DIR.glob("community-onboarding-probe-resolver-apply-*.json"))
    reports = apply_reports or sorted(REPORT_DIR.glob("community-onboarding-probe-resolver-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def proposal_for_finding(f):
    file = f.get("file")
    dimension = f.get("dimension")
    severity = f.get("severity")

    if file == "public/index.html" and dimension == "onboarding_sequence":
        return {
            "proposal_id": "homepage-onboarding-sequence",
            "file": file,
            "priority": "high",
            "change_type": "content_structure",
            "summary": "Add or clarify a homepage onboarding sequence for first-time parents and players.",
            "intended_effect": "Help visitors understand what HADO is, why it matters, who it is for, and what to do next.",
            "safe_change_shape": [
                "Add a concise 'New to HADO?' or 'Start here' section.",
                "Use short steps: 1) Watch/understand 2) Try/join 3) Join community/club.",
                "Avoid changing backend, auth, routing, or data APIs."
            ],
            "risk": "low",
            "requires_source_change_later": True,
            "source_change_allowed_now": False,
        }

    if file == "components/nav.html" and dimension in ("onboarding_sequence", "motivation_to_next_step"):
        return {
            "proposal_id": "nav-onboarding-entry-point",
            "file": file,
            "priority": "medium",
            "change_type": "navigation_labeling",
            "summary": "Add a clearer navigation entry point for new visitors, parents, or players.",
            "intended_effect": "Make the first successful action easier to find from global navigation.",
            "safe_change_shape": [
                "Consider adding or clarifying a nav label such as 'Start Here', 'Join', '体验HADO', or '家长入口'.",
                "Keep existing links intact unless a later controlled diff proves a safe replacement.",
                "Do not change JavaScript behavior in this proposal stage."
            ],
            "risk": "medium",
            "requires_source_change_later": True,
            "source_change_allowed_now": False,
        }

    if file == "public/gallery.html":
        return {
            "proposal_id": "gallery-next-action",
            "file": file,
            "priority": "medium",
            "change_type": "cta_and_context",
            "summary": "Add a next action and onboarding context to gallery visitors.",
            "intended_effect": "Turn interest from photos/videos into a clear next step.",
            "safe_change_shape": [
                "Add a lightweight CTA near gallery intro or bottom.",
                "Explain how visitors can try, join, or learn HADO after viewing gallery content.",
                "Avoid changing gallery data loading or media paths."
            ],
            "risk": "low",
            "requires_source_change_later": True,
            "source_change_allowed_now": False,
        }

    if file == "public/about.html" and dimension == "file_presence":
        return {
            "proposal_id": "about-page-presence-review",
            "file": file,
            "priority": "low",
            "change_type": "route_or_link_review",
            "summary": "Review whether an about page is expected and whether links point to it.",
            "intended_effect": "Avoid missing-page confusion for visitors seeking basic context.",
            "safe_change_shape": [
                "Check whether public/about.html should exist.",
                "If nav or content links to about.html, either create a simple page or remove/redirect the link.",
                "Do not create the page until link references are confirmed."
            ],
            "risk": "low",
            "requires_source_change_later": True,
            "source_change_allowed_now": False,
        }

    return {
        "proposal_id": f"generic-{file}-{dimension}".replace("/", "-"),
        "file": file,
        "priority": "medium" if severity in ("high", "medium") else "low",
        "change_type": "review",
        "summary": f"Review {dimension} finding in {file}.",
        "intended_effect": f.get("recommendation"),
        "safe_change_shape": [
            "Convert finding into a minimal, reviewable source-change proposal later.",
            "Do not edit source in planner stage."
        ],
        "risk": "low",
        "requires_source_change_later": True,
        "source_change_allowed_now": False,
    }

def dedupe(items):
    seen = set()
    out = []
    for item in items:
        key = item.get("proposal_id")
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write proposal planner result to state.json; never modifies website source")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    resolver_path, resolver = latest_resolver_report()
    findings = resolver.get("prioritized_findings") or []

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("current_topic") != "community-experience":
        failures.append(f"current_topic_not_community_experience:{state.get('current_topic')}")

    if state.get("current_stage") != "community_onboarding_proposal_ready":
        failures.append(f"current_stage_not_community_onboarding_proposal_ready:{state.get('current_stage')}")

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

    if not resolver_path:
        failures.append("missing_community_onboarding_resolver_report")

    if resolver.get("decision") != "proposal_ready":
        failures.append(f"resolver_not_proposal_ready:{resolver.get('decision')}")

    proposals = dedupe([proposal_for_finding(f) for f in findings])

    priority_order = {"high": 0, "medium": 1, "low": 2}
    proposals = sorted(proposals, key=lambda x: priority_order.get(x.get("priority"), 9))

    payload = {
        "generated_at": now_iso(),
        "planner_id": PLANNER_ID,
        "result": "ok" if not failures else "blocked",
        "target_family": TARGET_FAMILY,
        "resolver_report": str(resolver_path) if resolver_path else None,
        "finding_count": len(findings),
        "proposal_count": len(proposals),
        "proposals": proposals,
        "recommended_next_step": "build_controlled_source_change_plan" if proposals else "no_proposal_needed",
        "policy": {
            "source_change_allowed_now": False,
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "planner_only": True
        },
        "failures": failures
    }

    out_json = REPORT_DIR / f"community-onboarding-proposal-planner-{stamp()}.json"
    out_md = REPORT_DIR / f"community-onboarding-proposal-planner-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Community Onboarding Proposal Planner")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- planner_id: `{PLANNER_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- resolver_report: `{payload['resolver_report']}`")
    lines.append(f"- finding_count: `{payload['finding_count']}`")
    lines.append(f"- proposal_count: `{payload['proposal_count']}`")
    lines.append(f"- recommended_next_step: `{payload['recommended_next_step']}`")
    lines.append("- source_change_allowed_now: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Proposals")
    lines.append("")
    for p in proposals:
        lines.append(f"### `{p.get('proposal_id')}`")
        lines.append("")
        lines.append(f"- file: `{p.get('file')}`")
        lines.append(f"- priority: `{p.get('priority')}`")
        lines.append(f"- change_type: `{p.get('change_type')}`")
        lines.append(f"- summary: {p.get('summary')}")
        lines.append(f"- intended_effect: {p.get('intended_effect')}")
        lines.append(f"- risk: `{p.get('risk')}`")
        lines.append("- safe_change_shape:")
        for s in p.get("safe_change_shape") or []:
            lines.append(f"  - {s}")
        lines.append("")
    if failures:
        lines.append("## Failures")
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("community_onboarding_proposal_planner =", payload["result"])
    print("planner_id =", PLANNER_ID)
    print("target_family =", TARGET_FAMILY)
    print("resolver_report =", resolver_path)
    print("planner_json =", out_json)
    print("planner_md =", out_md)
    print("finding_count =", len(findings))
    print("proposal_count =", len(proposals))
    print("recommended_next_step =", payload["recommended_next_step"])
    print("source_change_allowed_now = false")
    print("state_written =", "true" if args.apply and not failures else "false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    print()
    print("proposal_preview =")
    for p in proposals:
        print(f"- {p.get('priority')} {p.get('proposal_id')} file={p.get('file')} risk={p.get('risk')}")


    if args.apply and not failures:
        state.setdefault("history", [])
        state["history"].append({
            "at": now_iso(),
            "executor": "community_onboarding_proposal_planner",
            "stage_before": "community_onboarding_proposal_ready",
            "stage_after": "community_onboarding_plan_ready",
            "target_family": TARGET_FAMILY,
            "resolver_report": str(resolver_path),
            "planner_report": str(out_json),
            "proposal_count": len(proposals),
            "source_changed": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        })
        state["last_community_onboarding_proposal_planner"] = {
            "at": now_iso(),
            "result": "community_onboarding_plan_ready",
            "target_family": TARGET_FAMILY,
            "resolver_report": str(resolver_path),
            "planner_report": str(out_json),
            "proposal_count": len(proposals),
            "source_changed": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        }
        state["current_stage"] = "community_onboarding_plan_ready"
        state["next_action"] = (
            "Build controlled source change plan from community onboarding proposal. "
            "Do not modify website source until source_change_gate opens."
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
