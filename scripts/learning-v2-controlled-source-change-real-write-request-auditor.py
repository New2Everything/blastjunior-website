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

SCRIPT_ID = "learning-v2-controlled-source-change-real-write-request-auditor-v0"

REQUIRED_NEXT = {
    "controlled_source_change_real_write_request_auditor",
    "real_write_executor_dry_run",
    "real_write_executor_auditor",
}

MUST_REMAIN_FALSE = {
    "business_source_written",
    "website_source_written",
    "source_change_gate_opened",
    "git_commit",
    "git_push",
    "deploy",
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
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is report-only and never writes website source.")
    args = ap.parse_args()

    request_path = latest_report("learning-v2-controlled-source-change-real-write-request-dry-run-*.json")
    apply_auditor_path = latest_report("learning-v2-controlled-source-change-apply-auditor-dry-run-*.json")
    apply_path = latest_report("learning-v2-controlled-source-change-apply-dry-run-*.json")
    patch_preview_path = latest_report("learning-v2-file-level-patch-preview-dry-run-*.json")
    evidence_snapshot_path = latest_report("learning-v2-pre-change-evidence-snapshot-dry-run-*.json")

    if not request_path:
        raise SystemExit("no controlled source-change real-write request report found")
    if not apply_auditor_path:
        raise SystemExit("no controlled source-change apply auditor report found")
    if not apply_path:
        raise SystemExit("no controlled source-change apply report found")
    if not patch_preview_path:
        raise SystemExit("no file-level patch preview report found")
    if not evidence_snapshot_path:
        raise SystemExit("no pre-change evidence snapshot report found")

    request = load_json(request_path, {})
    apply_auditor = load_json(apply_auditor_path, {})
    apply_report = load_json(apply_path, {})
    patch_preview = load_json(patch_preview_path, {})
    evidence_snapshot = load_json(evidence_snapshot_path, {})

    hard_blocks = []
    warnings = []

    if request.get("request_status") != "controlled_source_change_real_write_request_ready_for_audit":
        hard_blocks.append("real_write_request_not_ready_for_audit")
    if request.get("request_audit_allowed") is not True:
        hard_blocks.append("request_audit_not_allowed")
    if request.get("source_change_gate_allowed") is not False:
        hard_blocks.append("request_allows_gate_too_early")
    if request.get("source_change_gate_opened") is not False:
        hard_blocks.append("request_opened_gate")
    if request.get("hard_blocks"):
        hard_blocks.append("request_report_has_hard_blocks")

    if apply_auditor.get("audit_status") != "controlled_source_change_apply_ready_for_real_write_request_dry_run":
        hard_blocks.append("apply_auditor_not_ready_for_real_write_request")
    if apply_auditor.get("real_write_request_dry_run_allowed") is not True:
        hard_blocks.append("apply_auditor_did_not_allow_real_write_request")
    if apply_auditor.get("source_change_gate_allowed") is not False:
        hard_blocks.append("apply_auditor_allows_gate_too_early")

    if apply_report.get("apply_status") != "controlled_source_change_apply_dry_run_ready_for_audit":
        hard_blocks.append("controlled_apply_report_not_ready")
    if patch_preview.get("preview_status") != "patch_preview_ready_for_audit":
        hard_blocks.append("patch_preview_not_ready")
    if evidence_snapshot.get("snapshot_status") != "pre_change_evidence_snapshot_ready_for_audit":
        hard_blocks.append("pre_change_evidence_snapshot_not_ready")

    packet = request.get("request_packet") or {}
    if packet.get("request_type") != "controlled_source_change_real_write_request":
        hard_blocks.append("request_packet_type_invalid")
    if packet.get("requested_stage") != "controlled_source_change_real_write":
        hard_blocks.append("requested_stage_invalid")

    candidate_files = packet.get("candidate_files") or []
    request_items = packet.get("request_items") or []
    if not candidate_files:
        hard_blocks.append("missing_candidate_files")
    if not request_items:
        hard_blocks.append("missing_request_items")

    required_next = set(packet.get("required_next_before_any_write") or [])
    missing_required_next = sorted(REQUIRED_NEXT - required_next)
    if missing_required_next:
        hard_blocks.extend([f"missing_required_next:{x}" for x in missing_required_next])

    must_false = packet.get("must_remain_false_in_this_step") or {}
    for k in MUST_REMAIN_FALSE:
        if must_false.get(k) is not False:
            hard_blocks.append(f"must_remain_false_violation:{k}")

    audited_items = []
    for item in request_items:
        rel = item.get("path")
        item_blocks = []
        item_warnings = []

        if not rel:
            item_blocks.append("missing_path")
        else:
            if rel not in candidate_files:
                item_blocks.append("path_not_in_candidate_files")
            if not (WORKSPACE / rel).exists():
                item_blocks.append("source_missing")

        if item.get("request_real_source_write") is not True:
            item_blocks.append("request_real_source_write_not_true")
        if item.get("write_must_be_separately_audited") is not True:
            item_blocks.append("write_must_be_separately_audited_not_true")
        if item.get("git_commit_allowed") is not False:
            item_blocks.append("git_commit_allowed_not_false")
        if item.get("git_push_allowed") is not False:
            item_blocks.append("git_push_allowed_not_false")
        if item.get("deploy_allowed") is not False:
            item_blocks.append("deploy_allowed_not_false")
        if item.get("hard_blocks"):
            item_blocks.append("request_item_has_hard_blocks")

        audited_items.append({
            "path": rel,
            "hard_blocks": item_blocks,
            "warnings": item_warnings,
        })

        hard_blocks.extend([f"{rel}:{x}" for x in item_blocks])
        warnings.extend([f"{rel}:{x}" for x in item_warnings])

    safety = request.get("safety") or {}
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
        recommended_next_action = "fix_controlled_real_write_request_before_executor_dry_run"
        executor_dry_run_allowed = False
    else:
        audit_status = "controlled_source_change_real_write_request_ready_for_executor_dry_run"
        recommended_next_action = "run_controlled_source_change_real_write_executor_dry_run"
        executor_dry_run_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "controlled_source_change_real_write_request_source": str(request_path),
        "controlled_source_change_apply_auditor_source": str(apply_auditor_path),
        "controlled_source_change_apply_source": str(apply_path),
        "patch_preview_source": str(patch_preview_path),
        "pre_change_evidence_snapshot_source": str(evidence_snapshot_path),
        "audit_status": audit_status,
        "recommended_next_action": recommended_next_action,
        "candidate_file_count": len(candidate_files),
        "audited_items": audited_items,
        "executor_dry_run_allowed": executor_dry_run_allowed,
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
    json_path = REPORT_DIR / f"learning-v2-controlled-source-change-real-write-request-auditor-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-controlled-source-change-real-write-request-auditor-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Controlled Source-Change Real-Write Request Auditor Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- audit_status: `{audit_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- executor_dry_run_allowed: `{str(executor_dry_run_allowed).lower()}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- source_change_gate_opened: `false`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Audited Items")
    md.append("")
    for x in audited_items:
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
    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("controlled_source_change_real_write_request_auditor = ok")
    print("mode = dry_run")
    print("audit_status =", audit_status)
    print("recommended_next_action =", recommended_next_action)
    print("candidate_file_count =", len(candidate_files))
    print("executor_dry_run_allowed =", str(executor_dry_run_allowed).lower())
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
