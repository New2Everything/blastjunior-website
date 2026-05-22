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

SCRIPT_ID = "learning-v2-controlled-source-change-actual-source-write-gate-opener-v0"

EXPECTED_REPO = "New2Everything/blastjunior-website"
EXPECTED_BRANCH = "main"
EXPECTED_PLATFORM = "cloudflare_pages"
EXPECTED_TRIGGER = "github_main_branch_build"

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
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is dry-run only and never opens actual source-write gate.")
    args = ap.parse_args()

    gate_request_auditor_path = latest_report("learning-v2-controlled-source-change-actual-source-write-gate-request-auditor-dry-run-*.json")
    gate_request_path = latest_report("learning-v2-controlled-source-change-actual-source-write-gate-request-dry-run-*.json")
    apply_executor_auditor_path = latest_report("learning-v2-controlled-source-change-real-write-apply-executor-auditor-dry-run-*.json")
    route_auditor_path = latest_report("learning-v2-deployment-route-contract-auditor-dry-run-*.json")
    patch_preview_path = latest_report("learning-v2-file-level-patch-preview-dry-run-*.json")
    evidence_snapshot_path = latest_report("learning-v2-pre-change-evidence-snapshot-dry-run-*.json")

    for label, path in [
        ("actual source-write gate request auditor", gate_request_auditor_path),
        ("actual source-write gate request", gate_request_path),
        ("controlled real-write apply executor auditor", apply_executor_auditor_path),
        ("deployment route contract auditor", route_auditor_path),
        ("file-level patch preview", patch_preview_path),
        ("pre-change evidence snapshot", evidence_snapshot_path),
    ]:
        if not path:
            raise SystemExit(f"no {label} report found")

    gate_request_auditor = load_json(gate_request_auditor_path, {})
    gate_request = load_json(gate_request_path, {})
    apply_executor_auditor = load_json(apply_executor_auditor_path, {})
    route_auditor = load_json(route_auditor_path, {})
    patch_preview = load_json(patch_preview_path, {})
    evidence_snapshot = load_json(evidence_snapshot_path, {})

    hard_blocks = []
    warnings = []

    if gate_request_auditor.get("audit_status") != "controlled_source_change_actual_source_write_gate_request_ready_for_gate_opener_dry_run":
        hard_blocks.append("gate_request_auditor_not_ready_for_gate_opener")
    if gate_request_auditor.get("gate_opener_dry_run_allowed") is not True:
        hard_blocks.append("gate_opener_dry_run_not_allowed")
    if gate_request_auditor.get("actual_source_write_allowed") is not False:
        hard_blocks.append("gate_request_auditor_allows_actual_source_write_too_early")
    if gate_request_auditor.get("actual_source_write_gate_opened") is not False:
        hard_blocks.append("gate_request_auditor_opened_actual_source_write_gate")
    if gate_request_auditor.get("deploy_allowed") is not False:
        hard_blocks.append("gate_request_auditor_deploy_allowed_too_early")
    if gate_request_auditor.get("hard_blocks"):
        hard_blocks.append("gate_request_auditor_has_hard_blocks")

    if gate_request.get("request_status") != "controlled_source_change_actual_source_write_gate_request_ready_for_audit":
        hard_blocks.append("gate_request_not_ready")
    if gate_request.get("actual_source_write_allowed") is not False:
        hard_blocks.append("gate_request_allows_actual_source_write_too_early")
    if gate_request.get("actual_source_write_gate_opened") is not False:
        hard_blocks.append("gate_request_opened_actual_source_write_gate")

    if apply_executor_auditor.get("audit_status") != "controlled_source_change_real_write_apply_executor_ready_for_actual_source_write_gate_request_dry_run":
        hard_blocks.append("apply_executor_auditor_not_ready")
    if apply_executor_auditor.get("actual_source_write_gate_request_allowed") is not True:
        hard_blocks.append("apply_executor_auditor_did_not_allow_gate_request")
    if apply_executor_auditor.get("actual_source_write_allowed") is not False:
        hard_blocks.append("apply_executor_auditor_allows_actual_source_write_too_early")

    if route_auditor.get("audit_status") != "deployment_route_contract_ready_for_real_write_executor_dry_run":
        hard_blocks.append("deployment_route_auditor_not_ready")
    if route_auditor.get("github_repo") != EXPECTED_REPO:
        hard_blocks.append("route_auditor_github_repo_mismatch")
    if route_auditor.get("github_branch") != EXPECTED_BRANCH:
        hard_blocks.append("route_auditor_github_branch_mismatch")
    if route_auditor.get("deployment_platform") != EXPECTED_PLATFORM:
        hard_blocks.append("route_auditor_platform_mismatch")
    if route_auditor.get("deployment_trigger") != EXPECTED_TRIGGER:
        hard_blocks.append("route_auditor_trigger_mismatch")
    if route_auditor.get("deploy_allowed") is not False:
        hard_blocks.append("route_auditor_deploy_allowed_too_early")

    if patch_preview.get("preview_status") != "patch_preview_ready_for_audit":
        hard_blocks.append("patch_preview_not_ready")
    if evidence_snapshot.get("snapshot_status") != "pre_change_evidence_snapshot_ready_for_audit":
        hard_blocks.append("pre_change_evidence_snapshot_not_ready")

    packet = gate_request.get("gate_request_packet") or {}
    candidate_files = packet.get("candidate_files") or []
    gate_items = packet.get("gate_items") or []
    route = packet.get("deployment_route") or {}

    if route.get("github_repo") != EXPECTED_REPO:
        hard_blocks.append("packet_route_github_repo_mismatch")
    if route.get("github_branch") != EXPECTED_BRANCH:
        hard_blocks.append("packet_route_github_branch_mismatch")
    if route.get("deployment_platform") != EXPECTED_PLATFORM:
        hard_blocks.append("packet_route_platform_mismatch")
    if route.get("deployment_trigger") != EXPECTED_TRIGGER:
        hard_blocks.append("packet_route_trigger_mismatch")

    if not candidate_files:
        hard_blocks.append("missing_candidate_files")
    if not gate_items:
        hard_blocks.append("missing_gate_items")

    dry_run_gate_items = []
    for item in gate_items:
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

        if item.get("request_open_actual_source_write_gate") is not True:
            item_blocks.append("request_open_actual_source_write_gate_not_true")
        if item.get("actual_source_write_allowed_by_this_step") is not False:
            item_blocks.append("actual_source_write_allowed_by_this_step_not_false")
        if item.get("requires_explicit_human_approval_before_actual_write") is not True:
            item_blocks.append("requires_explicit_human_approval_before_actual_write_not_true")
        if item.get("requires_actual_write_executor_dry_run") is not True:
            item_blocks.append("requires_actual_write_executor_dry_run_not_true")
        if item.get("requires_actual_write_executor_auditor") is not True:
            item_blocks.append("requires_actual_write_executor_auditor_not_true")
        if item.get("requires_post_write_validation") is not True:
            item_blocks.append("requires_post_write_validation_not_true")
        if item.get("requires_git_diff_audit_before_commit") is not True:
            item_blocks.append("requires_git_diff_audit_before_commit_not_true")
        if item.get("requires_github_main_push_before_cloudflare_pages_deploy") is not True:
            item_blocks.append("requires_github_main_push_before_cloudflare_pages_deploy_not_true")
        if item.get("git_commit_allowed") is not False:
            item_blocks.append("git_commit_allowed_not_false")
        if item.get("git_push_allowed") is not False:
            item_blocks.append("git_push_allowed_not_false")
        if item.get("cloudflare_deploy_allowed") is not False:
            item_blocks.append("cloudflare_deploy_allowed_not_false")
        if item.get("deploy_allowed") is not False:
            item_blocks.append("deploy_allowed_not_false")
        if item.get("hard_blocks"):
            item_blocks.append("gate_item_has_hard_blocks")

        dry_run_gate_items.append({
            "path": rel,
            "requested_operation": item.get("requested_operation") or "previewed_change",
            "would_open_actual_source_write_gate_if_apply_enabled": True,
            "actual_source_write_gate_opened": False,
            "actual_source_write_allowed": False,
            "actual_source_written": False,
            "git_commit_allowed": False,
            "git_push_allowed": False,
            "cloudflare_deploy_allowed": False,
            "deploy_allowed": False,
            "requires_gate_opener_auditor": True,
            "requires_actual_write_executor_dry_run": True,
            "requires_actual_write_executor_auditor": True,
            "requires_post_write_validation": True,
            "requires_git_diff_audit_before_commit": True,
            "requires_github_main_push_before_cloudflare_pages_deploy": True,
            "hard_blocks": item_blocks,
            "warnings": item_warnings,
        })

        hard_blocks.extend([f"{rel}:{x}" for x in item_blocks])
        warnings.extend([f"{rel}:{x}" for x in item_warnings])

    if hard_blocks:
        opener_status = "blocked"
        recommended_next_action = "fix_actual_source_write_gate_opener_inputs"
        gate_opener_audit_allowed = False
    else:
        opener_status = "controlled_source_change_actual_source_write_gate_opener_dry_run_ready_for_audit"
        recommended_next_action = "run_controlled_source_change_actual_source_write_gate_opener_auditor_dry_run"
        gate_opener_audit_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "actual_source_write_gate_request_auditor_source": str(gate_request_auditor_path),
        "actual_source_write_gate_request_source": str(gate_request_path),
        "controlled_real_write_apply_executor_auditor_source": str(apply_executor_auditor_path),
        "deployment_route_contract_auditor_source": str(route_auditor_path),
        "patch_preview_source": str(patch_preview_path),
        "pre_change_evidence_snapshot_source": str(evidence_snapshot_path),
        "opener_status": opener_status,
        "recommended_next_action": recommended_next_action,
        "candidate_file_count": len(candidate_files),
        "dry_run_gate_items": dry_run_gate_items,
        "gate_opener_audit_allowed": gate_opener_audit_allowed,
        "actual_source_write_allowed": False,
        "actual_source_write_gate_opened": False,
        "actual_source_written": False,
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "deployment_route": {
            "github_repo": EXPECTED_REPO,
            "github_branch": EXPECTED_BRANCH,
            "deployment_platform": EXPECTED_PLATFORM,
            "deployment_trigger": EXPECTED_TRIGGER,
        },
        "source_change_gate_allowed": False,
        "source_change_gate_opened": False,
        "deploy_allowed": False,
        "safety": {
            "state_written": False,
            "business_source_written": False,
            "website_source_written": False,
            "git_commit": False,
            "git_push": False,
            "cloudflare_deploy": False,
            "deploy": False,
        },
    }

    ts = stamp()
    json_path = REPORT_DIR / f"learning-v2-controlled-source-change-actual-source-write-gate-opener-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-controlled-source-change-actual-source-write-gate-opener-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Actual Source-Write Gate Opener Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- opener_status: `{opener_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- gate_opener_audit_allowed: `{str(gate_opener_audit_allowed).lower()}`")
    md.append(f"- actual_source_write_allowed: `false`")
    md.append(f"- actual_source_write_gate_opened: `false`")
    md.append(f"- actual_source_written: `false`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- git_commit: `false`")
    md.append(f"- git_push: `false`")
    md.append(f"- cloudflare_deploy: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Deployment Route")
    md.append("")
    for k, v in payload["deployment_route"].items():
        md.append(f"- {k}: `{v}`")
    md.append("")
    md.append("## Candidate Files")
    md.append("")
    for x in sorted(set(candidate_files)):
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

    print("controlled_source_change_actual_source_write_gate_opener = ok")
    print("mode = dry_run")
    print("opener_status =", opener_status)
    print("recommended_next_action =", recommended_next_action)
    print("candidate_file_count =", len(candidate_files))
    print("gate_opener_audit_allowed =", str(gate_opener_audit_allowed).lower())
    print("actual_source_write_allowed = false")
    print("actual_source_write_gate_opened = false")
    print("actual_source_written = false")
    print("github_repo =", EXPECTED_REPO)
    print("github_branch =", EXPECTED_BRANCH)
    print("deployment_platform =", EXPECTED_PLATFORM)
    print("deployment_trigger =", EXPECTED_TRIGGER)
    print("source_change_gate_allowed = false")
    print("source_change_gate_opened = false")
    print("deploy_allowed = false")
    print("website_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("cloudflare_deploy = false")
    print("deploy = false")
    print("hard_blocks =", json.dumps(hard_blocks, ensure_ascii=False))
    print("warnings =", json.dumps(warnings, ensure_ascii=False))
    print("report_json =", json_path)
    print("report_md =", md_path)

if __name__ == "__main__":
    raise SystemExit(main())
