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

GATE_ID = "learning-v2-opportunity-validation-gate-v0"

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

    if target_family != "quality.missing_asset_reference":
        failures.append(f"unsupported_target_family:{target_family}")

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

    result = "ok" if not failures else "blocked"
    recommended_next_stage = "controlled_change_plan" if result == "ok" else "proposal_revision"

    out = {
        "generated_at": now_iso(),
        "gate_id": GATE_ID,
        "result": result,
        "source_proposal_report": str(proposal_path),
        "target_family": target_family,
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
