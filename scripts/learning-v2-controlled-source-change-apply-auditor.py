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

SCRIPT_ID = "learning-v2-controlled-source-change-apply-auditor-v0"

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
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is report-only and never writes source.")
    args = ap.parse_args()

    apply_path = latest_report("learning-v2-controlled-source-change-apply-dry-run-*.json")
    opener_auditor_path = latest_report("learning-v2-source-change-gate-opener-auditor-dry-run-*.json")
    patch_preview_path = latest_report("learning-v2-file-level-patch-preview-dry-run-*.json")
    evidence_snapshot_path = latest_report("learning-v2-pre-change-evidence-snapshot-dry-run-*.json")

    if not apply_path:
        raise SystemExit("no controlled source-change apply report found")
    if not opener_auditor_path:
        raise SystemExit("no source-change gate opener auditor report found")
    if not patch_preview_path:
        raise SystemExit("no file-level patch preview report found")
    if not evidence_snapshot_path:
        raise SystemExit("no pre-change evidence snapshot report found")

    apply_report = load_json(apply_path, {})
    opener_auditor = load_json(opener_auditor_path, {})
    patch_preview = load_json(patch_preview_path, {})
    evidence_snapshot = load_json(evidence_snapshot_path, {})

    hard_blocks = []
    warnings = []

    if apply_report.get("apply_status") != "controlled_source_change_apply_dry_run_ready_for_audit":
        hard_blocks.append("apply_status_not_ready_for_audit")
    if apply_report.get("apply_audit_allowed") is not True:
        hard_blocks.append("apply_audit_not_allowed")
    if apply_report.get("source_change_gate_allowed") is not False:
        hard_blocks.append("apply_report_allows_gate_too_early")
    if apply_report.get("source_change_gate_opened") is not False:
        hard_blocks.append("apply_report_opened_gate")
    if apply_report.get("hard_blocks"):
        hard_blocks.append("apply_report_has_hard_blocks")

    if opener_auditor.get("audit_status") != "source_change_gate_opener_ready_for_controlled_apply_dry_run":
        hard_blocks.append("opener_auditor_not_ready")
    if opener_auditor.get("controlled_apply_dry_run_allowed") is not True:
        hard_blocks.append("opener_auditor_did_not_allow_controlled_apply")
    if opener_auditor.get("source_change_gate_allowed") is not False:
        hard_blocks.append("opener_auditor_allows_gate_too_early")

    if patch_preview.get("preview_status") != "patch_preview_ready_for_audit":
        hard_blocks.append("patch_preview_not_ready")
    if evidence_snapshot.get("snapshot_status") != "pre_change_evidence_snapshot_ready_for_audit":
        hard_blocks.append("pre_change_evidence_snapshot_not_ready")

    apply_plan = apply_report.get("apply_plan") or []
    if not apply_plan:
        hard_blocks.append("missing_apply_plan")

    audited_files = []
    for item in apply_plan:
        rel = item.get("path")
        item_blocks = []
        item_warnings = []

        if not rel:
            item_blocks.append("missing_path")
        else:
            if not (WORKSPACE / rel).exists():
                item_blocks.append("source_missing")

        if item.get("source_exists") is not True:
            item_blocks.append("source_exists_not_true")
        if item.get("will_write_source") is not False:
            item_blocks.append("will_write_source_not_false")
        if item.get("will_commit") is not False:
            item_blocks.append("will_commit_not_false")
        if item.get("will_push") is not False:
            item_blocks.append("will_push_not_false")
        if item.get("will_deploy") is not False:
            item_blocks.append("will_deploy_not_false")

        if item.get("preview_exists") is not True:
            item_warnings.append("preview_detail_missing_or_unmatched")

        audited_files.append({
            "path": rel,
            "hard_blocks": item_blocks,
            "warnings": item_warnings,
        })

        hard_blocks.extend([f"{rel}:{x}" for x in item_blocks])
        warnings.extend([f"{rel}:{x}" for x in item_warnings])

    safety = apply_report.get("safety") or {}
    for k in [
        "business_source_written",
        "website_source_written",
        "source_change_gate_opened",
        "git_commit",
        "git_push",
        "deploy",
    ]:
        if safety.get(k) is not False:
            hard_blocks.append(f"safety_violation:{k}")

    if hard_blocks:
        audit_status = "blocked"
        recommended_next_action = "fix_controlled_source_change_apply_before_real_write_request"
        real_write_request_dry_run_allowed = False
    else:
        audit_status = "controlled_source_change_apply_ready_for_real_write_request_dry_run"
        recommended_next_action = "run_controlled_source_change_real_write_request_dry_run"
        real_write_request_dry_run_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "controlled_source_change_apply_source": str(apply_path),
        "source_change_gate_opener_auditor_source": str(opener_auditor_path),
        "patch_preview_source": str(patch_preview_path),
        "pre_change_evidence_snapshot_source": str(evidence_snapshot_path),
        "audit_status": audit_status,
        "recommended_next_action": recommended_next_action,
        "candidate_file_count": len(apply_plan),
        "audited_files": audited_files,
        "real_write_request_dry_run_allowed": real_write_request_dry_run_allowed,
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
    json_path = REPORT_DIR / f"learning-v2-controlled-source-change-apply-auditor-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-controlled-source-change-apply-auditor-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Controlled Source-Change Apply Auditor Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- audit_status: `{audit_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- real_write_request_dry_run_allowed: `{str(real_write_request_dry_run_allowed).lower()}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- source_change_gate_opened: `false`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Audited Files")
    md.append("")
    for x in audited_files:
        md.append(f"### {x['path']}")
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

    print("controlled_source_change_apply_auditor = ok")
    print("mode = dry_run")
    print("audit_status =", audit_status)
    print("recommended_next_action =", recommended_next_action)
    print("candidate_file_count =", len(apply_plan))
    print("real_write_request_dry_run_allowed =", str(real_write_request_dry_run_allowed).lower())
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
