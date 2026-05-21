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

SCRIPT_ID = "learning-v2-deployment-route-contract-auditor-v0"

EXPECTED_REPO = "New2Everything/blastjunior-website"
EXPECTED_BRANCH = "main"
EXPECTED_PLATFORM = "cloudflare_pages"
EXPECTED_SOURCE_OF_TRUTH = "github_main_branch"

REQUIRED_API_ALLOWED = {
    "check_pages_deployment_status",
    "trigger_pages_build_if_needed",
    "rollback_pages_deployment_if_needed",
    "purge_cache_if_needed",
    "inspect_d1_r2_kv_worker_bindings",
}

REQUIRED_API_FORBIDDEN = {
    "direct_upload_site_source_to_production",
    "bypass_github_main_branch",
    "write_cloudflare_token_to_repo",
    "deploy_uncommitted_local_files",
    "mix_d1_r2_kv_worker_mutations_with_static_site_source_change",
}

REQUIRED_FORBIDDEN_ROUTES = {
    "wrangler_pages_deploy_direct_from_local_source",
    "manual_production_file_upload",
    "cloudflare_api_direct_source_publish",
    "deploy_without_git_push_origin_main",
    "deploy_with_tokens_or_secrets_written_to_repo",
}

REQUIRED_SEPARATE_GATES = {
    "cloudflare_d1_schema_change",
    "cloudflare_r2_data_policy_change",
    "cloudflare_kv_session_or_presence_change",
    "cloudflare_worker_route_or_binding_change",
    "environment_secret_change",
}

