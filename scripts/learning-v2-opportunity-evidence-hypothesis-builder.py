#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
STATE = BASE / "state.json"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

BUILDER_ID = "learning-v2-opportunity-evidence-hypothesis-builder-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def latest_discovery_report():
    files = sorted(
        REPORT_DIR.glob("design-opportunity-discovery-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None

def build_evidence_packet(candidate, discovery_path):
    target_family = candidate.get("target_family")
    lane = candidate.get("lane")
    opportunity_type = candidate.get("opportunity_type")

    evidence = candidate.get("evidence") or {}

    packet = {
        "target_family": target_family,
        "lane": lane,
        "opportunity_type": opportunity_type,
        "criticality": candidate.get("criticality"),
        "capability": candidate.get("capability"),
        "suggested_scope": candidate.get("suggested_scope"),
        "why_this_matters": candidate.get("why_this_matters"),
        "expected_user_value": candidate.get("expected_user_value"),
        "discovery_report": str(discovery_path),
        "raw_evidence": evidence,
        "evidence_quality": "direct" if evidence else "weak",
        "current_site_observation": None,
        "gap_between_current_and_expected": None,
        "risk_notes": [
            "dry-run only",
            "no website files changed",
            "no commit",
            "no push",
            "no deploy",
        ],
    }

    if target_family == "quality.missing_asset_reference":
        missing_assets = evidence.get("missing_assets") or []
        packet["current_site_observation"] = (
            "At least one local asset reference is missing from the repository."
        )
        packet["gap_between_current_and_expected"] = (
            "A referenced CSS, JS, or image asset should exist at the normalized local target path."
        )
        packet["missing_asset_count"] = evidence.get("missing_asset_count")
        packet["missing_assets"] = missing_assets

    elif target_family == "quality.broken_internal_links":
        packet["current_site_observation"] = (
            "At least one internal page link points to a missing local target."
        )
        packet["gap_between_current_and_expected"] = (
            "Internal navigation links should resolve to existing public pages."
        )

    elif opportunity_type in ["missing_capability", "experience_friction"]:
        packet["current_site_observation"] = (
            "No critical quality bug was selected; this opportunity is based on design capability or friction scan."
        )
        packet["gap_between_current_and_expected"] = (
            "The current site appears to lack or under-serve the selected user experience capability."
        )

    else:
        packet["current_site_observation"] = "Opportunity selected by discovery layer."
        packet["gap_between_current_and_expected"] = "Needs proposal-stage clarification."

    return packet

def build_hypothesis(candidate, evidence_packet):
    target_family = candidate.get("target_family")
    opportunity_type = candidate.get("opportunity_type")

    if target_family == "quality.missing_asset_reference":
        hypothesis = {
            "hypothesis_id": "repair-missing-asset-reference-v0",
            "hypothesis_type": "repair",
            "user_problem_or_missing_capability": (
                "A page references a local asset that does not exist in the repository, which may break styling or page presentation."
            ),
            "proposed_smallest_change": (
                "Before editing website files, identify whether the correct fix is to add the missing asset, change the reference, or replace it with the established site stylesheet path."
            ),
            "expected_improvement": (
                "The affected page can load its intended styling or resource without missing-asset failure."
            ),
            "non_goals": [
                "do not redesign the page",
                "do not change unrelated public files",
                "do not deploy",
                "do not push",
            ],
            "rollback_note": (
                "If a fix is applied later, rollback should restore the previous file or reference exactly."
            ),
            "next_required_artifact": "proposal",
        }

    elif opportunity_type == "missing_capability":
        hypothesis = {
            "hypothesis_id": f"add-{target_family.replace('.', '-')}-v0",
            "hypothesis_type": "design_evolution",
            "user_problem_or_missing_capability": (
                candidate.get("why_this_matters") or "The site lacks an important user experience capability."
            ),
            "proposed_smallest_change": (
                "Create a minimal proposal that adds one clearly marked section or path for the selected capability."
            ),
            "expected_improvement": candidate.get("expected_user_value"),
            "non_goals": [
                "do not broadly redesign the site",
                "do not change deployment settings",
                "do not push",
                "do not deploy",
            ],
            "rollback_note": (
                "Remove the added section or revert the exact controlled delta if validation fails."
            ),
            "next_required_artifact": "proposal",
        }

    else:
        hypothesis = {
            "hypothesis_id": f"improve-{target_family.replace('.', '-')}-v0",
            "hypothesis_type": "experience_improvement",
            "user_problem_or_missing_capability": (
                candidate.get("why_this_matters") or "The user experience can be improved."
            ),
            "proposed_smallest_change": (
                "Create a minimal proposal for improving the selected experience friction."
            ),
            "expected_improvement": candidate.get("expected_user_value"),
            "non_goals": [
                "do not broadly redesign the site",
                "do not push",
                "do not deploy",
            ],
            "rollback_note": (
                "Revert the exact controlled delta if validation fails."
            ),
            "next_required_artifact": "proposal",
        }

    return hypothesis

def main():
    discovery_path = latest_discovery_report()
    if not discovery_path:
        raise SystemExit("NO_DISCOVERY_REPORT_FOUND")

    discovery = load_json(discovery_path, default={}) or {}
    candidate = discovery.get("recommended_candidate")

    if not candidate:
        raise SystemExit("NO_RECOMMENDED_CANDIDATE_FOUND")

    evidence_packet = build_evidence_packet(candidate, discovery_path)
    hypothesis = build_hypothesis(candidate, evidence_packet)

    state = load_json(STATE, default={}) or {}

    payload = {
        "generated_at": now_iso(),
        "builder_id": BUILDER_ID,
        "result": "built",
        "source_discovery_report": str(discovery_path),
        "target_family": candidate.get("target_family"),
        "lane": candidate.get("lane"),
        "opportunity_type": candidate.get("opportunity_type"),
        "criticality": candidate.get("criticality"),
        "recommended_scope": candidate.get("suggested_scope"),
        "current_state": {
            "current_topic": state.get("current_topic"),
            "current_stage": state.get("current_stage"),
            "current_target_family": state.get("current_target_family"),
        },
        "evidence_packet": evidence_packet,
        "hypothesis": hypothesis,
        "policy": {
            "dry_run_only": True,
            "website_files_changed": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
        },
        "recommended_next_stage": "proposal",
    }

    out_json = REPORT_DIR / f"opportunity-evidence-hypothesis-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"opportunity-evidence-hypothesis-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Opportunity Evidence + Hypothesis",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- builder_id: `{BUILDER_ID}`",
        f"- result: `{payload['result']}`",
        f"- source_discovery_report: `{payload['source_discovery_report']}`",
        f"- target_family: `{payload['target_family']}`",
        f"- lane: `{payload['lane']}`",
        f"- opportunity_type: `{payload['opportunity_type']}`",
        f"- criticality: `{payload['criticality']}`",
        f"- recommended_next_stage: `{payload['recommended_next_stage']}`",
        "",
        "## Evidence Packet",
        "",
        f"- evidence_quality: `{evidence_packet.get('evidence_quality')}`",
        f"- current_site_observation: {evidence_packet.get('current_site_observation')}",
        f"- gap_between_current_and_expected: {evidence_packet.get('gap_between_current_and_expected')}",
        "",
    ]

    if evidence_packet.get("missing_assets"):
        lines += [
            "### Missing Assets",
            "",
        ]
        for item in evidence_packet["missing_assets"]:
            lines.append(
                f"- source_file=`{item.get('source_file')}`, tag=`{item.get('tag')}`, ref=`{item.get('ref')}`, normalized_target=`{item.get('normalized_target')}`"
            )
        lines.append("")

    lines += [
        "## Hypothesis",
        "",
        f"- hypothesis_id: `{hypothesis.get('hypothesis_id')}`",
        f"- hypothesis_type: `{hypothesis.get('hypothesis_type')}`",
        "",
        "### User problem or missing capability",
        "",
        hypothesis.get("user_problem_or_missing_capability") or "",
        "",
        "### Proposed smallest change",
        "",
        hypothesis.get("proposed_smallest_change") or "",
        "",
        "### Expected improvement",
        "",
        hypothesis.get("expected_improvement") or "",
        "",
        "### Non-goals",
        "",
    ]

    for item in hypothesis.get("non_goals") or []:
        lines.append(f"- {item}")

    lines += [
        "",
        "## Safety",
        "",
        "- website_files_changed: `false`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
        "- restore_cloudflare_auto_deploy: `false`",
        "",
    ]

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("opportunity_evidence_hypothesis =", payload["result"])
    print("target_family =", payload["target_family"])
    print("lane =", payload["lane"])
    print("opportunity_type =", payload["opportunity_type"])
    print("criticality =", payload["criticality"])
    print("hypothesis_id =", hypothesis.get("hypothesis_id"))
    print("recommended_next_stage =", payload["recommended_next_stage"])
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("website_files_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
