#!/usr/bin/env python3
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-final-source-change-gate-auditor-v0"

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

def run_cmd(args):
    p = subprocess.run(
        args,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return {
        "args": args,
        "returncode": p.returncode,
        "output": p.stdout.strip(),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is report-only and never opens source_change_gate.")
    args = ap.parse_args()

    modules_auditor_path = latest_report("learning-v2-required-gate-evidence-modules-auditor-dry-run-*.json")
    modules_path = latest_report("learning-v2-required-gate-evidence-modules-dry-run-*.json")
    snapshot_path = latest_report("learning-v2-pre-change-evidence-snapshot-dry-run-*.json")
    preview_path = latest_report("learning-v2-file-level-patch-preview-dry-run-*.json")
    browser_visual_auditor_path = latest_report("learning-v2-browser-visual-capture-auditor-dry-run-*.json")

    if not modules_auditor_path:
        raise SystemExit("no required gate evidence modules auditor report found")
    if not modules_path:
        raise SystemExit("no required gate evidence modules report found")
    if not snapshot_path:
        raise SystemExit("no pre-change evidence snapshot report found")
    if not preview_path:
        raise SystemExit("no file-level patch preview report found")

    modules_auditor = load_json(modules_auditor_path, {})
    modules_report = load_json(modules_path, {})
    snapshot = load_json(snapshot_path, {})
    preview = load_json(preview_path, {})
    browser_visual_auditor = load_json(browser_visual_auditor_path, {}) if browser_visual_auditor_path else {}

    hard_blocks = []
    warnings = []
    pending_required_evidence = []

    if modules_auditor.get("audit_status") != "required_gate_evidence_modules_ready_for_final_gate_auditor":
        hard_blocks.append("required_gate_evidence_modules_auditor_not_ready")
    if modules_auditor.get("final_gate_auditor_allowed") is not True:
        hard_blocks.append("final_gate_auditor_not_allowed")
    if modules_auditor.get("source_change_gate_allowed") is not False:
        hard_blocks.append("modules_auditor_allows_gate_too_early")
    if modules_auditor.get("source_change_gate_opened") is not False:
        hard_blocks.append("modules_auditor_opened_gate")

    if modules_report.get("modules_status") != "required_gate_evidence_modules_ready_for_audit":
        hard_blocks.append("required_gate_evidence_modules_not_ready")
    if modules_report.get("source_change_gate_allowed") is not False:
        hard_blocks.append("modules_report_allows_gate_too_early")

    if snapshot.get("snapshot_status") != "pre_change_evidence_snapshot_ready_for_audit":
        hard_blocks.append("pre_change_snapshot_not_ready")
    if preview.get("preview_status") != "patch_preview_ready_for_audit":
        hard_blocks.append("patch_preview_not_ready")

    visual_evidence_confirmed = (
        browser_visual_auditor.get("audit_status") == "browser_visual_capture_ready_for_final_gate_recheck"
        and browser_visual_auditor.get("visual_evidence_confirmed") is True
        and browser_visual_auditor.get("final_gate_recheck_allowed") is True
        and browser_visual_auditor.get("source_change_gate_allowed") is False
    )

    modules = modules_report.get("modules") or []
    for m in modules:
        name = m.get("module")
        status = m.get("status")
        evidence = m.get("evidence") or {}

        if status == "ready_with_required_followup" and not visual_evidence_confirmed:
            pending_required_evidence.append(f"{name}:required_followup_not_completed")

        if name == "mobile_visual_snapshot_or_validation_module":
            if evidence.get("actual_screenshot_captured") is not True and not visual_evidence_confirmed:
                pending_required_evidence.append("mobile_visual_snapshot_or_validation_module:actual_screenshot_not_captured")

        if name == "pre_change_visual_snapshot_module":
            if evidence.get("actual_visual_snapshot_captured") is not True and not visual_evidence_confirmed:
                pending_required_evidence.append("pre_change_visual_snapshot_module:actual_visual_snapshot_not_captured")

    warnings.extend(modules_auditor.get("warnings") or [])
    warnings.extend(modules_report.get("warnings") or [])

    fast_status = run_cmd(["python3", "scripts/learning-v2-fast-status.py"])
    git_status = run_cmd(["git", "status", "-sb"])

    if fast_status["returncode"] != 0:
        hard_blocks.append("fast_status_returned_nonzero")

    if "learning_v2_fast_status = ok" not in fast_status.get("output", ""):
        hard_blocks.append("fast_status_not_ok")

    if "deploy = true" in fast_status.get("output", ""):
        hard_blocks.append("fast_status_indicates_deploy_true")

    if pending_required_evidence:
        audit_status = "gate_blocked_pending_visual_evidence"
        recommended_next_action = "build_visual_evidence_capture_or_validation_dry_run"
        gate_open_allowed = False
        visual_evidence_required = True
    elif hard_blocks:
        audit_status = "blocked"
        recommended_next_action = "fix_final_gate_auditor_inputs_before_gate"
        gate_open_allowed = False
        visual_evidence_required = False
    else:
        audit_status = "gate_open_candidate_ready_but_not_opened"
        recommended_next_action = "run_source_change_gate_open_request_dry_run"
        gate_open_allowed = False
        visual_evidence_required = False

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "required_gate_evidence_modules_auditor_source": str(modules_auditor_path),
        "required_gate_evidence_modules_source": str(modules_path),
        "pre_change_evidence_snapshot_source": str(snapshot_path),
        "patch_preview_source": str(preview_path),
        "browser_visual_capture_auditor_source": str(browser_visual_auditor_path) if browser_visual_auditor_path else None,
        "visual_evidence_confirmed": visual_evidence_confirmed,
        "audit_status": audit_status,
        "recommended_next_action": recommended_next_action,
        "pending_required_evidence": sorted(set(pending_required_evidence)),
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "visual_evidence_required": visual_evidence_required,
        "gate_open_allowed": gate_open_allowed,
        "source_change_gate_allowed": False,
        "source_change_gate_opened": False,
        "fast_status": fast_status,
        "git_status": git_status,
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
    json_path = REPORT_DIR / f"learning-v2-final-source-change-gate-auditor-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-final-source-change-gate-auditor-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Final Source-Change Gate Auditor Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- audit_status: `{audit_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- visual_evidence_required: `{str(visual_evidence_required).lower()}`")
    md.append(f"- gate_open_allowed: `{str(gate_open_allowed).lower()}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- source_change_gate_opened: `false`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Pending Required Evidence")
    md.append("")
    if pending_required_evidence:
        for x in sorted(set(pending_required_evidence)):
            md.append(f"- {x}")
    else:
        md.append("- none")
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

    print("final_source_change_gate_auditor = ok")
    print("mode = dry_run")
    print("audit_status =", audit_status)
    print("recommended_next_action =", recommended_next_action)
    print("visual_evidence_confirmed =", str(visual_evidence_confirmed).lower())
    print("visual_evidence_required =", str(visual_evidence_required).lower())
    print("gate_open_allowed =", str(gate_open_allowed).lower())
    print("source_change_gate_allowed = false")
    print("source_change_gate_opened = false")
    print("pending_required_evidence =", json.dumps(sorted(set(pending_required_evidence)), ensure_ascii=False))
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
