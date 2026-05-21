#!/usr/bin/env python3
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-pre-change-evidence-snapshot-v0"

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

def run_cmd(args):
    p = subprocess.run(
        args,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return {
        "args": args,
        "returncode": p.returncode,
        "output": p.stdout.strip(),
    }

def file_snapshot(path):
    p = WORKSPACE / path
    if not p.exists() or not p.is_file():
        return {
            "path": path,
            "exists": False,
            "sha256": None,
            "size_bytes": None,
        }
    data = p.read_bytes()
    return {
        "path": path,
        "exists": True,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is report-only and never edits website source.")
    args = ap.parse_args()

    policy_path = latest_report("learning-v2-source-change-gate-open-policy-dry-run-*.json")
    preview_path = latest_report("learning-v2-file-level-patch-preview-dry-run-*.json")
    auditor_path = latest_report("learning-v2-patch-preview-auditor-dry-run-*.json")

    if not policy_path:
        raise SystemExit("no source-change gate open policy report found")
    if not preview_path:
        raise SystemExit("no file-level patch preview report found")
    if not auditor_path:
        raise SystemExit("no patch preview auditor report found")

    policy = load_json(policy_path, {})
    preview = load_json(preview_path, {})
    auditor = load_json(auditor_path, {})

    hard_blocks = []
    warnings = []

    if policy.get("policy_decision") != "require_pre_change_evidence_before_gate":
        hard_blocks.append("gate_policy_does_not_require_pre_change_evidence")
    if policy.get("pre_change_evidence_required") is not True:
        hard_blocks.append("pre_change_evidence_not_required_by_policy")
    if policy.get("source_change_gate_allowed") is not False:
        hard_blocks.append("policy_allows_source_change_gate_too_early")
    if policy.get("source_change_gate_opened") is not False:
        hard_blocks.append("policy_opened_source_change_gate")

    if preview.get("preview_status") != "patch_preview_ready_for_audit":
        hard_blocks.append("patch_preview_not_ready")
    if auditor.get("audit_status") != "patch_preview_ready_for_gate_policy_review":
        hard_blocks.append("patch_preview_auditor_not_ready_for_gate_policy")

    patch_previews = preview.get("patch_previews") or []
    if not patch_previews:
        hard_blocks.append("no_patch_previews_available")

    files = []
    for p in patch_previews:
        path = p.get("path")
        if path:
            files.append(path)

    files = sorted(set(files))
    snapshots = [file_snapshot(x) for x in files]

    missing = [x["path"] for x in snapshots if not x["exists"]]
    if missing:
        hard_blocks.extend([f"{x}:missing_file_for_snapshot" for x in missing])

    git_status = run_cmd(["git", "status", "-sb"])
    git_diff_name_status = run_cmd(["git", "diff", "--name-status"])
    git_log_head = run_cmd(["git", "log", "-1", "--oneline", "--decorate"])

    dirty_lines = [
        line for line in git_status.get("output", "").splitlines()
        if line and not line.startswith("##")
    ]

    tracked_business_dirty = [
        line for line in dirty_lines
        if any(x in line for x in [
            "public/index.html",
            "public/gallery.html",
            "public/news.html",
            "public/profile.html",
            "public/styles.css",
            "components/nav.html",
        ])
    ]

    if tracked_business_dirty:
        hard_blocks.append("candidate_business_files_dirty_before_gate")

    sensitive_files = sorted(set(policy.get("sensitive_files") or []))
    medium_or_higher = sorted(set(policy.get("medium_or_higher_files") or []))

    evidence_items = {
        "file_hash_snapshots": True,
        "git_status_snapshot": True,
        "sensitive_files_identified": bool(sensitive_files),
        "mobile_validation_required": "mobile_validation_required_for_sensitive_surfaces" in (policy.get("required_before_gate_open") or []),
        "screenshot_or_visual_snapshot_required": "pre_change_screenshot_or_snapshot_required" in (policy.get("required_before_gate_open") or []),
        "actual_browser_screenshot_captured": False,
        "reason_actual_screenshot_not_captured": "v0 records requirement only; screenshot capture should be handled by a later visual evidence module",
    }

    required_next_evidence = []
    if evidence_items["mobile_validation_required"]:
        required_next_evidence.append("mobile_visual_snapshot_or_validation_module")
    if evidence_items["screenshot_or_visual_snapshot_required"]:
        required_next_evidence.append("pre_change_visual_snapshot_module")
    if medium_or_higher:
        required_next_evidence.append("explicit_rollback_packet_module")
        required_next_evidence.append("post_validation_command_plan_module")

    by_file_exists = Counter(str(x["exists"]).lower() for x in snapshots)

    if hard_blocks:
        snapshot_status = "blocked"
        recommended_next_action = "fix_pre_change_evidence_inputs_before_gate"
        evidence_audit_allowed = False
    else:
        snapshot_status = "pre_change_evidence_snapshot_ready_for_audit"
        recommended_next_action = "run_pre_change_evidence_auditor_before_gate"
        evidence_audit_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "gate_policy_source": str(policy_path),
        "patch_preview_source": str(preview_path),
        "patch_preview_auditor_source": str(auditor_path),
        "snapshot_status": snapshot_status,
        "recommended_next_action": recommended_next_action,
        "candidate_file_count": len(files),
        "file_snapshots": snapshots,
        "by_file_exists": dict(by_file_exists),
        "sensitive_files": sensitive_files,
        "medium_or_higher_files": medium_or_higher,
        "evidence_items": evidence_items,
        "required_next_evidence": sorted(set(required_next_evidence)),
        "git": {
            "status_sb": git_status,
            "diff_name_status": git_diff_name_status,
            "head": git_log_head,
            "tracked_business_dirty": tracked_business_dirty,
        },
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "evidence_audit_allowed": evidence_audit_allowed,
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
    json_path = REPORT_DIR / f"learning-v2-pre-change-evidence-snapshot-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-pre-change-evidence-snapshot-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Pre-Change Evidence Snapshot Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- snapshot_status: `{snapshot_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- candidate_file_count: `{len(files)}`")
    md.append(f"- evidence_audit_allowed: `{str(evidence_audit_allowed).lower()}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## File Snapshots")
    md.append("")
    for x in snapshots:
        md.append(f"- `{x['path']}` exists=`{str(x['exists']).lower()}` sha256=`{x['sha256']}` size=`{x['size_bytes']}`")
    md.append("")
    md.append("## Required Next Evidence")
    md.append("")
    if payload["required_next_evidence"]:
        for x in payload["required_next_evidence"]:
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
    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("pre_change_evidence_snapshot = ok")
    print("mode = dry_run")
    print("snapshot_status =", snapshot_status)
    print("recommended_next_action =", recommended_next_action)
    print("candidate_file_count =", len(files))
    print("sensitive_files =", json.dumps(sensitive_files, ensure_ascii=False))
    print("required_next_evidence =", json.dumps(payload["required_next_evidence"], ensure_ascii=False))
    print("evidence_audit_allowed =", str(evidence_audit_allowed).lower())
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
