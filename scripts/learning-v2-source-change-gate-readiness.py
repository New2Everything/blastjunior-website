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

SCRIPT_ID = "learning-v2-source-change-gate-readiness-v0"

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

    plan_path = latest_report("learning-v2-source-change-plan-dry-run-*.json")
    auditor_path = latest_report("learning-v2-source-change-plan-auditor-dry-run-*.json")

    if not plan_path:
        raise SystemExit("no source-change plan dry-run report found")
    if not auditor_path:
        raise SystemExit("no source-change plan auditor report found")

    plan = load_json(plan_path, {})
    auditor = load_json(auditor_path, {})

    hard_blocks = []
    warnings = list(auditor.get("warnings") or [])
    required_before_open_gate = []

    if auditor.get("audit_status") != "plan_ready_for_gate_review":
        hard_blocks.append("plan_auditor_not_ready_for_gate_review")
    if auditor.get("gate_review_allowed") is not True:
        hard_blocks.append("auditor_does_not_allow_gate_review")
    if auditor.get("source_change_gate_allowed") is not False:
        hard_blocks.append("auditor_allows_source_change_gate_too_early")
    if auditor.get("hard_blocks"):
        hard_blocks.append("auditor_has_hard_blocks")

    safety = plan.get("safety") or {}
    if safety.get("website_source_written") is not False:
        hard_blocks.append("plan_safety_does_not_confirm_no_website_write")
    if safety.get("source_change_gate_opened") is not False:
        hard_blocks.append("plan_safety_does_not_confirm_gate_closed")
    if safety.get("deploy") is not False:
        hard_blocks.append("plan_safety_does_not_confirm_no_deploy")

    if int(plan.get("candidate_file_count") or 0) <= 0:
        hard_blocks.append("no_candidate_files")
    if int(plan.get("missing_file_count") or 0) != 0:
        hard_blocks.append("missing_candidate_files")

    file_plans = plan.get("file_plans") or []
    medium_or_higher = []
    sensitive_surfaces = []

    for fp in file_plans:
        info = fp.get("file") or {}
        p = fp.get("plan") or {}
        path = info.get("path")
        risk = p.get("risk")

        if risk in ("medium", "medium-high", "high"):
            medium_or_higher.append(path)
        if path in ("public/index.html", "components/nav.html"):
            sensitive_surfaces.append(path)

        if not info.get("sha256"):
            hard_blocks.append(f"{path}:missing_pre_change_hash")
        if not p.get("planned_operations"):
            hard_blocks.append(f"{path}:missing_planned_operations")
        if not p.get("acceptance_checks"):
            hard_blocks.append(f"{path}:missing_acceptance_checks")

    if medium_or_higher:
        required_before_open_gate.append("file_level_patch_preview_required")
        required_before_open_gate.append("rollback_plan_required")
    if sensitive_surfaces:
        required_before_open_gate.append("pre_change_screenshot_or_snapshot_required")
        required_before_open_gate.append("mobile_validation_required_for_navigation_or_homepage")

    required_before_open_gate.append("post_validation_checklist_required")
    required_before_open_gate.append("explicit_gate_open_policy_required")

    # v0 intentionally does NOT open the gate. It decides what is missing before a later gate-open step.
    if hard_blocks:
        readiness_status = "blocked"
        recommended_next_action = "fix_source_change_plan_or_auditor_before_gate_readiness"
        gate_open_readiness = False
    elif required_before_open_gate:
        readiness_status = "patch_preview_required_before_gate"
        recommended_next_action = "build_file_level_patch_preview_and_rollback_dry_run"
        gate_open_readiness = False
    else:
        readiness_status = "gate_open_candidate_ready"
        recommended_next_action = "run_source_change_gate_open_policy_dry_run"
        gate_open_readiness = False

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "source_change_plan_source": str(plan_path),
        "source_change_plan_auditor_source": str(auditor_path),
        "readiness_status": readiness_status,
        "recommended_next_action": recommended_next_action,
        "candidate_file_count": plan.get("candidate_file_count"),
        "missing_file_count": plan.get("missing_file_count"),
        "medium_or_higher_risk_files": medium_or_higher,
        "sensitive_surfaces": sorted(set(sensitive_surfaces)),
        "required_before_open_gate": sorted(set(required_before_open_gate)),
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "gate_open_readiness": gate_open_readiness,
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
    json_path = REPORT_DIR / f"learning-v2-source-change-gate-readiness-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-source-change-gate-readiness-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Source-Change Gate Readiness Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- readiness_status: `{readiness_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- gate_open_readiness: `{str(gate_open_readiness).lower()}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- source_change_gate_opened: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Required Before Open Gate")
    md.append("")
    if payload["required_before_open_gate"]:
        for x in payload["required_before_open_gate"]:
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
    md.append("## Sensitive Surfaces")
    md.append("")
    if sensitive_surfaces:
        for x in sorted(set(sensitive_surfaces)):
            md.append(f"- {x}")
    else:
        md.append("- none")
    md.append("")
    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("source_change_gate_readiness = ok")
    print("mode = dry_run")
    print("readiness_status =", readiness_status)
    print("recommended_next_action =", recommended_next_action)
    print("candidate_file_count =", plan.get("candidate_file_count"))
    print("missing_file_count =", plan.get("missing_file_count"))
    print("gate_open_readiness =", str(gate_open_readiness).lower())
    print("source_change_gate_allowed = false")
    print("source_change_gate_opened = false")
    print("required_before_open_gate =", json.dumps(payload["required_before_open_gate"], ensure_ascii=False))
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
