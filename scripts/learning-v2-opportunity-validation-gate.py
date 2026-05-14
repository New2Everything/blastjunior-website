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

GATE_ID = "learning-v2-opportunity-validation-gate-v0.1"
REGISTRY_PATH = BASE / "target-family-registry.json"

ALLOWED_CREATE_FILE_PREFIXES = [
    "public/assets/",
]

FORBIDDEN_PATH_PREFIXES = [
    ".git/",
    "learning-v2/",
    "scripts/",
    "worker/",
    "workers/",
    "node_modules/",
]

FORBIDDEN_EXACT_PATHS = [
    "wrangler.toml",
    "package.json",
    "package-lock.json",
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


def latest_proposal_report():
    files = sorted(
        REPORT_DIR.glob("opportunity-proposal-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None

def path_forbidden(path):
    if path in FORBIDDEN_EXACT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in FORBIDDEN_PATH_PREFIXES)

def path_allowed_for_create(path):
    return any(path.startswith(prefix) for prefix in ALLOWED_CREATE_FILE_PREFIXES)


def validate_event_storytelling_proposal(proposal):
    failures = []
    warnings = []

    proposal_id = proposal.get("proposal_id")
    preferred_option = proposal.get("preferred_option")
    files_to_change = proposal.get("files_to_change") or []
    story_elements = proposal.get("proposed_story_elements") or []
    future_surfaces = proposal.get("candidate_future_surfaces") or []
    validation_plan = proposal.get("validation_plan") or []

    if proposal_id != "proposal-event-storytelling-path-v0":
        warnings.append(f"unexpected_proposal_id:{proposal_id}")

    if preferred_option != "proposal_only_storytelling_path_design":
        failures.append(f"unsupported_preferred_option:{preferred_option}")

    if files_to_change:
        failures.append(f"proposal_only_files_to_change_must_be_empty:{files_to_change}")

    required_story_elements = [
        "event context",
        "turning point",
        "competitive spirit",
        "community proof",
    ]
    for item in required_story_elements:
        if item not in story_elements:
            failures.append(f"missing_story_element:{item}")

    if not future_surfaces:
        failures.append("candidate_future_surfaces_empty")

    required_validation_notes = [
        "proposal-only",
        "does not change website files",
        "no commit, push, or deploy",
        "controlled-change-plan before any website source edit",
    ]

    joined_plan = " | ".join(validation_plan)
    for note in required_validation_notes:
        if note not in joined_plan:
            failures.append(f"validation_plan_missing_note:{note}")

    return failures, warnings


def main():
    proposal_path = latest_proposal_report()
    if not proposal_path:
        raise SystemExit("NO_PROPOSAL_REPORT_FOUND")

    payload = load_json(proposal_path, default={}) or {}
    proposal = payload.get("proposal") or {}

    target_family = payload.get("target_family")
    proposal_id = proposal.get("proposal_id")
    preferred_option = proposal.get("preferred_option")
    files_to_change = proposal.get("files_to_change") or []
    options = proposal.get("options") or []

    failures = []
    warnings = []

    registry, registry_families = load_target_family_registry()
    registry_family = registry_families.get(target_family) or {}
    registry_warnings = []

    if target_family and not registry_family:
        registry_warnings.append(f"target_family_not_in_registry:{target_family}")

    if registry_family and registry_family.get("status") != "supported":
        registry_warnings.append(f"registry_family_not_supported:{target_family}:{registry_family.get('status')}")

    if registry_family and registry_family.get("validation_mode") is None:
        registry_warnings.append(f"registry_validation_mode_missing:{target_family}")

    warnings.extend(registry_warnings)

    if target_family == "event.storytelling_path":
        event_failures, event_warnings = validate_event_storytelling_proposal(proposal)
        failures.extend(event_failures)
        warnings.extend(event_warnings)

    elif target_family == "quality.missing_asset_reference":
        if proposal_id != "proposal-repair-missing-asset-reference-v0":
            warnings.append(f"unexpected_proposal_id:{proposal_id}")

        if preferred_option != "create_missing_asset_at_referenced_path":
            failures.append(f"unsupported_preferred_option:{preferred_option}")

        if not files_to_change:
            failures.append("files_to_change_empty")

        if len(files_to_change) > 3:
            failures.append(f"too_many_files_to_change:{len(files_to_change)}")

        for path in files_to_change:
            if path_forbidden(path):
                failures.append(f"forbidden_path:{path}")
            if not path_allowed_for_create(path):
                failures.append(f"path_not_allowed_for_create:{path}")

            full = WORKSPACE / path
            if full.exists():
                warnings.append(f"target_file_already_exists:{path}")

        if "public/assets/css/site.css" not in files_to_change:
            warnings.append("expected_target_public_assets_css_site_css_not_selected")

        option_ids = [x.get("option_id") for x in options]
        if "create_missing_asset_at_referenced_path" not in option_ids:
            failures.append("required_option_missing:create_missing_asset_at_referenced_path")

    else:
        failures.append(f"unsupported_target_family:{target_family}")

    result = "ok" if not failures else "blocked"
    recommended_next_stage = "controlled_change_plan" if result == "ok" else "proposal_revision"

    out = {
        "generated_at": now_iso(),
        "gate_id": GATE_ID,
        "result": result,
        "source_proposal_report": str(proposal_path),
        "target_family": target_family,
        "registry_family_status": registry_family.get("status"),
        "registry_current_support": registry_family.get("current_support"),
        "registry_type": registry_family.get("type"),
        "registry_lane": registry_family.get("lane"),
        "registry_validation_mode": registry_family.get("validation_mode"),
        "registry_path": str(REGISTRY_PATH),
        "registry_warnings": registry_warnings,
        "proposal_id": proposal_id,
        "preferred_option": preferred_option,
        "files_to_change": files_to_change,
        "failures": failures,
        "warnings": warnings,
        "recommended_next_stage": recommended_next_stage,
        "policy": {
            "dry_run_only": True,
            "website_files_changed": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
        },
    }

    out_json = REPORT_DIR / f"opportunity-validation-gate-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"opportunity-validation-gate-{stamp()}.md"

    out_json.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Opportunity Validation Gate",
        "",
        f"- generated_at: `{out['generated_at']}`",
        f"- gate_id: `{GATE_ID}`",
        f"- result: `{result}`",
        f"- source_proposal_report: `{out['source_proposal_report']}`",
        f"- target_family: `{target_family}`",
        f"- registry_family_status: `{registry_family.get('status')}`",
        f"- registry_current_support: `{registry_family.get('current_support')}`",
        f"- registry_type: `{registry_family.get('type')}`",
        f"- registry_lane: `{registry_family.get('lane')}`",
        f"- registry_validation_mode: `{registry_family.get('validation_mode')}`",
        f"- proposal_id: `{proposal_id}`",
        f"- preferred_option: `{preferred_option}`",
        f"- recommended_next_stage: `{recommended_next_stage}`",
        "",
        "## Files to Change",
        "",
    ]

    if files_to_change:
        for f in files_to_change:
            lines.append(f"- `{f}`")
    else:
        lines.append("- none")

    lines += ["", "## Failures", ""]
    lines += [f"- {f}" for f in failures] if failures else ["- none"]

    lines += ["", "## Warnings", ""]
    lines += [f"- {w}" for w in warnings] if warnings else ["- none"]

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

    print("opportunity_validation_gate =", result)
    print("target_family =", target_family)
    print("registry_family_status =", registry_family.get("status"))
    print("registry_current_support =", registry_family.get("current_support"))
    print("registry_type =", registry_family.get("type"))
    print("registry_lane =", registry_family.get("lane"))
    print("registry_validation_mode =", registry_family.get("validation_mode"))
    print("proposal_id =", proposal_id)
    print("preferred_option =", preferred_option)
    print("files_to_change =", json.dumps(files_to_change, ensure_ascii=False))
    print("recommended_next_stage =", recommended_next_stage)
    print("report_json =", out_json)
    print("report_md =", out_md)
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
    if warnings:
        print("warnings =", json.dumps(warnings, ensure_ascii=False, indent=2))
    print("website_files_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
