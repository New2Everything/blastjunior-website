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

SCRIPT_ID = "learning-v2-source-change-gate-open-request-v0"

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
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 never opens source_change_gate.")
    args = ap.parse_args()

    final_gate_path = latest_report("learning-v2-final-source-change-gate-auditor-dry-run-*.json")
    visual_auditor_path = latest_report("learning-v2-browser-visual-capture-auditor-dry-run-*.json")
    patch_preview_path = latest_report("learning-v2-file-level-patch-preview-dry-run-*.json")
    evidence_snapshot_path = latest_report("learning-v2-pre-change-evidence-snapshot-dry-run-*.json")

    if not final_gate_path:
        raise SystemExit("no final source-change gate auditor report found")
    if not visual_auditor_path:
        raise SystemExit("no browser visual capture auditor report found")
    if not patch_preview_path:
        raise SystemExit("no file-level patch preview report found")
    if not evidence_snapshot_path:
        raise SystemExit("no pre-change evidence snapshot report found")

    final_gate = load_json(final_gate_path, {})
    visual_auditor = load_json(visual_auditor_path, {})
    patch_preview = load_json(patch_preview_path, {})
    evidence_snapshot = load_json(evidence_snapshot_path, {})

    hard_blocks = []
    warnings = []

    if final_gate.get("audit_status") != "gate_open_candidate_ready_but_not_opened":
        hard_blocks.append("final_gate_auditor_not_ready_for_gate_open_request")
    if final_gate.get("visual_evidence_confirmed") is not True:
        hard_blocks.append("final_gate_visual_evidence_not_confirmed")
    if final_gate.get("gate_open_allowed") is not False:
        hard_blocks.append("final_gate_gate_open_allowed_too_early")
    if final_gate.get("source_change_gate_allowed") is not False:
        hard_blocks.append("final_gate_allows_source_change_gate_too_early")
    if final_gate.get("source_change_gate_opened") is not False:
        hard_blocks.append("final_gate_opened_source_change_gate")
    if final_gate.get("hard_blocks"):
        hard_blocks.append("final_gate_has_hard_blocks")

    if visual_auditor.get("audit_status") != "browser_visual_capture_ready_for_final_gate_recheck":
        hard_blocks.append("visual_auditor_not_ready")
    if visual_auditor.get("visual_evidence_confirmed") is not True:
        hard_blocks.append("visual_auditor_did_not_confirm_visual_evidence")
    if visual_auditor.get("source_change_gate_allowed") is not False:
        hard_blocks.append("visual_auditor_allows_gate_too_early")

    if patch_preview.get("preview_status") != "patch_preview_ready_for_audit":
        hard_blocks.append("patch_preview_not_ready")
    if patch_preview.get("source_change_gate_allowed") is not False:
        hard_blocks.append("patch_preview_allows_gate_too_early")

    if evidence_snapshot.get("snapshot_status") != "pre_change_evidence_snapshot_ready_for_audit":
        hard_blocks.append("pre_change_evidence_snapshot_not_ready")
    if evidence_snapshot.get("source_change_gate_allowed") is not False:
        hard_blocks.append("pre_change_snapshot_allows_gate_too_early")

    patch_previews = patch_preview.get("patch_previews") or []
    candidate_files = sorted({p.get("path") for p in patch_previews if p.get("path")})

    if not candidate_files:
        hard_blocks.append("no_candidate_files_for_gate_open_request")

    request_packet = {
        "request_type": "source_change_gate_open_request",
        "requested_gate": "source_change_gate",
        "request_scope": "single_controlled_source_change_candidate",
        "candidate_files": candidate_files,
        "required_preconditions": [
            "final_gate_auditor_passed_with_visual_evidence",
            "browser_visual_capture_auditor_confirmed",
            "patch_preview_exists",
            "pre_change_evidence_snapshot_exists",
            "rollback_and_post_validation_plan_exists",
            "deploy_remains_blocked",
        ],
        "must_remain_false_until_separate_gate_opener": {
            "source_change_gate_allowed": False,
            "source_change_gate_opened": False,
            "website_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
    }

    if hard_blocks:
        request_status = "blocked"
        recommended_next_action = "fix_source_change_gate_open_request_inputs"
        request_audit_allowed = False
    else:
        request_status = "source_change_gate_open_request_ready_for_audit"
        recommended_next_action = "run_source_change_gate_open_request_auditor_dry_run"
        request_audit_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "final_gate_auditor_source": str(final_gate_path),
        "browser_visual_capture_auditor_source": str(visual_auditor_path),
        "patch_preview_source": str(patch_preview_path),
        "pre_change_evidence_snapshot_source": str(evidence_snapshot_path),
        "request_status": request_status,
        "recommended_next_action": recommended_next_action,
        "request_packet": request_packet,
        "candidate_file_count": len(candidate_files),
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "request_audit_allowed": request_audit_allowed,
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
    json_path = REPORT_DIR / f"learning-v2-source-change-gate-open-request-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-source-change-gate-open-request-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Source-Change Gate Open Request Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- request_status: `{request_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- request_audit_allowed: `{str(request_audit_allowed).lower()}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- source_change_gate_opened: `false`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Candidate Files")
    md.append("")
    if candidate_files:
        for x in candidate_files:
            md.append(f"- `{x}`")
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
    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("source_change_gate_open_request = ok")
    print("mode = dry_run")
    print("request_status =", request_status)
    print("recommended_next_action =", recommended_next_action)
    print("candidate_file_count =", len(candidate_files))
    print("request_audit_allowed =", str(request_audit_allowed).lower())
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
