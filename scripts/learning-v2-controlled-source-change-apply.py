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

SCRIPT_ID = "learning-v2-controlled-source-change-apply-v0"

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
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is dry-run only and never writes website source.")
    args = ap.parse_args()

    opener_auditor_path = latest_report("learning-v2-source-change-gate-opener-auditor-dry-run-*.json")
    opener_path = latest_report("learning-v2-source-change-gate-opener-dry-run-*.json")
    request_path = latest_report("learning-v2-source-change-gate-open-request-dry-run-*.json")
    patch_preview_path = latest_report("learning-v2-file-level-patch-preview-dry-run-*.json")
    evidence_snapshot_path = latest_report("learning-v2-pre-change-evidence-snapshot-dry-run-*.json")

    if not opener_auditor_path:
        raise SystemExit("no source-change gate opener auditor report found")
    if not opener_path:
        raise SystemExit("no source-change gate opener report found")
    if not request_path:
        raise SystemExit("no source-change gate open request report found")
    if not patch_preview_path:
        raise SystemExit("no file-level patch preview report found")
    if not evidence_snapshot_path:
        raise SystemExit("no pre-change evidence snapshot report found")

    opener_auditor = load_json(opener_auditor_path, {})
    opener = load_json(opener_path, {})
    request = load_json(request_path, {})
    patch_preview = load_json(patch_preview_path, {})
    evidence_snapshot = load_json(evidence_snapshot_path, {})

    hard_blocks = []
    warnings = []

    if opener_auditor.get("audit_status") != "source_change_gate_opener_ready_for_controlled_apply_dry_run":
        hard_blocks.append("opener_auditor_not_ready_for_controlled_apply")
    if opener_auditor.get("controlled_apply_dry_run_allowed") is not True:
        hard_blocks.append("controlled_apply_dry_run_not_allowed")
    if opener_auditor.get("source_change_gate_allowed") is not False:
        hard_blocks.append("opener_auditor_allows_gate_too_early")
    if opener_auditor.get("source_change_gate_opened") is not False:
        hard_blocks.append("opener_auditor_opened_gate")
    if opener_auditor.get("hard_blocks"):
        hard_blocks.append("opener_auditor_has_hard_blocks")

    if opener.get("opener_status") != "source_change_gate_opener_dry_run_ready_for_audit":
        hard_blocks.append("opener_not_ready")
    if opener.get("source_change_gate_allowed") is not False:
        hard_blocks.append("opener_allows_gate_too_early")

    if request.get("request_status") != "source_change_gate_open_request_ready_for_audit":
        hard_blocks.append("gate_open_request_not_ready")
    if request.get("source_change_gate_allowed") is not False:
        hard_blocks.append("gate_open_request_allows_gate_too_early")

    if patch_preview.get("preview_status") != "patch_preview_ready_for_audit":
        hard_blocks.append("patch_preview_not_ready")
    if patch_preview.get("source_change_gate_allowed") is not False:
        hard_blocks.append("patch_preview_allows_gate_too_early")

    if evidence_snapshot.get("snapshot_status") != "pre_change_evidence_snapshot_ready_for_audit":
        hard_blocks.append("pre_change_evidence_snapshot_not_ready")
    if evidence_snapshot.get("source_change_gate_allowed") is not False:
        hard_blocks.append("pre_change_snapshot_allows_gate_too_early")

    request_packet = request.get("request_packet") or {}
    requested_files = sorted(set(request_packet.get("candidate_files") or []))

    patch_previews = patch_preview.get("patch_previews") or []
    preview_by_path = {x.get("path"): x for x in patch_previews if x.get("path")}

    if not requested_files:
        hard_blocks.append("missing_requested_candidate_files")

    apply_plan = []
    for rel in requested_files:
        src = WORKSPACE / rel
        preview = preview_by_path.get(rel) or {}
        apply_plan.append({
            "path": rel,
            "source_exists": src.exists(),
            "preview_exists": bool(preview),
            "operation": preview.get("operation") or preview.get("change_type") or "previewed_change",
            "will_write_source": False,
            "will_commit": False,
            "will_push": False,
            "will_deploy": False,
        })

        if not src.exists():
            hard_blocks.append(f"{rel}:source_missing")
        if not preview:
            warnings.append(f"{rel}:no_matching_patch_preview_detail")

    if hard_blocks:
        apply_status = "blocked"
        recommended_next_action = "fix_controlled_source_change_apply_inputs"
        apply_audit_allowed = False
    else:
        apply_status = "controlled_source_change_apply_dry_run_ready_for_audit"
        recommended_next_action = "run_controlled_source_change_apply_auditor_dry_run"
        apply_audit_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "source_change_gate_opener_auditor_source": str(opener_auditor_path),
        "source_change_gate_opener_source": str(opener_path),
        "source_change_gate_open_request_source": str(request_path),
        "patch_preview_source": str(patch_preview_path),
        "pre_change_evidence_snapshot_source": str(evidence_snapshot_path),
        "apply_status": apply_status,
        "recommended_next_action": recommended_next_action,
        "candidate_file_count": len(requested_files),
        "apply_plan": apply_plan,
        "apply_audit_allowed": apply_audit_allowed,
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
    json_path = REPORT_DIR / f"learning-v2-controlled-source-change-apply-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-controlled-source-change-apply-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Controlled Source-Change Apply Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- apply_status: `{apply_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- apply_audit_allowed: `{str(apply_audit_allowed).lower()}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- source_change_gate_opened: `false`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Apply Plan")
    md.append("")
    for x in apply_plan:
        md.append(f"### {x['path']}")
        md.append(f"- source_exists: `{str(x['source_exists']).lower()}`")
        md.append(f"- preview_exists: `{str(x['preview_exists']).lower()}`")
        md.append(f"- operation: `{x['operation']}`")
        md.append(f"- will_write_source: `false`")
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

    print("controlled_source_change_apply = ok")
    print("mode = dry_run")
    print("apply_status =", apply_status)
    print("recommended_next_action =", recommended_next_action)
    print("candidate_file_count =", len(requested_files))
    print("apply_audit_allowed =", str(apply_audit_allowed).lower())
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
