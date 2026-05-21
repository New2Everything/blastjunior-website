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

SCRIPT_ID = "learning-v2-required-gate-evidence-modules-auditor-v0"

REQUIRED_MODULES = {
    "explicit_rollback_packet_module",
    "mobile_visual_snapshot_or_validation_module",
    "post_validation_command_plan_module",
    "pre_change_visual_snapshot_module",
}

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

    modules_path = latest_report("learning-v2-required-gate-evidence-modules-dry-run-*.json")
    evidence_auditor_path = latest_report("learning-v2-pre-change-evidence-auditor-dry-run-*.json")

    if not modules_path:
        raise SystemExit("no required gate evidence modules report found")
    if not evidence_auditor_path:
        raise SystemExit("no pre-change evidence auditor report found")

    modules_report = load_json(modules_path, {})
    evidence_auditor = load_json(evidence_auditor_path, {})

    hard_blocks = []
    warnings = list(modules_report.get("warnings") or [])

    if modules_report.get("modules_status") != "required_gate_evidence_modules_ready_for_audit":
        hard_blocks.append("modules_status_not_ready_for_audit")
    if modules_report.get("evidence_modules_audit_allowed") is not True:
        hard_blocks.append("evidence_modules_audit_not_allowed")
    if modules_report.get("source_change_gate_allowed") is not False:
        hard_blocks.append("modules_report_allows_source_change_gate_too_early")
    if modules_report.get("source_change_gate_opened") is not False:
        hard_blocks.append("modules_report_opened_source_change_gate")
    if modules_report.get("hard_blocks"):
        hard_blocks.append("modules_report_has_hard_blocks")

    if evidence_auditor.get("audit_status") != "pre_change_evidence_ready_for_required_evidence_modules":
        hard_blocks.append("pre_change_evidence_auditor_not_ready_for_modules")
    if evidence_auditor.get("source_change_gate_allowed") is not False:
        hard_blocks.append("pre_change_evidence_auditor_allows_source_change_gate_too_early")

    modules = modules_report.get("modules") or []
    module_names = {m.get("module") for m in modules}

    missing = sorted(REQUIRED_MODULES - module_names)
    unknown = sorted(module_names - REQUIRED_MODULES)

    if missing:
        hard_blocks.extend([f"missing_required_module:{x}" for x in missing])
    if unknown:
        hard_blocks.extend([f"unknown_module:{x}" for x in unknown])

    audited_modules = []
    for m in modules:
        name = m.get("module")
        status = m.get("status")
        evidence = m.get("evidence") or {}

        module_blocks = []
        module_warnings = list(m.get("warnings") or [])

        if name not in REQUIRED_MODULES:
            module_blocks.append("module_not_in_required_set")
        if status not in ("ready", "ready_with_required_followup"):
            module_blocks.append("module_status_not_acceptable")
        if not m.get("purpose"):
            module_blocks.append("missing_purpose")
        if not evidence:
            module_blocks.append("missing_evidence")

        if name == "explicit_rollback_packet_module":
            if not evidence.get("file_hashes_captured"):
                module_blocks.append("missing_file_hashes_captured")
            if not evidence.get("rollback_strategy"):
                module_blocks.append("missing_rollback_strategy")

        if name == "mobile_visual_snapshot_or_validation_module":
            if not evidence.get("required_checks"):
                module_blocks.append("missing_mobile_required_checks")
            if evidence.get("actual_screenshot_captured") is not False:
                module_blocks.append("unexpected_actual_screenshot_flag")
            module_warnings.append("mobile_visual_capture_still_required_before_real_gate")

        if name == "post_validation_command_plan_module":
            if not evidence.get("planned_validation_commands"):
                module_blocks.append("missing_validation_commands")
            if not evidence.get("planned_manual_or_browser_checks"):
                module_blocks.append("missing_manual_or_browser_checks")

        if name == "pre_change_visual_snapshot_module":
            if not evidence.get("required_snapshots"):
                module_blocks.append("missing_required_snapshots")
            if evidence.get("actual_visual_snapshot_captured") is not False:
                module_blocks.append("unexpected_actual_visual_snapshot_flag")
            module_warnings.append("pre_change_visual_capture_still_required_before_real_gate")

        audited_modules.append({
            "module": name,
            "status": status,
            "hard_blocks": module_blocks,
            "warnings": module_warnings,
        })

        hard_blocks.extend([f"{name}:{x}" for x in module_blocks])
        warnings.extend([f"{name}:{x}" for x in module_warnings])

    by_status = Counter(m.get("status") for m in modules)

    if hard_blocks:
        audit_status = "blocked"
        recommended_next_action = "fix_required_gate_evidence_modules_before_gate"
        final_gate_auditor_allowed = False
    else:
        audit_status = "required_gate_evidence_modules_ready_for_final_gate_auditor"
        recommended_next_action = "run_final_source_change_gate_auditor_dry_run"
        final_gate_auditor_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "required_gate_evidence_modules_source": str(modules_path),
        "pre_change_evidence_auditor_source": str(evidence_auditor_path),
        "audit_status": audit_status,
        "recommended_next_action": recommended_next_action,
        "required_module_count": len(REQUIRED_MODULES),
        "built_module_count": len(modules),
        "by_status": dict(by_status),
        "audited_modules": audited_modules,
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "final_gate_auditor_allowed": final_gate_auditor_allowed,
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
    json_path = REPORT_DIR / f"learning-v2-required-gate-evidence-modules-auditor-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-required-gate-evidence-modules-auditor-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Required Gate Evidence Modules Auditor Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- audit_status: `{audit_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- final_gate_auditor_allowed: `{str(final_gate_auditor_allowed).lower()}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- source_change_gate_opened: `false`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Audited Modules")
    md.append("")
    for x in audited_modules:
        md.append(f"### {x['module']}")
        md.append(f"- status: `{x['status']}`")
        md.append(f"- hard_blocks: `{x['hard_blocks']}`")
        md.append(f"- warnings: `{x['warnings']}`")
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

    print("required_gate_evidence_modules_auditor = ok")
    print("mode = dry_run")
    print("audit_status =", audit_status)
    print("recommended_next_action =", recommended_next_action)
    print("required_module_count =", len(REQUIRED_MODULES))
    print("built_module_count =", len(modules))
    print("by_status =", json.dumps(dict(by_status), ensure_ascii=False))
    print("final_gate_auditor_allowed =", str(final_gate_auditor_allowed).lower())
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
