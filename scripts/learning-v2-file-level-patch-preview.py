#!/usr/bin/env python3
import argparse
import hashlib
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

SCRIPT_ID = "learning-v2-file-level-patch-preview-v0"

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

def sha256_file(path):
    p = WORKSPACE / path
    if not p.exists() or not p.is_file():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()

def preview_for_file(path, risk):
    if path == "public/index.html":
        return {
            "patch_intent": "Clarify homepage first-success path with minimal content hierarchy changes.",
            "preview_operations": [
                "Identify existing hero / first-screen CTA block.",
                "Prepare copy-only or small markup proposal for primary action clarity.",
                "Connect community and event entry as secondary paths, not competing primary CTAs.",
                "Avoid JS behavior changes in this pass."
            ],
            "rollback_steps": [
                "Restore public/index.html from captured pre-change hash snapshot.",
                "Re-run homepage smoke check.",
                "Confirm no CTA/nav regression."
            ],
            "post_validation": [
                "Homepage renders.",
                "Primary CTA is visible on desktop.",
                "No duplicate first-screen CTA.",
                "No console error introduced."
            ],
        }

    if path == "components/nav.html":
        return {
            "patch_intent": "Review nav support for first-success path without increasing mobile density.",
            "preview_operations": [
                "Inspect existing nav item order and labels.",
                "Prefer label clarification over adding items.",
                "Do not add mobile nav density unless separate mobile evidence allows it."
            ],
            "rollback_steps": [
                "Restore components/nav.html from captured pre-change hash snapshot.",
                "Check desktop and mobile navigation visibility.",
                "Confirm profile/login/gallery links remain reachable."
            ],
            "post_validation": [
                "Nav renders.",
                "No new mobile overflow.",
                "Existing links remain present.",
            ],
        }

    if path == "public/styles.css":
        return {
            "patch_intent": "Only support minimal hierarchy styling if content preview requires it.",
            "preview_operations": [
                "Prefer existing classes.",
                "Avoid broad theme, color, spacing, or layout rewrite.",
                "Do not introduce global CSS changes without isolated selectors."
            ],
            "rollback_steps": [
                "Restore public/styles.css from captured pre-change hash snapshot.",
                "Re-run homepage/gallery/profile visual smoke checks."
            ],
            "post_validation": [
                "Desktop readable.",
                "Mobile readable.",
                "No obvious global layout regression.",
            ],
        }

    if path == "public/gallery.html":
        return {
            "patch_intent": "Defer performance-sensitive gallery edits unless proof-of-activity copy is clearly needed.",
            "preview_operations": [
                "Inspect whether gallery can serve as proof after homepage first action.",
                "Do not touch image loading, lazy loading, tag loading, or performance-sensitive code."
            ],
            "rollback_steps": [
                "Restore public/gallery.html from captured pre-change hash snapshot.",
                "Confirm gallery still loads.",
            ],
            "post_validation": [
                "Gallery opens.",
                "No media loading logic changed.",
                "No poster/gallery performance regression expected.",
            ],
        }

    if path == "public/news.html":
        return {
            "patch_intent": "Decide whether event entry belongs in news or should remain homepage-only.",
            "preview_operations": [
                "Inspect event/news structure.",
                "Avoid adding duplicate event explanation.",
                "Defer if there is no concrete event page target."
            ],
            "rollback_steps": [
                "Restore public/news.html from captured pre-change hash snapshot.",
                "Confirm news page opens."
            ],
            "post_validation": [
                "News page renders.",
                "No broken local link introduced.",
            ],
        }

    if path == "public/profile.html":
        return {
            "patch_intent": "Likely exclude profile from first-success path because it may depend on auth/session.",
            "preview_operations": [
                "Inspect whether profile belongs in first-success path.",
                "Avoid auth/session/localStorage changes.",
                "Defer unless evidence proves profile is part of onboarding."
            ],
            "rollback_steps": [
                "Restore public/profile.html from captured pre-change hash snapshot.",
                "Confirm profile/auth behavior unchanged."
            ],
            "post_validation": [
                "Profile page opens.",
                "No token/localStorage behavior changed.",
                "No auth regression expected.",
            ],
        }

    return {
        "patch_intent": "Inspect only; no patch preview available.",
        "preview_operations": ["Inspect file before any source-change gate."],
        "rollback_steps": ["Restore file from captured pre-change hash snapshot."],
        "post_validation": ["No write performed."],
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is report-only and never edits website source.")
    args = ap.parse_args()

    readiness_path = latest_report("learning-v2-source-change-gate-readiness-dry-run-*.json")
    plan_path = latest_report("learning-v2-source-change-plan-dry-run-*.json")

    if not readiness_path:
        raise SystemExit("no source-change gate readiness report found")
    if not plan_path:
        raise SystemExit("no source-change plan dry-run report found")

    readiness = load_json(readiness_path, {})
    plan = load_json(plan_path, {})

    if readiness.get("readiness_status") != "patch_preview_required_before_gate":
        raise SystemExit("gate readiness is not requesting patch preview")
    if readiness.get("source_change_gate_allowed") is not False:
        raise SystemExit("unexpected: gate readiness allows source_change_gate too early")

    file_plans = plan.get("file_plans") or []
    previews = []
    hard_blocks = []
    warnings = []

    for fp in file_plans:
        info = fp.get("file") or {}
        plan_info = fp.get("plan") or {}
        path = info.get("path")
        exists = info.get("exists")
        old_hash = info.get("sha256") or sha256_file(path)
        risk = plan_info.get("risk")

        if not path:
            hard_blocks.append("file_plan_missing_path")
            continue
        if exists is not True:
            hard_blocks.append(f"{path}:file_missing")
        if not old_hash:
            hard_blocks.append(f"{path}:missing_pre_change_hash")

        preview = preview_for_file(path, risk)
        if risk in ("medium", "medium-high", "high"):
            warnings.append(f"{path}:patch_preview_requires_later_audit_before_gate")
        if path in ("public/index.html", "components/nav.html"):
            warnings.append(f"{path}:sensitive_surface_requires_snapshot_or_mobile_validation")

        previews.append({
            "path": path,
            "exists": exists,
            "pre_change_sha256": old_hash,
            "risk": risk,
            "linked_targets": fp.get("linked_targets") or [],
            "patch_intent": preview["patch_intent"],
            "preview_operations": preview["preview_operations"],
            "rollback_steps": preview["rollback_steps"],
            "post_validation": preview["post_validation"],
            "actual_file_written": False,
            "source_change_gate_allowed": False,
        })

    if not previews:
        hard_blocks.append("no_patch_previews_created")

    by_risk = Counter(x.get("risk") for x in previews)

    if hard_blocks:
        preview_status = "blocked"
        recommended_next_action = "fix_patch_preview_before_gate"
        patch_preview_audit_allowed = False
    else:
        preview_status = "patch_preview_ready_for_audit"
        recommended_next_action = "run_patch_preview_auditor_before_any_source_change_gate"
        patch_preview_audit_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "gate_readiness_source": str(readiness_path),
        "source_change_plan_source": str(plan_path),
        "preview_status": preview_status,
        "recommended_next_action": recommended_next_action,
        "patch_preview_count": len(previews),
        "by_risk": dict(by_risk),
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "patch_previews": previews,
        "patch_preview_audit_allowed": patch_preview_audit_allowed,
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
    json_path = REPORT_DIR / f"learning-v2-file-level-patch-preview-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-file-level-patch-preview-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 File-Level Patch Preview Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- preview_status: `{preview_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- patch_preview_count: `{len(previews)}`")
    md.append(f"- patch_preview_audit_allowed: `{str(patch_preview_audit_allowed).lower()}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Patch Previews")
    md.append("")
    for p in previews:
        md.append(f"### {p['path']}")
        md.append("")
        md.append(f"- pre_change_sha256: `{p['pre_change_sha256']}`")
        md.append(f"- risk: `{p['risk']}`")
        md.append(f"- patch_intent: {p['patch_intent']}")
        md.append("- preview_operations:")
        for x in p["preview_operations"]:
            md.append(f"  - {x}")
        md.append("- rollback_steps:")
        for x in p["rollback_steps"]:
            md.append(f"  - {x}")
        md.append("- post_validation:")
        for x in p["post_validation"]:
            md.append(f"  - {x}")
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
    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("file_level_patch_preview = ok")
    print("mode = dry_run")
    print("preview_status =", preview_status)
    print("recommended_next_action =", recommended_next_action)
    print("patch_preview_count =", len(previews))
    print("patch_preview_audit_allowed =", str(patch_preview_audit_allowed).lower())
    print("by_risk =", json.dumps(dict(by_risk), ensure_ascii=False))
    print("hard_blocks =", json.dumps(hard_blocks, ensure_ascii=False))
    print("warnings =", json.dumps(warnings, ensure_ascii=False))
    print("source_change_gate_allowed = false")
    print("source_change_gate_opened = false")
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
