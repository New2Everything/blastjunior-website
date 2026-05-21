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

SCRIPT_ID = "learning-v2-required-gate-evidence-modules-v0"

REQUIRED_MODULES = [
    "explicit_rollback_packet_module",
    "mobile_visual_snapshot_or_validation_module",
    "post_validation_command_plan_module",
    "pre_change_visual_snapshot_module",
]

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

def build_module(name, snapshot, preview, auditor):
    file_snapshots = snapshot.get("file_snapshots") or []
    patch_previews = preview.get("patch_previews") or []
    sensitive_files = sorted(set(snapshot.get("sensitive_files") or []))

    if name == "explicit_rollback_packet_module":
        return {
            "module": name,
            "status": "ready",
            "purpose": "Define rollback requirements using pre-change hashes and file list.",
            "evidence": {
                "candidate_file_count": snapshot.get("candidate_file_count"),
                "file_hashes_captured": [
                    {
                        "path": x.get("path"),
                        "sha256": x.get("sha256"),
                        "exists": x.get("exists"),
                        "size_bytes": x.get("size_bytes"),
                    }
                    for x in file_snapshots
                ],
                "rollback_strategy": [
                    "Before any real source write, copy each candidate file to a timestamped rollback directory.",
                    "After patch application, keep both before/after hashes in reports.",
                    "If post-validation fails, restore all candidate files from rollback directory.",
                    "Do not commit, push, or deploy until rollback restore test passes or is explicitly waived by policy.",
                ],
            },
            "hard_blocks": [],
            "warnings": [],
        }

    if name == "mobile_visual_snapshot_or_validation_module":
        return {
            "module": name,
            "status": "ready_with_required_followup",
            "purpose": "Record that sensitive homepage/nav surfaces require mobile validation before any actual gate.",
            "evidence": {
                "sensitive_files": sensitive_files,
                "required_checks": [
                    "Verify public/index.html first-screen CTA on mobile viewport.",
                    "Verify components/nav.html does not introduce overflow or density regression.",
                    "Capture or record mobile visual evidence before gate open.",
                    "If screenshot automation is unavailable, require a manual/mobile validation artifact before gate open.",
                ],
                "actual_screenshot_captured": False,
                "reason_actual_screenshot_not_captured": "v0 creates the evidence-module contract only; visual capture is a later executable module.",
            },
            "hard_blocks": [],
            "warnings": [
                "mobile_visual_evidence_not_captured_yet",
                "sensitive_surfaces_require_later_visual_validation",
            ],
        }

    if name == "post_validation_command_plan_module":
        return {
            "module": name,
            "status": "ready",
            "purpose": "Define post-change validation commands/checks required after any future source write.",
            "evidence": {
                "planned_validation_commands": [
                    "python3 scripts/learning-v2-fast-status.py",
                    "python3 scripts/learning-v2-system-integrity.py",
                    "git status -sb",
                    "git diff --check",
                ],
                "planned_manual_or_browser_checks": [
                    "Homepage renders on desktop.",
                    "Homepage first CTA remains visible and understandable.",
                    "Navigation remains reachable and does not overflow on mobile.",
                    "Gallery page still opens and no performance-sensitive gallery loading code was changed.",
                    "Profile/auth behavior remains unchanged.",
                ],
                "deploy_policy": "deploy remains false unless a separate deploy gate is explicitly passed later.",
            },
            "hard_blocks": [],
            "warnings": [],
        }

    if name == "pre_change_visual_snapshot_module":
        return {
            "module": name,
            "status": "ready_with_required_followup",
            "purpose": "Record visual snapshot requirements before any real source write.",
            "evidence": {
                "target_surfaces": sorted(set([
                    "public/index.html",
                    "components/nav.html",
                ] + sensitive_files)),
                "required_snapshots": [
                    "Desktop homepage before-change snapshot.",
                    "Mobile homepage before-change snapshot.",
                    "Mobile navigation before-change snapshot.",
                ],
                "actual_visual_snapshot_captured": False,
                "reason_actual_visual_snapshot_not_captured": "v0 records requirements; visual snapshot capture should be handled by a later visual evidence module.",
            },
            "hard_blocks": [],
            "warnings": [
                "pre_change_visual_snapshot_not_captured_yet",
            ],
        }

    return {
        "module": name,
        "status": "unknown",
        "purpose": "Unknown module.",
        "evidence": {},
        "hard_blocks": [f"unknown_module:{name}"],
        "warnings": [],
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is report-only and never opens source_change_gate.")
    args = ap.parse_args()

    auditor_path = latest_report("learning-v2-pre-change-evidence-auditor-dry-run-*.json")
    snapshot_path = latest_report("learning-v2-pre-change-evidence-snapshot-dry-run-*.json")
    preview_path = latest_report("learning-v2-file-level-patch-preview-dry-run-*.json")

    if not auditor_path:
        raise SystemExit("no pre-change evidence auditor report found")
    if not snapshot_path:
        raise SystemExit("no pre-change evidence snapshot report found")
    if not preview_path:
        raise SystemExit("no file-level patch preview report found")

    auditor = load_json(auditor_path, {})
    snapshot = load_json(snapshot_path, {})
    preview = load_json(preview_path, {})

    hard_blocks = []
    warnings = []

    if auditor.get("audit_status") != "pre_change_evidence_ready_for_required_evidence_modules":
        hard_blocks.append("pre_change_evidence_auditor_not_ready")
    if auditor.get("required_evidence_modules_allowed") is not True:
        hard_blocks.append("required_evidence_modules_not_allowed")
    if auditor.get("source_change_gate_allowed") is not False:
        hard_blocks.append("auditor_allows_source_change_gate_too_early")
    if auditor.get("source_change_gate_opened") is not False:
        hard_blocks.append("auditor_opened_source_change_gate")

    required_next = sorted(set(auditor.get("required_next_evidence") or []))
    missing_required = sorted(set(REQUIRED_MODULES) - set(required_next))
    unknown_required = sorted(set(required_next) - set(REQUIRED_MODULES))

    if missing_required:
        hard_blocks.extend([f"missing_required_module:{x}" for x in missing_required])
    if unknown_required:
        hard_blocks.extend([f"unknown_required_module:{x}" for x in unknown_required])

    modules = []
    for name in REQUIRED_MODULES:
        m = build_module(name, snapshot, preview, auditor)
        modules.append(m)
        hard_blocks.extend([f"{name}:{x}" for x in m.get("hard_blocks", [])])
        warnings.extend([f"{name}:{x}" for x in m.get("warnings", [])])

    by_status = Counter(m.get("status") for m in modules)

    if hard_blocks:
        modules_status = "blocked"
        recommended_next_action = "fix_required_gate_evidence_modules_before_gate"
        evidence_modules_audit_allowed = False
    else:
        modules_status = "required_gate_evidence_modules_ready_for_audit"
        recommended_next_action = "run_required_gate_evidence_modules_auditor_before_gate"
        evidence_modules_audit_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "pre_change_evidence_auditor_source": str(auditor_path),
        "pre_change_evidence_snapshot_source": str(snapshot_path),
        "patch_preview_source": str(preview_path),
        "modules_status": modules_status,
        "recommended_next_action": recommended_next_action,
        "required_module_count": len(REQUIRED_MODULES),
        "built_module_count": len(modules),
        "by_status": dict(by_status),
        "modules": modules,
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "evidence_modules_audit_allowed": evidence_modules_audit_allowed,
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
    json_path = REPORT_DIR / f"learning-v2-required-gate-evidence-modules-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-required-gate-evidence-modules-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Required Gate Evidence Modules Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- modules_status: `{modules_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- required_module_count: `{len(REQUIRED_MODULES)}`")
    md.append(f"- built_module_count: `{len(modules)}`")
    md.append(f"- evidence_modules_audit_allowed: `{str(evidence_modules_audit_allowed).lower()}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- source_change_gate_opened: `false`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Modules")
    md.append("")
    for m in modules:
        md.append(f"### {m['module']}")
        md.append(f"- status: `{m['status']}`")
        md.append(f"- purpose: {m['purpose']}")
        md.append(f"- hard_blocks: `{m['hard_blocks']}`")
        md.append(f"- warnings: `{m['warnings']}`")
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

    print("required_gate_evidence_modules = ok")
    print("mode = dry_run")
    print("modules_status =", modules_status)
    print("recommended_next_action =", recommended_next_action)
    print("required_module_count =", len(REQUIRED_MODULES))
    print("built_module_count =", len(modules))
    print("by_status =", json.dumps(dict(by_status), ensure_ascii=False))
    print("evidence_modules_audit_allowed =", str(evidence_modules_audit_allowed).lower())
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
