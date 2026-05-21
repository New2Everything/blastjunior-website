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

SCRIPT_ID = "learning-v2-source-change-gate-opener-auditor-v0"

REQUIRED_NOT_ALLOWED = {
    "business_source_written",
    "website_source_written",
    "git_commit",
    "git_push",
    "deploy",
}

REQUIRED_STILL_REQUIRES = {
    "source_change_gate_opener_auditor",
    "source_change_apply_dry_run",
    "rollback_packet_reconfirm",
    "post_validation_plan_reconfirm",
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
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is report-only and never writes source.")
    args = ap.parse_args()

    opener_path = latest_report("learning-v2-source-change-gate-opener-dry-run-*.json")
    request_auditor_path = latest_report("learning-v2-source-change-gate-open-request-auditor-dry-run-*.json")
    request_path = latest_report("learning-v2-source-change-gate-open-request-dry-run-*.json")

    if not opener_path:
        raise SystemExit("no source-change gate opener report found")
    if not request_auditor_path:
        raise SystemExit("no source-change gate open request auditor report found")
    if not request_path:
        raise SystemExit("no source-change gate open request report found")

    opener = load_json(opener_path, {})
    request_auditor = load_json(request_auditor_path, {})
    request = load_json(request_path, {})

    hard_blocks = []
    warnings = []

    if opener.get("opener_status") != "source_change_gate_opener_dry_run_ready_for_audit":
        hard_blocks.append("opener_status_not_ready_for_audit")
    if opener.get("opener_audit_allowed") is not True:
        hard_blocks.append("opener_audit_not_allowed")
    if opener.get("source_change_gate_allowed") is not False:
        hard_blocks.append("opener_allows_source_change_gate_too_early")
    if opener.get("source_change_gate_opened") is not False:
        hard_blocks.append("opener_opened_source_change_gate")
    if opener.get("hard_blocks"):
        hard_blocks.append("opener_report_has_hard_blocks")

    if request_auditor.get("audit_status") != "source_change_gate_open_request_ready_for_gate_opener_dry_run":
        hard_blocks.append("request_auditor_not_ready_for_gate_opener")
    if request_auditor.get("gate_opener_dry_run_allowed") is not True:
        hard_blocks.append("request_auditor_did_not_allow_gate_opener_dry_run")
    if request_auditor.get("source_change_gate_allowed") is not False:
        hard_blocks.append("request_auditor_allows_gate_too_early")

    if request.get("request_status") != "source_change_gate_open_request_ready_for_audit":
        hard_blocks.append("gate_open_request_not_ready")
    if request.get("source_change_gate_allowed") is not False:
        hard_blocks.append("gate_open_request_allows_gate_too_early")

    gate_open_plan = opener.get("gate_open_plan") or {}
    if gate_open_plan.get("gate") != "source_change_gate":
        hard_blocks.append("gate_open_plan_gate_invalid")
    if gate_open_plan.get("mode") != "dry_run_only":
        hard_blocks.append("gate_open_plan_not_dry_run_only")
    if gate_open_plan.get("next_allowed_stage_after_audited_gate_open") != "controlled_source_change_apply_dry_run":
        hard_blocks.append("next_allowed_stage_invalid")

    candidate_files = gate_open_plan.get("candidate_files") or opener.get("candidate_files") or []
    if not candidate_files:
        hard_blocks.append("gate_open_plan_missing_candidate_files")

    explicitly_not_allowed = set(gate_open_plan.get("explicitly_not_allowed_in_this_step") or [])
    missing_not_allowed = sorted(REQUIRED_NOT_ALLOWED - explicitly_not_allowed)
    if missing_not_allowed:
        hard_blocks.extend([f"missing_explicit_not_allowed:{x}" for x in missing_not_allowed])

    still_requires = set(gate_open_plan.get("still_requires_before_real_source_write") or [])
    missing_still_requires = sorted(REQUIRED_STILL_REQUIRES - still_requires)
    if missing_still_requires:
        hard_blocks.extend([f"missing_still_requires_before_real_write:{x}" for x in missing_still_requires])

    safety = opener.get("safety") or {}
    for k in ["business_source_written", "website_source_written", "source_change_gate_opened", "git_commit", "git_push", "deploy"]:
        if safety.get(k) is not False:
            hard_blocks.append(f"safety_violation:{k}")

    if hard_blocks:
        audit_status = "blocked"
        recommended_next_action = "fix_source_change_gate_opener_before_controlled_apply"
        controlled_apply_dry_run_allowed = False
    else:
        audit_status = "source_change_gate_opener_ready_for_controlled_apply_dry_run"
        recommended_next_action = "run_controlled_source_change_apply_dry_run"
        controlled_apply_dry_run_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "source_change_gate_opener_source": str(opener_path),
        "source_change_gate_open_request_auditor_source": str(request_auditor_path),
        "source_change_gate_open_request_source": str(request_path),
        "audit_status": audit_status,
        "recommended_next_action": recommended_next_action,
        "candidate_file_count": len(candidate_files),
        "candidate_files": candidate_files,
        "controlled_apply_dry_run_allowed": controlled_apply_dry_run_allowed,
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
    json_path = REPORT_DIR / f"learning-v2-source-change-gate-opener-auditor-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-source-change-gate-opener-auditor-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Source-Change Gate Opener Auditor Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- audit_status: `{audit_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- controlled_apply_dry_run_allowed: `{str(controlled_apply_dry_run_allowed).lower()}`")
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

    print("source_change_gate_opener_auditor = ok")
    print("mode = dry_run")
    print("audit_status =", audit_status)
    print("recommended_next_action =", recommended_next_action)
    print("candidate_file_count =", len(candidate_files))
    print("controlled_apply_dry_run_allowed =", str(controlled_apply_dry_run_allowed).lower())
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
