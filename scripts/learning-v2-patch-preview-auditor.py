#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-patch-preview-auditor-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    if default is None:
        default = {}
    try:
        p = Path(path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_load_error": str(e), "_path": str(path)}
    return default

def latest_report(pattern):
    files = sorted(REPORT_DIR.glob(pattern))
    return files[-1] if files else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is report-only and never opens source_change_gate.")
    args = ap.parse_args()

    preview_path = latest_report("learning-v2-file-level-patch-preview-dry-run-*.json")
    if not preview_path:
        raise SystemExit("no file-level patch preview report found")

    preview = load_json(preview_path, {})
    safety = preview.get("safety") or {}
    patches = preview.get("patch_previews") or []

    hard_blocks = []
    warnings = list(preview.get("warnings") or [])

    if preview.get("preview_status") != "patch_preview_ready_for_audit":
        hard_blocks.append("preview_status_not_ready_for_audit")
    if preview.get("patch_preview_audit_allowed") is not True:
        hard_blocks.append("patch_preview_audit_not_allowed")
    if preview.get("source_change_gate_allowed") is not False:
        hard_blocks.append("source_change_gate_allowed_too_early")
    if preview.get("source_change_gate_opened") is not False:
        hard_blocks.append("source_change_gate_opened_too_early")
    if safety.get("website_source_written") is not False:
        hard_blocks.append("safety_does_not_confirm_no_website_write")
    if safety.get("source_change_gate_opened") is not False:
        hard_blocks.append("safety_does_not_confirm_gate_closed")
    if safety.get("deploy") is not False:
        hard_blocks.append("safety_does_not_confirm_no_deploy")
    if not patches:
        hard_blocks.append("no_patch_previews_found")

    audited_patches = []

    for p in patches:
        path = p.get("path")
        file_blocks = []
        file_warnings = []

        if not path:
            file_blocks.append("missing_path")
        if not p.get("pre_change_sha256"):
            file_blocks.append("missing_pre_change_hash")
        if not p.get("patch_intent"):
            file_blocks.append("missing_patch_intent")
        if not p.get("preview_operations"):
            file_blocks.append("missing_preview_operations")
        if not p.get("rollback_steps"):
            file_blocks.append("missing_rollback_steps")
        if not p.get("post_validation"):
            file_blocks.append("missing_post_validation")
        if p.get("actual_file_written") is not False:
            file_blocks.append("actual_file_written_not_false")
        if p.get("source_change_gate_allowed") is not False:
            file_blocks.append("patch_allows_source_change_gate_too_early")

        if p.get("risk") in ("medium", "medium-high", "high"):
            file_warnings.append("medium_or_higher_risk_requires_gate_policy_review")
        if path in ("public/index.html", "components/nav.html"):
            file_warnings.append("sensitive_surface_requires_snapshot_or_mobile_validation_before_actual_gate")

        audited_patches.append({
            "path": path,
            "risk": p.get("risk"),
            "hard_blocks": file_blocks,
            "warnings": file_warnings,
        })

        hard_blocks.extend([f"{path}:{x}" for x in file_blocks])
        warnings.extend([f"{path}:{x}" for x in file_warnings])

    by_risk = Counter(p.get("risk") for p in patches)

    if hard_blocks:
        audit_status = "blocked"
        recommended_next_action = "fix_patch_preview_before_gate_policy"
        gate_policy_review_allowed = False
    else:
        audit_status = "patch_preview_ready_for_gate_policy_review"
        recommended_next_action = "run_source_change_gate_open_policy_dry_run"
        gate_policy_review_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "patch_preview_source": str(preview_path),
        "audit_status": audit_status,
        "recommended_next_action": recommended_next_action,
        "patch_preview_count": len(patches),
        "by_risk": dict(by_risk),
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "audited_patches": audited_patches,
        "gate_policy_review_allowed": gate_policy_review_allowed,
        "source_change_gate_allowed": False,
        "source_change_gate_opened": False,
        "safety": {
            "state_written": False,
            "business_source_written": False,
            "website_source_written": False,
            "source_change_gate_opened": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
    }

    ts = stamp()
    json_path = REPORT_DIR / f"learning-v2-patch-preview-auditor-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-patch-preview-auditor-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Patch Preview Auditor Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- audit_status: `{audit_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- gate_policy_review_allowed: `{str(gate_policy_review_allowed).lower()}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- source_change_gate_opened: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Hard Blocks")
    md.append("")
    if hard_blocks:
        for x in hard_blocks:
            md.append(f"- {x}")
    else:
        md.append("- none")
    md.append("")
    md.append("## Warnings")
    md.append("")
    if warnings:
        for x in warnings:
            md.append(f"- {x}")
    else:
        md.append("- none")
    md.append("")
    md.append("## Audited Patches")
    md.append("")
    for x in audited_patches:
        md.append(f"### {x['path']}")
        md.append(f"- risk: `{x['risk']}`")
        md.append(f"- hard_blocks: `{x['hard_blocks']}`")
        md.append(f"- warnings: `{x['warnings']}`")
        md.append("")
    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("patch_preview_auditor = ok")
    print("mode = dry_run")
    print("audit_status =", audit_status)
    print("recommended_next_action =", recommended_next_action)
    print("patch_preview_source =", preview_path)
    print("patch_preview_count =", len(patches))
    print("gate_policy_review_allowed =", str(gate_policy_review_allowed).lower())
    print("source_change_gate_allowed = false")
    print("source_change_gate_opened = false")
    print("hard_blocks =", json.dumps(hard_blocks, ensure_ascii=False))
    print("warnings =", json.dumps(warnings, ensure_ascii=False))
    print("state_written = false")
    print("business_source_written = false")
    print("website_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("report_json =", json_path)
    print("report_md =", md_path)

if __name__ == "__main__":
    raise SystemExit(main())
