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

PLANNER_ID = "learning-v2-community-engagement-path-proposal-planner-v0"
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

def latest_resolver_report():
    reports = sorted(REPORT_DIR.glob("community-engagement-path-probe-resolver-*.json"))
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

    resolver_path, resolver = latest_resolver_report()

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

    if not resolver_path:
        failures.append("missing_community_engagement_path_probe_resolver_report")

    if resolver.get("result") != "ok":
        failures.append(f"resolver_not_ok:{resolver.get('result')}")

    if resolver.get("target_family") != TARGET_FAMILY:
        failures.append(f"resolver_target_family_mismatch:{resolver.get('target_family')}")

    if resolver.get("decision") != "proposal_ready":
        failures.append(f"resolver_decision_not_proposal_ready:{resolver.get('decision')}")

    resolver_policy = resolver.get("policy") or {}
    if resolver_policy.get("resolver_only") is not True:
        failures.append(f"resolver_only_not_true:{resolver_policy.get('resolver_only')}")

    if resolver_policy.get("business_source_written") is not False:
        failures.append(f"resolver_business_source_written_not_false:{resolver_policy.get('business_source_written')}")

    recommended_scope = resolver.get("recommended_scope") or {}
    candidate_files = recommended_scope.get("candidate_target_files_for_future_proposal") or []
    not_recommended = set(recommended_scope.get("not_recommended_first_target_files") or [])

    existing_candidate_files = [
        rel for rel in candidate_files
        if rel not in not_recommended
        and (WORKSPACE / rel).exists()
        and (WORKSPACE / rel).is_file()
    ]

    if not existing_candidate_files:
        failures.append("no_existing_candidate_files_for_proposal")

    proposals = []

    # Proposal 1: safest first target from resolver scope.
    if "public/news.html" in existing_candidate_files:
        proposals.append({
            "proposal_id": "engagement-news-return-path-cta",
            "file": "public/news.html",
            "priority": 1,
            "change_type": "minimal_existing_html_cta_insert_or_edit",
            "summary": "Add a compact return-path CTA on the news page so readers can move from browsing club updates to a clear community action.",
            "intended_effect": "Strengthen return_path_after_browsing without creating a new page or touching navigation.",
            "safe_change_shape": [
                "Use existing public/news.html only.",
                "Add or clarify one compact CTA block near the page end or after the main news content.",
                "Point users toward an existing safe destination such as gallery, homepage, join/contact path, or club community action.",
                "Keep copy short and beginner-friendly.",
                "Do not change scripts, auth, data APIs, or deployment files.",
                "Do not create public/about.html in the first engagement-path source change.",
                "Do not commit, push, or deploy."
            ],
            "acceptance_checks": [
                "public/news.html contains a clear next-step CTA after browsing news.",
                "CTA text connects community updates to joining, trying, contacting, or viewing HADO moments.",
                "No unrelated files changed.",
                "Source change remains minimal and reversible.",
                "Gate closes after apply.",
                "Isolated validator confirms only intended delta."
            ],
            "risk": "low",
            "requires_source_change_later": True,
            "source_change_allowed_now": False,
            "why_priority": [
                "Resolver identified return_path_after_browsing as review/medium.",
                "public/news.html is an existing browsing page.",
                "This avoids creating a missing about page as the first move.",
                "It is likely lower-risk than touching nav or expanding page structure."
            ],
        })

    # Proposal 2: gallery already has some evidence, so strengthen only if planner later permits.
    if "public/gallery.html" in existing_candidate_files:
        proposals.append({
            "proposal_id": "engagement-gallery-return-path-strengthening",
            "file": "public/gallery.html",
            "priority": 2,
            "change_type": "minimal_existing_html_cta_refinement",
            "summary": "Strengthen the existing gallery next-action area if future checks show the return path is still weak.",
            "intended_effect": "Improve the path from watching HADO moments to a concrete club action.",
            "safe_change_shape": [
                "Use existing public/gallery.html only.",
                "Refine or add a very small CTA/link cluster.",
                "Do not duplicate the existing gallery-next-action block unnecessarily.",
                "Do not touch media/gallery loading logic.",
                "Do not commit, push, or deploy."
            ],
            "acceptance_checks": [
                "Existing gallery-next-action remains present.",
                "CTA path is clearer without duplicate blocks.",
                "No JS behavior changes.",
                "Only public/gallery.html changes if selected."
            ],
            "risk": "low",
            "requires_source_change_later": True,
            "source_change_allowed_now": False,
            "why_priority": [
                "Gallery already has some return-path evidence.",
                "It was recently changed and accepted, so avoid selecting it first unless needed.",
                "Useful as fallback if news page is not suitable."
            ],
        })

    # Proposal 3: homepage as central fallback, but avoid over-editing after prior closed loop.
    if "public/index.html" in existing_candidate_files:
        proposals.append({
            "proposal_id": "engagement-homepage-community-path-linkage",
            "file": "public/index.html",
            "priority": 3,
            "change_type": "minimal_existing_html_copy_or_link_refinement",
            "summary": "Refine homepage engagement-path wording only if later planning shows the homepage is the safest place to connect users to community action.",
            "intended_effect": "Make the overall community path easier to follow from the homepage.",
            "safe_change_shape": [
                "Use existing public/index.html only.",
                "Prefer copy/link refinement over adding a new large block.",
                "Do not disturb the existing homepage onboarding block.",
                "Do not touch unrelated sections.",
                "Do not commit, push, or deploy."
            ],
            "acceptance_checks": [
                "Homepage onboarding block remains present.",
                "Community path is clearer.",
                "No unrelated homepage changes.",
                "Only public/index.html changes if selected."
            ],
            "risk": "low",
            "requires_source_change_later": True,
            "source_change_allowed_now": False,
            "why_priority": [
                "Homepage already has onboarding improvements from a closed loop.",
                "Avoid over-optimizing the same file unless later scoring prefers it.",
                "Useful as fallback, not first pick."
            ],
        })

    # Track missing about separately, not first source change.
    tracked_deferred_items = []
    for rel in not_recommended:
        tracked_deferred_items.append({
            "file": rel,
            "reason": "Resolver marked this as not recommended first target.",
            "future_candidate": True,
            "source_change_allowed_now": False,
            "recommended_handling": "Track separately; do not create a new page before lower-risk existing-page improvements are planned and tested.",
        })

    proposal_count = len(proposals)
    recommended_first_proposal = proposals[0] if proposals else None

    if proposal_count == 0 and not failures:
        failures.append("no_proposals_generated")

    result = "ok" if not failures else "blocked"

    out_json = REPORT_DIR / f"community-engagement-path-proposal-planner-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"community-engagement-path-proposal-planner-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "planner_id": PLANNER_ID,
        "result": result,
        "target_family": TARGET_FAMILY,
        "resolver_report": str(resolver_path) if resolver_path else None,
        "finding_count": resolver.get("finding_count"),
        "review_or_missing_count": resolver.get("review_or_missing_count"),
        "high_or_medium_count": resolver.get("high_or_medium_count"),
        "proposal_count": proposal_count,
        "recommended_first_proposal": recommended_first_proposal,
        "proposals": proposals,
        "tracked_deferred_items": tracked_deferred_items,
        "file_info": [file_info(x) for x in sorted(set(candidate_files + list(not_recommended)))],
        "recommended_next_step": "build_community_engagement_path_controlled_source_change_plan" if result == "ok" else "fix_engagement_path_proposal_planner_blockers",
        "policy": {
            "planner_only": True,
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
    lines.append("# Learning V2 Community Engagement Path Proposal Planner")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- planner_id: `{PLANNER_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- proposal_count: `{proposal_count}`")
    lines.append(f"- recommended_next_step: `{payload['recommended_next_step']}`")
    lines.append("- planner_only: `true`")
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
    lines.append("## Recommended First Proposal")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(recommended_first_proposal, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Proposals")
    for p in proposals:
        lines.append(f"- `{p['proposal_id']}` file=`{p['file']}` priority=`{p['priority']}` risk=`{p['risk']}`")
    if tracked_deferred_items:
        lines.append("")
        lines.append("## Deferred Items")
        for item in tracked_deferred_items:
            lines.append(f"- `{item['file']}`: {item['reason']}")
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

    print("community_engagement_path_proposal_planner =", result)
    print("target_family =", TARGET_FAMILY)
    print("resolver_report =", str(resolver_path) if resolver_path else None)
    print("proposal_count =", proposal_count)
    print("recommended_first_proposal_id =", recommended_first_proposal.get("proposal_id") if recommended_first_proposal else None)
    print("recommended_first_target_file =", recommended_first_proposal.get("file") if recommended_first_proposal else None)
    print("recommended_next_step =", payload["recommended_next_step"])
    print("planner_only = True")
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
