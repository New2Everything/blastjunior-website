#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

BUILDER_ID = "learning-v2-opportunity-proposal-builder-v0.1"
REGISTRY_PATH = BASE / "target-family-registry.json"

CSS_CANDIDATES = [
    "public/assets/css/site.css",
    "assets/css/site.css",
    "public/styles.css",
    "public/nav.css",
    "components/nav.css",
]

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


def load_target_family_registry():
    registry = load_json(REGISTRY_PATH, default={}) or {}
    families = registry.get("families") or {}
    return registry, families


def latest_evidence_report():
    files = sorted(
        REPORT_DIR.glob("opportunity-evidence-hypothesis-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None

def path_exists(rel):
    return (WORKSPACE / rel).exists()

def inspect_css_candidates():
    return [
        {
            "path": rel,
            "exists": path_exists(rel),
        }
        for rel in CSS_CANDIDATES
    ]

def build_missing_asset_proposal(evidence_payload):
    evidence_packet = evidence_payload.get("evidence_packet") or {}
    hypothesis = evidence_payload.get("hypothesis") or {}
    missing_assets = evidence_packet.get("missing_assets") or []
    css_inventory = inspect_css_candidates()

    target_paths = []
    for item in missing_assets:
        target = item.get("normalized_target")
        if target and target not in target_paths:
            target_paths.append(target)

    source_files = []
    for item in missing_assets:
        source = item.get("source_file")
        if source and source not in source_files:
            source_files.append(source)

    preferred_option = None
    options = []

    # Option A: create the exact missing normalized asset.
    if target_paths:
        options.append({
            "option_id": "create_missing_asset_at_referenced_path",
            "change_type": "create_file",
            "files_to_change": target_paths,
            "summary": "Create the missing asset at the exact path already referenced by the page.",
            "pros": [
                "Does not require changing the page reference.",
                "Directly satisfies the current asset path.",
                "Easy to validate by checking file existence and rerunning discovery.",
            ],
            "risks": [
                "A new stylesheet may duplicate existing style rules if not aligned with current site CSS.",
                "Must ensure the created CSS is minimal and safe.",
            ],
        })

    # Option B: change the page reference to an existing stylesheet.
    existing_css = [x["path"] for x in css_inventory if x["exists"]]
    if existing_css and source_files:
        options.append({
            "option_id": "change_reference_to_existing_stylesheet",
            "change_type": "edit_file",
            "files_to_change": source_files,
            "summary": "Change the missing stylesheet reference to an existing local stylesheet.",
            "existing_stylesheet_candidates": existing_css,
            "pros": [
                "Reuses an existing stylesheet.",
                "May avoid creating a new CSS file.",
            ],
            "risks": [
                "Changing the reference may diverge from the intended global stylesheet path.",
                "Must verify that the existing stylesheet provides the intended layout.",
            ],
        })

    # Option C: no source edit; mark as accepted if served externally by platform.
    options.append({
        "option_id": "defer_if_asset_served_outside_repo",
        "change_type": "no_source_change",
        "files_to_change": [],
        "summary": "Only valid if the asset is intentionally served outside this repository.",
        "pros": [
            "Avoids unnecessary source change if runtime hosting provides the file.",
        ],
        "risks": [
            "Current repository scan cannot verify the asset.",
            "Should not be accepted without runtime proof.",
        ],
    })

    # Current recommendation:
    # If the referenced normalized target is missing and no exact file exists,
    # prefer creating the missing file at the referenced path.
    if target_paths:
        preferred_option = "create_missing_asset_at_referenced_path"
    elif existing_css:
        preferred_option = "change_reference_to_existing_stylesheet"
    else:
        preferred_option = "needs_human_review"

    proposal = {
        "proposal_id": "proposal-repair-missing-asset-reference-v0",
        "target_family": evidence_payload.get("target_family"),
        "lane": evidence_payload.get("lane"),
        "opportunity_type": evidence_payload.get("opportunity_type"),
        "criticality": evidence_payload.get("criticality"),
        "hypothesis_id": hypothesis.get("hypothesis_id"),
        "proposal_type": "repair",
        "preferred_option": preferred_option,
        "files_to_change": target_paths if preferred_option == "create_missing_asset_at_referenced_path" else source_files,
        "intended_markers": [
            "quality.missing_asset_reference resolved",
            "missing_asset_count becomes 0 or no longer includes the repaired asset",
        ],
        "user_facing_copy": [],
        "structure_change_summary": "No page redesign. Only repair the missing asset reference path or its target.",
        "validation_plan": [
            "Run design-opportunity-discoverer again.",
            "Confirm quality.missing_asset_reference is resolved or reduced.",
            "Confirm no new quality.broken_internal_links candidate appears.",
            "Run system_integrity.",
            "Do not push or deploy during this proposal stage.",
        ],
        "risk_classification": "low_to_medium",
        "options": options,
        "css_inventory": css_inventory,
        "non_goals": [
            "do not redesign public/about.html",
            "do not change gallery.html or news.html",
            "do not deploy",
            "do not push",
            "do not restore Cloudflare production auto-deploy",
        ],
    }

    return proposal


def build_event_storytelling_proposal(evidence_payload):
    hypothesis = evidence_payload.get("hypothesis") or {}
    return {
        "proposal_id": "proposal-event-storytelling-path-v0",
        "target_family": "event.storytelling_path",
        "lane": evidence_payload.get("lane"),
        "opportunity_type": evidence_payload.get("opportunity_type"),
        "criticality": evidence_payload.get("criticality"),
        "hypothesis_id": hypothesis.get("hypothesis_id"),
        "proposal_type": "design_capability_proposal",
        "preferred_option": "proposal_only_storytelling_path_design",
        "files_to_change": [],
        "capability_intent": "Create a future event storytelling path that turns competitions into emotional proof of club value.",
        "target_user_value": "Visitors should feel competitive spirit, community identity, and why events matter.",
        "proposed_story_elements": [
            "event context",
            "team or player challenge",
            "turning point",
            "competitive spirit",
            "community proof",
            "next action after reading"
        ],
        "candidate_future_surfaces": [
            "public/news.html",
            "a future dedicated event story section",
            "a future story card component"
        ],
        "validation_plan": [
            "Validate that this is proposal-only and does not change website files.",
            "Validate that files_to_change is empty at this stage.",
            "Validate that candidate_future_surfaces are suggestions, not approved edits.",
            "Validate that no commit, push, or deploy is requested.",
            "Require a later controlled-change-plan before any website source edit."
        ],
        "risk_classification": "medium_design_scope",
        "non_goals": [
            "do not edit public files in proposal stage",
            "do not choose final placement yet",
            "do not generate final marketing copy yet",
            "do not push",
            "do not deploy",
            "do not restore Cloudflare production auto-deploy"
        ],
    }


def main():
    evidence_path = latest_evidence_report()
    if not evidence_path:
        raise SystemExit("NO_EVIDENCE_HYPOTHESIS_REPORT_FOUND")

    evidence_payload = load_json(evidence_path, default={}) or {}
    target_family = evidence_payload.get("target_family")

    registry, registry_families = load_target_family_registry()
    registry_family = registry_families.get(target_family) or {}
    registry_warnings = []

    if target_family and not registry_family:
        registry_warnings.append(f"target_family_not_in_registry:{target_family}")

    if registry_family and registry_family.get("status") not in ["supported", "candidate"]:
        registry_warnings.append(f"unexpected_registry_family_status:{registry_family.get('status')}")

    if target_family == "quality.missing_asset_reference":
        proposal = build_missing_asset_proposal(evidence_payload)
    elif target_family == "event.storytelling_path":
        proposal = build_event_storytelling_proposal(evidence_payload)
    else:
        proposal = {
            "proposal_id": f"proposal-{target_family}-v0",
            "target_family": target_family,
            "proposal_type": "generic",
            "preferred_option": "needs_specific_builder",
            "files_to_change": [],
            "validation_plan": [
                "Add target-specific proposal builder before applying source changes."
            ],
            "non_goals": [
                "do not push",
                "do not deploy",
            ],
        }

    proposal["registry_family_status"] = registry_family.get("status")
    proposal["registry_current_support"] = registry_family.get("current_support")
    proposal["registry_type"] = registry_family.get("type")
    proposal["registry_lane"] = registry_family.get("lane")

    payload = {
        "generated_at": now_iso(),
        "builder_id": BUILDER_ID,
        "result": "built",
        "source_evidence_report": str(evidence_path),
        "target_family": target_family,
        "registry_family_status": registry_family.get("status"),
        "registry_current_support": registry_family.get("current_support"),
        "registry_type": registry_family.get("type"),
        "registry_lane": registry_family.get("lane"),
        "registry_path": str(REGISTRY_PATH),
        "registry_warnings": registry_warnings,
        "proposal": proposal,
        "policy": {
            "dry_run_only": True,
            "website_files_changed": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
        },
        "recommended_next_stage": "validation_gate",
    }

    out_json = REPORT_DIR / f"opportunity-proposal-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"opportunity-proposal-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Opportunity Proposal",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- builder_id: `{BUILDER_ID}`",
        f"- result: `{payload['result']}`",
        f"- source_evidence_report: `{payload['source_evidence_report']}`",
        f"- target_family: `{target_family}`",
        f"- registry_family_status: `{registry_family.get('status')}`",
        f"- registry_current_support: `{registry_family.get('current_support')}`",
        f"- registry_type: `{registry_family.get('type')}`",
        f"- registry_lane: `{registry_family.get('lane')}`",
        f"- proposal_id: `{proposal.get('proposal_id')}`",
        f"- proposal_type: `{proposal.get('proposal_type')}`",
        f"- preferred_option: `{proposal.get('preferred_option')}`",
        f"- recommended_next_stage: `{payload['recommended_next_stage']}`",
        "",
        "## Files to Change",
        "",
    ]

    files = proposal.get("files_to_change") or []
    if files:
        for f in files:
            lines.append(f"- `{f}`")
    else:
        lines.append("- none")

    lines += [
        "",
        "## CSS Inventory",
        "",
    ]

    for item in proposal.get("css_inventory") or []:
        lines.append(f"- `{item['path']}` exists=`{str(item['exists']).lower()}`")

    lines += [
        "",
        "## Options",
        "",
    ]

    for opt in proposal.get("options") or []:
        lines.append(f"### {opt.get('option_id')}")
        lines.append("")
        lines.append(f"- change_type: `{opt.get('change_type')}`")
        lines.append(f"- summary: {opt.get('summary')}")
        lines.append("")

    lines += [
        "## Validation Plan",
        "",
    ]

    for item in proposal.get("validation_plan") or []:
        lines.append(f"- {item}")

    lines += [
        "",
        "## Non-goals",
        "",
    ]

    for item in proposal.get("non_goals") or []:
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

    print("opportunity_proposal =", payload["result"])
    print("target_family =", target_family)
    print("registry_family_status =", registry_family.get("status"))
    print("registry_current_support =", registry_family.get("current_support"))
    print("registry_type =", registry_family.get("type"))
    print("registry_lane =", registry_family.get("lane"))
    print("proposal_id =", proposal.get("proposal_id"))
    print("preferred_option =", proposal.get("preferred_option"))
    print("files_to_change =", json.dumps(proposal.get("files_to_change"), ensure_ascii=False))
    print("recommended_next_stage =", payload["recommended_next_stage"])
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("website_files_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
