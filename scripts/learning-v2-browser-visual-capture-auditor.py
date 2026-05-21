#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-browser-visual-capture-auditor-v0"

REQUIRED_TARGETS = {
    "homepage_desktop": {"mobile_required": False},
    "homepage_mobile": {"mobile_required": True},
    "nav_mobile": {"mobile_required": True},
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def latest_report(pattern):
    files = sorted(REPORT_DIR.glob(pattern))
    return files[-1] if files else None

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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is report-only and never opens source_change_gate.")
    args = ap.parse_args()

    capture_path = latest_report("learning-v2-browser-visual-capture-dry-run-*.json")
    validation_path = latest_report("learning-v2-visual-evidence-capture-validation-dry-run-*.json")
    final_gate_path = latest_report("learning-v2-final-source-change-gate-auditor-dry-run-*.json")

    if not capture_path:
        raise SystemExit("no browser visual capture report found")
    if not validation_path:
        raise SystemExit("no visual evidence validation report found")
    if not final_gate_path:
        raise SystemExit("no final gate auditor report found")

    capture = load_json(capture_path, {})
    validation = load_json(validation_path, {})
    final_gate = load_json(final_gate_path, {})

    hard_blocks = []
    warnings = []

    if capture.get("capture_status") != "browser_visual_capture_ready_for_audit":
        hard_blocks.append("capture_status_not_ready_for_audit")
    if capture.get("visual_evidence_audit_allowed") is not True:
        hard_blocks.append("visual_evidence_audit_not_allowed")
    if capture.get("source_change_gate_allowed") is not False:
        hard_blocks.append("capture_allows_source_change_gate_too_early")
    if capture.get("source_change_gate_opened") is not False:
        hard_blocks.append("capture_opened_source_change_gate")
    if capture.get("hard_blocks"):
        hard_blocks.append("capture_report_has_hard_blocks")

    if validation.get("validation_status") != "browser_visual_capture_module_required":
        warnings.append("visual_validation_status_unexpected")
    if final_gate.get("audit_status") != "gate_blocked_pending_visual_evidence":
        warnings.append("final_gate_not_currently_blocked_by_visual_evidence")

    target_results = capture.get("target_results") or []
    by_name = {x.get("name"): x for x in target_results}

    audited_targets = []
    for name, rule in REQUIRED_TARGETS.items():
        r = by_name.get(name)
        target_blocks = []
        target_warnings = []

        if not r:
            target_blocks.append("missing_target_result")
        else:
            screenshot_path = r.get("screenshot_path")
            if not r.get("source_exists"):
                target_blocks.append("source_missing")
            if not r.get("screenshot_exists"):
                target_blocks.append("screenshot_missing")
            if not r.get("actual_visual_captured"):
                target_blocks.append("actual_visual_not_captured")
            if not screenshot_path:
                target_blocks.append("missing_screenshot_path")
            elif not Path(screenshot_path).exists():
                target_blocks.append("screenshot_path_does_not_exist")
            if rule["mobile_required"] and r.get("actual_mobile_validated") is not True:
                target_blocks.append("mobile_validation_missing")
            if r.get("returncode") != 0:
                target_blocks.append("capture_returncode_not_zero")

        audited_targets.append({
            "name": name,
            "screenshot_path": r.get("screenshot_path") if r else None,
            "hard_blocks": target_blocks,
            "warnings": target_warnings,
        })

        hard_blocks.extend([f"{name}:{x}" for x in target_blocks])
        warnings.extend([f"{name}:{x}" for x in target_warnings])

    captured_count = int(capture.get("captured_count") or 0)
    required_count = int(capture.get("required_count") or 0)
    mobile_validated_count = int(capture.get("mobile_validated_count") or 0)

    if required_count < len(REQUIRED_TARGETS):
        hard_blocks.append("required_count_less_than_expected_targets")
    if captured_count < required_count:
        hard_blocks.append("captured_count_less_than_required_count")
    if mobile_validated_count < 2:
        hard_blocks.append("mobile_validated_count_less_than_required_mobile_targets")

    if hard_blocks:
        audit_status = "blocked"
        recommended_next_action = "fix_browser_visual_capture_before_gate"
        final_gate_recheck_allowed = False
        visual_evidence_confirmed = False
    else:
        audit_status = "browser_visual_capture_ready_for_final_gate_recheck"
        recommended_next_action = "rerun_final_source_change_gate_auditor_with_visual_evidence"
        final_gate_recheck_allowed = True
        visual_evidence_confirmed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "browser_visual_capture_source": str(capture_path),
        "visual_validation_source": str(validation_path),
        "final_gate_auditor_source": str(final_gate_path),
        "audit_status": audit_status,
        "recommended_next_action": recommended_next_action,
        "captured_count": captured_count,
        "required_count": required_count,
        "mobile_validated_count": mobile_validated_count,
        "visual_evidence_confirmed": visual_evidence_confirmed,
        "final_gate_recheck_allowed": final_gate_recheck_allowed,
        "audited_targets": audited_targets,
        "hard_blocks": hard_blocks,
        "warnings": warnings,
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
    json_path = REPORT_DIR / f"learning-v2-browser-visual-capture-auditor-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-browser-visual-capture-auditor-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Browser Visual Capture Auditor Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- audit_status: `{audit_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- visual_evidence_confirmed: `{str(visual_evidence_confirmed).lower()}`")
    md.append(f"- final_gate_recheck_allowed: `{str(final_gate_recheck_allowed).lower()}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Audited Targets")
    md.append("")
    for x in audited_targets:
        md.append(f"### {x['name']}")
        md.append(f"- screenshot_path: `{x['screenshot_path']}`")
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
    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("browser_visual_capture_auditor = ok")
    print("mode = dry_run")
    print("audit_status =", audit_status)
    print("recommended_next_action =", recommended_next_action)
    print("captured_count =", captured_count)
    print("required_count =", required_count)
    print("mobile_validated_count =", mobile_validated_count)
    print("visual_evidence_confirmed =", str(visual_evidence_confirmed).lower())
    print("final_gate_recheck_allowed =", str(final_gate_recheck_allowed).lower())
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