MUST_REMAIN_FALSE = {
    "business_source_written",
    "website_source_written",
    "git_commit",
    "git_push",
    "cloudflare_deploy",
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
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is report-only and never deploys.")
    args = ap.parse_args()

    contract_path = latest_report("learning-v2-deployment-route-contract-dry-run-*.json")
    real_write_request_auditor_path = latest_report("learning-v2-controlled-source-change-real-write-request-auditor-dry-run-*.json")

    if not contract_path:
        raise SystemExit("no deployment route contract report found")
    if not real_write_request_auditor_path:
        raise SystemExit("no controlled real-write request auditor report found")

    contract_report = load_json(contract_path, {})
    real_write_request_auditor = load_json(real_write_request_auditor_path, {})

    hard_blocks = []
    warnings = []

    if contract_report.get("contract_status") != "deployment_route_contract_ready_for_audit":
        hard_blocks.append("contract_status_not_ready_for_audit")
    if contract_report.get("contract_audit_allowed") is not True:
        hard_blocks.append("contract_audit_not_allowed")
    if contract_report.get("deploy_allowed") is not False:
        hard_blocks.append("contract_deploy_allowed_too_early")
    if contract_report.get("source_change_gate_allowed") is not False:
        hard_blocks.append("contract_allows_source_change_gate_too_early")
    if contract_report.get("source_change_gate_opened") is not False:
        hard_blocks.append("contract_opened_source_change_gate")
    if contract_report.get("hard_blocks"):
        hard_blocks.append("contract_report_has_hard_blocks")

    if real_write_request_auditor.get("audit_status") != "controlled_source_change_real_write_request_ready_for_executor_dry_run":
        hard_blocks.append("real_write_request_auditor_not_ready")
    if real_write_request_auditor.get("executor_dry_run_allowed") is not True:
        hard_blocks.append("real_write_executor_dry_run_not_allowed")

    contract = contract_report.get("deployment_route_contract") or {}

    if contract.get("website_source_of_truth") != EXPECTED_SOURCE_OF_TRUTH:
        hard_blocks.append("website_source_of_truth_not_github_main_branch")

    github = contract.get("github") or {}
    if github.get("repo") != EXPECTED_REPO:
        hard_blocks.append("github_repo_mismatch")
    if github.get("branch") != EXPECTED_BRANCH:
        hard_blocks.append("github_branch_mismatch")
    if github.get("push_target") != "origin/main":
        hard_blocks.append("github_push_target_not_origin_main")

    cf = contract.get("cloudflare") or {}
    if cf.get("deployment_platform") != EXPECTED_PLATFORM:
        hard_blocks.append("cloudflare_platform_not_pages")
    if cf.get("deployment_trigger") != "github_main_branch_build":
        hard_blocks.append("cloudflare_deployment_trigger_not_github_main_build")

    allowed = set(cf.get("api_allowed_uses") or [])
    forbidden = set(cf.get("api_forbidden_uses") or [])
    forbidden_routes = set(contract.get("forbidden_routes") or [])
    separate_gates = set(contract.get("separate_gate_required_for") or [])

    missing_allowed = sorted(REQUIRED_API_ALLOWED - allowed)
    missing_forbidden = sorted(REQUIRED_API_FORBIDDEN - forbidden)
    missing_forbidden_routes = sorted(REQUIRED_FORBIDDEN_ROUTES - forbidden_routes)
    missing_separate_gates = sorted(REQUIRED_SEPARATE_GATES - separate_gates)

    hard_blocks.extend([f"missing_api_allowed_use:{x}" for x in missing_allowed])
    hard_blocks.extend([f"missing_api_forbidden_use:{x}" for x in missing_forbidden])
    hard_blocks.extend([f"missing_forbidden_route:{x}" for x in missing_forbidden_routes])
    hard_blocks.extend([f"missing_separate_gate:{x}" for x in missing_separate_gates])

    must_false = contract.get("must_remain_false_in_this_step") or {}
    for k in MUST_REMAIN_FALSE:
        if must_false.get(k) is not False:
            hard_blocks.append(f"must_remain_false_violation:{k}")

    safety = contract_report.get("safety") or {}
    for k in MUST_REMAIN_FALSE:
        if safety.get(k) is not False:
            hard_blocks.append(f"safety_violation:{k}")

    if hard_blocks:
        audit_status = "blocked"
        recommended_next_action = "fix_deployment_route_contract_before_real_write_executor"
        real_write_executor_dry_run_allowed = False
    else:
        audit_status = "deployment_route_contract_ready_for_real_write_executor_dry_run"
        recommended_next_action = "run_controlled_source_change_real_write_executor_dry_run"
        real_write_executor_dry_run_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "deployment_route_contract_source": str(contract_path),
        "controlled_source_change_real_write_request_auditor_source": str(real_write_request_auditor_path),
        "audit_status": audit_status,
        "recommended_next_action": recommended_next_action,
        "github_repo": github.get("repo"),
        "github_branch": github.get("branch"),
        "deployment_platform": cf.get("deployment_platform"),
        "deployment_trigger": cf.get("deployment_trigger"),
        "real_write_executor_dry_run_allowed": real_write_executor_dry_run_allowed,
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
    json_path = REPORT_DIR / f"learning-v2-deployment-route-contract-auditor-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-deployment-route-contract-auditor-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Deployment Route Contract Auditor Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- audit_status: `{audit_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- github_repo: `{github.get('repo')}`")
    md.append(f"- github_branch: `{github.get('branch')}`")
    md.append(f"- deployment_platform: `{cf.get('deployment_platform')}`")
    md.append(f"- deployment_trigger: `{cf.get('deployment_trigger')}`")
    md.append(f"- real_write_executor_dry_run_allowed: `{str(real_write_executor_dry_run_allowed).lower()}`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- git_push: `false`")
    md.append(f"- cloudflare_deploy: `false`")
    md.append(f"- deploy: `false`")
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

    print("deployment_route_contract_auditor = ok")
    print("mode = dry_run")
    print("audit_status =", audit_status)
    print("recommended_next_action =", recommended_next_action)
    print("github_repo =", github.get("repo"))
    print("github_branch =", github.get("branch"))
    print("deployment_platform =", cf.get("deployment_platform"))
    print("deployment_trigger =", cf.get("deployment_trigger"))
    print("real_write_executor_dry_run_allowed =", str(real_write_executor_dry_run_allowed).lower())
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
