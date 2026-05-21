#!/usr/bin/env python3
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-controlled-source-change-real-write-executor-v0"

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

def sha256_file(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except Exception:
        return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is dry-run only and never writes website source.")
    args = ap.parse_args()

    route_auditor_path = latest_report("learning-v2-deployment-route-contract-auditor-dry-run-*.json")
    request_auditor_path = latest_report("learning-v2-controlled-source-change-real-write-request-auditor-dry-run-*.json")
    request_path = latest_report("learning-v2-controlled-source-change-real-write-request-dry-run-*.json")
    apply_path = latest_report("learning-v2-controlled-source-change-apply-dry-run-*.json")
    patch_preview_path = latest_report("learning-v2-file-level-patch-preview-dry-run-*.json")
    evidence_snapshot_path = latest_report("learning-v2-pre-change-evidence-snapshot-dry-run-*.json")

    if not route_auditor_path:
        raise SystemExit("no deployment route contract auditor report found")
    if not request_auditor_path:
        raise SystemExit("no controlled real-write request auditor report found")
    if not request_path:
        raise SystemExit("no controlled real-write request report found")
    if not apply_path:
        raise SystemExit("no controlled source-change apply report found")
    if not patch_preview_path:
        raise SystemExit("no file-level patch preview report found")
    if not evidence_snapshot_path:
        raise SystemExit("no pre-change evidence snapshot report found")

    route_auditor = load_json(route_auditor_path, {})
    request_auditor = load_json(request_auditor_path, {})
    request = load_json(request_path, {})
    apply_report = load_json(apply_path, {})
    patch_preview = load_json(patch_preview_path, {})
    evidence_snapshot = load_json(evidence_snapshot_path, {})

    hard_blocks = []
    warnings = []

    if route_auditor.get("audit_status") != "deployment_route_contract_ready_for_real_write_executor_dry_run":
        hard_blocks.append("deployment_route_contract_auditor_not_ready")
    if route_auditor.get("real_write_executor_dry_run_allowed") is not True:
        hard_blocks.append("deployment_route_contract_did_not_allow_executor_dry_run")
    if route_auditor.get("deployment_platform") != "cloudflare_pages":
        hard_blocks.append("deployment_platform_not_cloudflare_pages")
    if route_auditor.get("deployment_trigger") != "github_main_branch_build":
        hard_blocks.append("deployment_trigger_not_github_main_branch_build")
    if route_auditor.get("deploy_allowed") is not False:
        hard_blocks.append("route_auditor_deploy_allowed_too_early")

    if request_auditor.get("audit_status") != "controlled_source_change_real_write_request_ready_for_executor_dry_run":
        hard_blocks.append("real_write_request_auditor_not_ready")
    if request_auditor.get("executor_dry_run_allowed") is not True:
        hard_blocks.append("real_write_request_auditor_did_not_allow_executor_dry_run")
    if request_auditor.get("source_change_gate_allowed") is not False:
        hard_blocks.append("request_auditor_allows_source_change_gate_too_early")

    if request.get("request_status") != "controlled_source_change_real_write_request_ready_for_audit":
        hard_blocks.append("real_write_request_not_ready")
    if apply_report.get("apply_status") != "controlled_source_change_apply_dry_run_ready_for_audit":
        hard_blocks.append("controlled_apply_report_not_ready")
    if patch_preview.get("preview_status") != "patch_preview_ready_for_audit":
        hard_blocks.append("patch_preview_not_ready")
    if evidence_snapshot.get("snapshot_status") != "pre_change_evidence_snapshot_ready_for_audit":
        hard_blocks.append("pre_change_evidence_snapshot_not_ready")

    packet = request.get("request_packet") or {}
    request_items = packet.get("request_items") or []
    candidate_files = packet.get("candidate_files") or []

    if not candidate_files:
        hard_blocks.append("missing_candidate_files")
    if not request_items:
        hard_blocks.append("missing_request_items")

    execution_plan = []
    for item in request_items:
        rel = item.get("path")
        item_blocks = []
        item_warnings = []

        source_path = WORKSPACE / rel if rel else None
        source_exists = bool(source_path and source_path.exists())
        current_sha256 = sha256_file(source_path) if source_exists else None

        if not rel:
            item_blocks.append("missing_path")
        else:
            if rel not in candidate_files:
                item_blocks.append("path_not_in_candidate_files")
            if not source_exists:
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

        execution_plan.append({
            "path": rel,
            "requested_operation": item.get("requested_operation") or "previewed_change",
            "source_exists": source_exists,
            "current_sha256": current_sha256,
            "would_write_source_if_apply_enabled": True,
            "actual_source_written": False,
            "actual_git_commit": False,
            "actual_git_push": False,
            "actual_deploy": False,
            "requires_post_write_validation": True,
            "requires_git_diff_audit_before_commit": True,
            "requires_github_main_push_before_cloudflare_pages_deploy": True,
            "hard_blocks": item_blocks,
            "warnings": item_warnings,
        })

        hard_blocks.extend([f"{rel}:{x}" for x in item_blocks])
        warnings.extend([f"{rel}:{x}" for x in item_warnings])

    if hard_blocks:
        executor_status = "blocked"
        recommended_next_action = "fix_controlled_real_write_executor_inputs"
        executor_audit_allowed = False
    else:
        executor_status = "controlled_source_change_real_write_executor_dry_run_ready_for_audit"
        recommended_next_action = "run_controlled_source_change_real_write_executor_auditor_dry_run"
        executor_audit_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "deployment_route_contract_auditor_source": str(route_auditor_path),
        "controlled_real_write_request_auditor_source": str(request_auditor_path),
        "controlled_real_write_request_source": str(request_path),
        "controlled_apply_source": str(apply_path),
        "patch_preview_source": str(patch_preview_path),
        "pre_change_evidence_snapshot_source": str(evidence_snapshot_path),
        "executor_status": executor_status,
        "recommended_next_action": recommended_next_action,
        "candidate_file_count": len(candidate_files),
        "execution_plan": execution_plan,
        "executor_audit_allowed": executor_audit_allowed,
        "deployment_route": {
            "github_repo": route_auditor.get("github_repo"),
            "github_branch": route_auditor.get("github_branch"),
            "deployment_platform": route_auditor.get("deployment_platform"),
            "deployment_trigger": route_auditor.get("deployment_trigger"),
        },
        "hard_blocks": hard_blocks,
        "warnings": warnings,
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
    json_path = REPORT_DIR / f"learning-v2-controlled-source-change-real-write-executor-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-controlled-source-change-real-write-executor-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Controlled Source-Change Real-Write Executor Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- executor_status: `{executor_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- executor_audit_allowed: `{str(executor_audit_allowed).lower()}`")
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
    md.append("## Execution Plan")
    md.append("")
    for x in execution_plan:
        md.append(f"### {x['path']}")
        md.append(f"- source_exists: `{str(x['source_exists']).lower()}`")
        md.append(f"- would_write_source_if_apply_enabled: `true`")
        md.append(f"- actual_source_written: `false`")
        md.append(f"- current_sha256: `{x['current_sha256']}`")
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

    print("controlled_source_change_real_write_executor = ok")
    print("mode = dry_run")
    print("executor_status =", executor_status)
    print("recommended_next_action =", recommended_next_action)
    print("candidate_file_count =", len(candidate_files))
    print("executor_audit_allowed =", str(executor_audit_allowed).lower())
    print("github_repo =", route_auditor.get("github_repo"))
    print("github_branch =", route_auditor.get("github_branch"))
    print("deployment_platform =", route_auditor.get("deployment_platform"))
    print("deployment_trigger =", route_auditor.get("deployment_trigger"))
    print("source_change_gate_allowed = false")
    print("source_change_gate_opened = false")
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
