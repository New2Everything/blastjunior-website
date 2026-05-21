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

SCRIPT_ID = "learning-v2-pre-change-evidence-auditor-v0"

REQUIRED_NEXT_EVIDENCE_ALLOWLIST = {
    "explicit_rollback_packet_module",
    "mobile_visual_snapshot_or_validation_module",
    "post_validation_command_plan_module",
    "pre_change_visual_snapshot_module",
}

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

    snapshot_path = latest_report("learning-v2-pre-change-evidence-snapshot-dry-run-*.json")
    gate_policy_path = latest_report("learning-v2-source-change-gate-open-policy-dry-run-*.json")
    patch_preview_path = latest_report("learning-v2-file-level-patch-preview-dry-run-*.json")

    if not snapshot_path:
        raise SystemExit("no pre-change evidence snapshot report found")
    if not gate_policy_path:
        raise SystemExit("no source-change gate open policy report found")
    if not patch_preview_path:
        raise SystemExit("no file-level patch preview report found")

    snapshot = load_json(snapshot_path, {})
    gate_policy = load_json(gate_policy_path, {})
    patch_preview = load_json(patch_preview_path, {})

    hard_blocks = []
    warnings = list(snapshot.get("warnings") or [])

    if snapshot.get("snapshot_status") != "pre_change_evidence_snapshot_ready_for_audit":
        hard_blocks.append("snapshot_status_not_ready_for_audit")
    if snapshot.get("evidence_audit_allowed") is not True:
        hard_blocks.append("evidence_audit_not_allowed")
    if snapshot.get("source_change_gate_allowed") is not False:
        hard_blocks.append("snapshot_allows_source_change_gate_too_early")
    if snapshot.get("source_change_gate_opened") is not False:
        hard_blocks.append("snapshot_opened_source_change_gate")
    if snapshot.get("hard_blocks"):
        hard_blocks.append("snapshot_has_hard_blocks")

    if gate_policy.get("policy_decision") != "require_pre_change_evidence_before_gate":
        hard_blocks.append("gate_policy_not_requiring_pre_change_evidence")
    if gate_policy.get("source_change_gate_allowed") is not False:
        hard_blocks.append("gate_policy_allows_source_change_gate_too_early")
    if patch_preview.get("source_change_gate_allowed") is not False:
        hard_blocks.append("patch_preview_allows_source_change_gate_too_early")

    file_snapshots = snapshot.get("file_snapshots") or []
    candidate_file_count = int(snapshot.get("candidate_file_count") or 0)

    if candidate_file_count <= 0:
        hard_blocks.append("no_candidate_files_in_snapshot")
    if len(file_snapshots) != candidate_file_count:
        hard_blocks.append("file_snapshot_count_mismatch")

    audited_files = []
    for fs in file_snapshots:
        path = fs.get("path")
        file_blocks = []
        file_warnings = []

        if not path:
            file_blocks.append("missing_path")
        if fs.get("exists") is not True:
            file_blocks.append("file_missing")
        if not fs.get("sha256"):
            file_blocks.append("missing_sha256")
        if not fs.get("size_bytes"):
            file_warnings.append("size_bytes_missing_or_zero")

        if path in ("public/index.html", "components/nav.html"):
            file_warnings.append("sensitive_surface_evidence_requires_visual_or_mobile_followup")

        audited_files.append({
            "path": path,
            "exists": fs.get("exists"),
            "sha256_present": bool(fs.get("sha256")),
            "size_bytes": fs.get("size_bytes"),
            "hard_blocks": file_blocks,
            "warnings": file_warnings,
        })

        hard_blocks.extend([f"{path}:{x}" for x in file_blocks])
        warnings.extend([f"{path}:{x}" for x in file_warnings])

    git_info = snapshot.get("git") or {}
    tracked_business_dirty = git_info.get("tracked_business_dirty") or []
    if tracked_business_dirty:
        hard_blocks.append("tracked_candidate_business_files_dirty_before_gate")

    required_next_evidence = snapshot.get("required_next_evidence") or []
    unknown_required = sorted(set(required_next_evidence) - REQUIRED_NEXT_EVIDENCE_ALLOWLIST)
    if unknown_required:
        hard_blocks.extend([f"unknown_required_next_evidence:{x}" for x in unknown_required])

    evidence_items = snapshot.get("evidence_items") or {}
    if evidence_items.get("file_hash_snapshots") is not True:
        hard_blocks.append("file_hash_snapshots_not_confirmed")
    if evidence_items.get("git_status_snapshot") is not True:
        hard_blocks.append("git_status_snapshot_not_confirmed")

    sensitive_files = snapshot.get("sensitive_files") or []
    if sensitive_files and evidence_items.get("mobile_validation_required") is not True:
        warnings.append("sensitive_files_exist_but_mobile_validation_flag_not_true")

    if hard_blocks:
        audit_status = "blocked"
        recommended_next_action = "fix_pre_change_evidence_snapshot_before_gate"
        required_evidence_modules_allowed = False
    elif required_next_evidence:
        audit_status = "pre_change_evidence_ready_for_required_evidence_modules"
        recommended_next_action = "build_required_gate_evidence_modules_dry_run"
        required_evidence_modules_allowed = True
    else:
        audit_status = "pre_change_evidence_ready_for_final_gate_policy"
        recommended_next_action = "run_final_gate_open_auditor_dry_run"
        required_evidence_modules_allowed = False

    by_file_exists = Counter(str(x.get("exists")).lower() for x in file_snapshots)

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "pre_change_evidence_snapshot_source": str(snapshot_path),
        "gate_policy_source": str(gate_policy_path),
        "patch_preview_source": str(patch_preview_path),
        "audit_status": audit_status,
        "recommended_next_action": recommended_next_action,
        "candidate_file_count": candidate_file_count,
        "file_snapshot_count": len(file_snapshots),
        "by_file_exists": dict(by_file_exists),
        "sensitive_files": sensitive_files,
        "required_next_evidence": required_next_evidence,
        "audited_files": audited_files,
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "required_evidence_modules_allowed": required_evidence_modules_allowed,
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
    json_path = REPORT_DIR / f"learning-v2-pre-change-evidence-auditor-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-pre-change-evidence-auditor-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Pre-Change Evidence Auditor Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- audit_status: `{audit_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- candidate_file_count: `{candidate_file_count}`")
    md.append(f"- file_snapshot_count: `{len(file_snapshots)}`")
    md.append(f"- required_evidence_modules_allowed: `{str(required_evidence_modules_allowed).lower()}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- source_change_gate_opened: `false`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Required Next Evidence")
    md.append("")
    if required_next_evidence:
        for x in required_next_evidence:
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
    md.append("## Audited Files")
    md.append("")
    for x in audited_files:
        md.append(f"### {x['path']}")
        md.append(f"- exists: `{str(x['exists']).lower()}`")
        md.append(f"- sha256_present: `{str(x['sha256_present']).lower()}`")
        md.append(f"- size_bytes: `{x['size_bytes']}`")
        md.append(f"- hard_blocks: `{x['hard_blocks']}`")
        md.append(f"- warnings: `{x['warnings']}`")
        md.append("")
    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("pre_change_evidence_auditor = ok")
    print("mode = dry_run")
    print("audit_status =", audit_status)
    print("recommended_next_action =", recommended_next_action)
    print("candidate_file_count =", candidate_file_count)
    print("file_snapshot_count =", len(file_snapshots))
    print("required_next_evidence =", json.dumps(required_next_evidence, ensure_ascii=False))
    print("required_evidence_modules_allowed =", str(required_evidence_modules_allowed).lower())
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
