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

SCRIPT_ID = "learning-v2-source-change-gate-opener-v0"

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
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 never writes source and never deploys.")
    args = ap.parse_args()

    request_auditor_path = latest_report("learning-v2-source-change-gate-open-request-auditor-dry-run-*.json")
    request_path = latest_report("learning-v2-source-change-gate-open-request-dry-run-*.json")
    final_gate_path = latest_report("learning-v2-final-source-change-gate-auditor-dry-run-*.json")
    visual_auditor_path = latest_report("learning-v2-browser-visual-capture-auditor-dry-run-*.json")

    if not request_auditor_path:
        raise SystemExit("no source-change gate open request auditor report found")
    if not request_path:
        raise SystemExit("no source-change gate open request report found")
    if not final_gate_path:
        raise SystemExit("no final gate auditor report found")
    if not visual_auditor_path:
        raise SystemExit("no browser visual capture auditor report found")

    request_auditor = load_json(request_auditor_path, {})
    request = load_json(request_path, {})
    final_gate = load_json(final_gate_path, {})
    visual_auditor = load_json(visual_auditor_path, {})

    hard_blocks = []
    warnings = []

    if request_auditor.get("audit_status") != "source_change_gate_open_request_ready_for_gate_opener_dry_run":
        hard_blocks.append("request_auditor_not_ready_for_gate_opener")
    if request_auditor.get("gate_opener_dry_run_allowed") is not True:
        hard_blocks.append("gate_opener_dry_run_not_allowed")
    if request_auditor.get("source_change_gate_allowed") is not False:
        hard_blocks.append("request_auditor_allows_gate_too_early")
    if request_auditor.get("source_change_gate_opened") is not False:
        hard_blocks.append("request_auditor_opened_gate")
    if request_auditor.get("hard_blocks"):
        hard_blocks.append("request_auditor_has_hard_blocks")

    if request.get("request_status") != "source_change_gate_open_request_ready_for_audit":
        hard_blocks.append("gate_open_request_not_ready")
    if request.get("source_change_gate_allowed") is not False:
        hard_blocks.append("gate_open_request_allows_gate_too_early")

    if final_gate.get("audit_status") != "gate_open_candidate_ready_but_not_opened":
        hard_blocks.append("final_gate_not_ready")
    if final_gate.get("visual_evidence_confirmed") is not True:
        hard_blocks.append("final_gate_visual_evidence_not_confirmed")
    if final_gate.get("source_change_gate_allowed") is not False:
        hard_blocks.append("final_gate_allows_gate_too_early")

    if visual_auditor.get("visual_evidence_confirmed") is not True:
        hard_blocks.append("visual_evidence_not_confirmed")

    packet = request.get("request_packet") or {}
    candidate_files = packet.get("candidate_files") or []

    if not candidate_files:
        hard_blocks.append("missing_candidate_files")

    gate_open_plan = {
        "gate": "source_change_gate",
        "mode": "dry_run_only",
        "candidate_files": candidate_files,
        "next_allowed_stage_after_audited_gate_open": "controlled_source_change_apply_dry_run",
        "explicitly_not_allowed_in_this_step": [
            "business_source_written",
            "website_source_written",
            "git_commit",
            "git_push",
            "deploy",
        ],
        "still_requires_before_real_source_write": [
            "source_change_gate_opener_auditor",
            "source_change_apply_dry_run",
            "rollback_packet_reconfirm",
            "post_validation_plan_reconfirm",
        ],
    }

    if hard_blocks:
        opener_status = "blocked"
        recommended_next_action = "fix_source_change_gate_opener_inputs"
        opener_audit_allowed = False
    else:
        opener_status = "source_change_gate_opener_dry_run_ready_for_audit"
        recommended_next_action = "run_source_change_gate_opener_auditor_dry_run"
        opener_audit_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "source_change_gate_open_request_auditor_source": str(request_auditor_path),
        "source_change_gate_open_request_source": str(request_path),
        "final_gate_auditor_source": str(final_gate_path),
        "browser_visual_capture_auditor_source": str(visual_auditor_path),
        "opener_status": opener_status,
        "recommended_next_action": recommended_next_action,
        "candidate_file_count": len(candidate_files),
        "candidate_files": candidate_files,
        "gate_open_plan": gate_open_plan,
        "opener_audit_allowed": opener_audit_allowed,
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
    json_path = REPORT_DIR / f"learning-v2-source-change-gate-opener-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-source-change-gate-opener-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Source-Change Gate Opener Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- opener_status: `{opener_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- opener_audit_allowed: `{str(opener_audit_allowed).lower()}`")
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

    print("source_change_gate_opener = ok")
    print("mode = dry_run")
    print("opener_status =", opener_status)
    print("recommended_next_action =", recommended_next_action)
    print("candidate_file_count =", len(candidate_files))
    print("opener_audit_allowed =", str(opener_audit_allowed).lower())
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
