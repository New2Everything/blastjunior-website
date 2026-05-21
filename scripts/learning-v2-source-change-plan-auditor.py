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

SCRIPT_ID = "learning-v2-source-change-plan-auditor-v0"

REQUIRED_BEFORE_APPLY = [
    "source-change plan auditor passes",
    "file-level patch preview exists",
    "pre-change hashes captured",
    "rollback plan exists",
    "post-validation checklist exists",
    "source_change_gate explicitly opens in a later step",
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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is report-only.")
    args = ap.parse_args()

    plan_path = latest_report("learning-v2-source-change-plan-dry-run-*.json")
    if not plan_path:
        raise SystemExit("no source-change plan dry-run report found")

    plan = load_json(plan_path, {})
    safety = plan.get("safety") or {}
    file_plans = plan.get("file_plans") or []
    required = plan.get("required_before_any_apply") or []

    hard_blocks = []
    warnings = []

    if plan.get("decision") != "source_change_plan_dry_run_ready":
        hard_blocks.append("unexpected_plan_decision")
    if plan.get("source_change_plan_dry_run_allowed") is not True:
        hard_blocks.append("plan_dry_run_not_allowed")
    if plan.get("source_change_gate_allowed") is not False:
        hard_blocks.append("source_change_gate_allowed_too_early")
    if safety.get("website_source_written") is not False:
        hard_blocks.append("safety_does_not_confirm_no_website_write")
    if safety.get("source_change_gate_opened") is not False:
        hard_blocks.append("safety_does_not_confirm_gate_closed")
    if safety.get("deploy") is not False:
        hard_blocks.append("safety_does_not_confirm_no_deploy")
    if int(plan.get("candidate_file_count") or 0) <= 0:
        hard_blocks.append("no_candidate_files")
    if int(plan.get("missing_file_count") or 0) != 0:
        hard_blocks.append("missing_candidate_files")

    for needed in REQUIRED_BEFORE_APPLY:
        if needed not in required:
            hard_blocks.append(f"missing_required_before_apply:{needed}")

    audited_files = []
    for fp in file_plans:
        info = fp.get("file") or {}
        p = fp.get("plan") or {}
        path = info.get("path")
        file_blocks = []
        file_warnings = []

        if info.get("exists") is not True:
            file_blocks.append("file_missing")
        if not info.get("sha256"):
            file_blocks.append("missing_pre_change_hash")
        if not p.get("change_intent"):
            file_blocks.append("missing_change_intent")
        if not p.get("planned_operations"):
            file_blocks.append("missing_planned_operations")
        if not p.get("acceptance_checks"):
            file_blocks.append("missing_acceptance_checks")
        if p.get("risk") in ("medium", "medium-high", "high"):
            file_warnings.append("requires_explicit_patch_preview_and_rollback_before_gate")
        if path in ("public/index.html", "components/nav.html"):
            file_warnings.append("sensitive_user_entry_surface")

        audited_files.append({
            "path": path,
            "risk": p.get("risk"),
            "hard_blocks": file_blocks,
            "warnings": file_warnings,
        })
        hard_blocks.extend([f"{path}:{x}" for x in file_blocks])
        warnings.extend([f"{path}:{x}" for x in file_warnings])

    unresolved = plan.get("unresolved_surfaces") or []
    for item in unresolved:
        if item.get("surface") == "campaigns/events pages if present":
            warnings.append("unresolved_concept_surface_deferred:campaigns/events pages if present")
        else:
            hard_blocks.append(f"unresolved_surface:{item.get('surface')}")

    if hard_blocks:
        audit_status = "blocked"
        recommended_next_action = "fix_source_change_plan_before_gate_review"
        gate_review_allowed = False
    else:
        audit_status = "plan_ready_for_gate_review"
        recommended_next_action = "build_source_change_gate_readiness_dry_run"
        gate_review_allowed = True

    by_risk = Counter((fp.get("plan") or {}).get("risk") for fp in file_plans)

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "source_change_plan_source": str(plan_path),
        "audit_status": audit_status,
        "recommended_next_action": recommended_next_action,
        "candidate_file_count": plan.get("candidate_file_count"),
        "missing_file_count": plan.get("missing_file_count"),
        "by_risk": dict(by_risk),
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "audited_files": audited_files,
        "gate_review_allowed": gate_review_allowed,
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
    json_path = REPORT_DIR / f"learning-v2-source-change-plan-auditor-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-source-change-plan-auditor-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Source-Change Plan Auditor Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- audit_status: `{audit_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- gate_review_allowed: `{str(gate_review_allowed).lower()}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Hard Blocks")
    md.append("")
    if hard_blocks:
        for b in hard_blocks:
            md.append(f"- {b}")
    else:
        md.append("- none")
    md.append("")
    md.append("## Warnings")
    md.append("")
    if warnings:
        for w in warnings:
            md.append(f"- {w}")
    else:
        md.append("- none")
    md.append("")
    md.append("## Audited Files")
    md.append("")
    for f in audited_files:
        md.append(f"### {f['path']}")
        md.append(f"- risk: `{f['risk']}`")
        md.append(f"- hard_blocks: `{f['hard_blocks']}`")
        md.append(f"- warnings: `{f['warnings']}`")
        md.append("")
    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("source_change_plan_auditor = ok")
    print("mode = dry_run")
    print("audit_status =", audit_status)
    print("recommended_next_action =", recommended_next_action)
    print("source_change_plan_source =", plan_path)
    print("candidate_file_count =", plan.get("candidate_file_count"))
    print("missing_file_count =", plan.get("missing_file_count"))
    print("gate_review_allowed =", str(gate_review_allowed).lower())
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
