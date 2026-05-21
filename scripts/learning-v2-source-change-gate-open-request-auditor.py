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

SCRIPT_ID = "learning-v2-source-change-gate-open-request-auditor-v0"

REQUIRED_PRECONDITIONS = {
    "final_gate_auditor_passed_with_visual_evidence",
    "browser_visual_capture_auditor_confirmed",
    "patch_preview_exists",
    "pre_change_evidence_snapshot_exists",
    "rollback_and_post_validation_plan_exists",
    "deploy_remains_blocked",
}

MUST_REMAIN_FALSE = {
    "source_change_gate_allowed",
    "source_change_gate_opened",
    "website_source_written",
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
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is report-only and never opens source_change_gate.")
    args = ap.parse_args()

    request_path = latest_report("learning-v2-source-change-gate-open-request-dry-run-*.json")
    final_gate_path = latest_report("learning-v2-final-source-change-gate-auditor-dry-run-*.json")
    visual_auditor_path = latest_report("learning-v2-browser-visual-capture-auditor-dry-run-*.json")

    if not request_path:
        raise SystemExit("no source-change gate open request report found")
    if not final_gate_path:
        raise SystemExit("no final gate auditor report found")
    if not visual_auditor_path:
        raise SystemExit("no browser visual capture auditor report found")

    request = load_json(request_path, {})
    final_gate = load_json(final_gate_path, {})
    visual_auditor = load_json(visual_auditor_path, {})

    hard_blocks = []
    warnings = []

    if request.get("request_status") != "source_change_gate_open_request_ready_for_audit":
        hard_blocks.append("request_status_not_ready_for_audit")
    if request.get("request_audit_allowed") is not True:
        hard_blocks.append("request_audit_not_allowed")
    if request.get("source_change_gate_allowed") is not False:
        hard_blocks.append("request_allows_source_change_gate_too_early")
    if request.get("source_change_gate_opened") is not False:
        hard_blocks.append("request_opened_source_change_gate")
    if request.get("hard_blocks"):
        hard_blocks.append("request_report_has_hard_blocks")

    if final_gate.get("audit_status") != "gate_open_candidate_ready_but_not_opened":
        hard_blocks.append("final_gate_auditor_not_ready")
    if final_gate.get("visual_evidence_confirmed") is not True:
        hard_blocks.append("final_gate_visual_evidence_not_confirmed")
    if final_gate.get("source_change_gate_allowed") is not False:
        hard_blocks.append("final_gate_allows_source_change_gate_too_early")

    if visual_auditor.get("audit_status") != "browser_visual_capture_ready_for_final_gate_recheck":
        hard_blocks.append("visual_auditor_not_ready")
    if visual_auditor.get("visual_evidence_confirmed") is not True:
        hard_blocks.append("visual_auditor_not_confirmed")

    packet = request.get("request_packet") or {}
    if packet.get("request_type") != "source_change_gate_open_request":
        hard_blocks.append("request_packet_type_invalid")
    if packet.get("requested_gate") != "source_change_gate":
        hard_blocks.append("requested_gate_invalid")

    candidate_files = packet.get("candidate_files") or []
    if not candidate_files:
        hard_blocks.append("request_packet_missing_candidate_files")

    preconditions = set(packet.get("required_preconditions") or [])
    missing_preconditions = sorted(REQUIRED_PRECONDITIONS - preconditions)
    unknown_preconditions = sorted(preconditions - REQUIRED_PRECONDITIONS)
    if missing_preconditions:
        hard_blocks.extend([f"missing_precondition:{x}" for x in missing_preconditions])
    if unknown_preconditions:
        warnings.extend([f"unknown_precondition:{x}" for x in unknown_preconditions])

    must_false = packet.get("must_remain_false_until_separate_gate_opener") or {}
    for k in MUST_REMAIN_FALSE:
        if must_false.get(k) is not False:
            hard_blocks.append(f"must_remain_false_violation:{k}")

    if hard_blocks:
        audit_status = "blocked"
        recommended_next_action = "fix_source_change_gate_open_request_before_gate_opener"
        gate_opener_dry_run_allowed = False
    else:
        audit_status = "source_change_gate_open_request_ready_for_gate_opener_dry_run"
        recommended_next_action = "run_source_change_gate_opener_dry_run"
        gate_opener_dry_run_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "source_change_gate_open_request_source": str(request_path),
        "final_gate_auditor_source": str(final_gate_path),
        "browser_visual_capture_auditor_source": str(visual_auditor_path),
        "audit_status": audit_status,
        "recommended_next_action": recommended_next_action,
        "candidate_file_count": len(candidate_files),
        "candidate_files": candidate_files,
        "gate_opener_dry_run_allowed": gate_opener_dry_run_allowed,
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
    json_path = REPORT_DIR / f"learning-v2-source-change-gate-open-request-auditor-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-source-change-gate-open-request-auditor-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Source-Change Gate Open Request Auditor Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- audit_status: `{audit_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- gate_opener_dry_run_allowed: `{str(gate_opener_dry_run_allowed).lower()}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- source_change_gate_opened: `false`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Candidate Files")
    md.append("")
    for x in candidate_files:
        md.append(f"- `{x}`")
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

    print("source_change_gate_open_request_auditor = ok")
    print("mode = dry_run")
    print("audit_status =", audit_status)
    print("recommended_next_action =", recommended_next_action)
    print("candidate_file_count =", len(candidate_files))
    print("gate_opener_dry_run_allowed =", str(gate_opener_dry_run_allowed).lower())
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
