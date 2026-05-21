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

SCRIPT_ID = "learning-v2-deployment-route-contract-v0"

EXPECTED_REPO = "New2Everything/blastjunior-website"
EXPECTED_BRANCH = "main"
EXPECTED_DEPLOYMENT_PLATFORM = "cloudflare_pages"
EXPECTED_SOURCE_OF_TRUTH = "github_main_branch"

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

    real_write_request_auditor_path = latest_report("learning-v2-controlled-source-change-real-write-request-auditor-dry-run-*.json")
    real_write_request_path = latest_report("learning-v2-controlled-source-change-real-write-request-dry-run-*.json")

    if not real_write_request_auditor_path:
        raise SystemExit("no controlled source-change real-write request auditor report found")
    if not real_write_request_path:
        raise SystemExit("no controlled source-change real-write request report found")

    real_write_request_auditor = load_json(real_write_request_auditor_path, {})
    real_write_request = load_json(real_write_request_path, {})

    hard_blocks = []
    warnings = []

    if real_write_request_auditor.get("audit_status") != "controlled_source_change_real_write_request_ready_for_executor_dry_run":
        hard_blocks.append("real_write_request_auditor_not_ready_for_executor")
    if real_write_request_auditor.get("executor_dry_run_allowed") is not True:
        hard_blocks.append("executor_dry_run_not_allowed")
    if real_write_request_auditor.get("source_change_gate_allowed") is not False:
        hard_blocks.append("real_write_request_auditor_allows_gate_too_early")
    if real_write_request_auditor.get("hard_blocks"):
        hard_blocks.append("real_write_request_auditor_has_hard_blocks")

    if real_write_request.get("request_status") != "controlled_source_change_real_write_request_ready_for_audit":
        hard_blocks.append("real_write_request_not_ready")

    packet = real_write_request.get("request_packet") or {}
    candidate_files = packet.get("candidate_files") or []

    if not candidate_files:
        hard_blocks.append("missing_candidate_files")

    deployment_route_contract = {
        "contract_type": "deployment_route_contract",
        "contract_version": "v0",
        "website_source_of_truth": EXPECTED_SOURCE_OF_TRUTH,
        "github": {
            "repo": EXPECTED_REPO,
            "branch": EXPECTED_BRANCH,
            "push_target": "origin/main",
            "required_before_deploy": [
                "controlled_source_write",
                "post_write_validation",
                "git_diff_audit",
                "git_commit_gate",
                "git_push_gate",
            ],
        },
        "cloudflare": {
            "deployment_platform": EXPECTED_DEPLOYMENT_PLATFORM,
            "pages_project_expected": "blastjunior-website",
            "deployment_trigger": "github_main_branch_build",
            "api_allowed_uses": [
                "check_pages_deployment_status",
                "trigger_pages_build_if_needed",
                "rollback_pages_deployment_if_needed",
                "purge_cache_if_needed",
                "inspect_d1_r2_kv_worker_bindings",
            ],
            "api_forbidden_uses": [
                "direct_upload_site_source_to_production",
                "bypass_github_main_branch",
                "write_cloudflare_token_to_repo",
                "deploy_uncommitted_local_files",
                "mix_d1_r2_kv_worker_mutations_with_static_site_source_change",
            ],
        },
        "forbidden_routes": [
            "wrangler_pages_deploy_direct_from_local_source",
            "manual_production_file_upload",
            "cloudflare_api_direct_source_publish",
            "deploy_without_git_push_origin_main",
            "deploy_with_tokens_or_secrets_written_to_repo",
        ],
        "separate_gate_required_for": [
            "cloudflare_d1_schema_change",
            "cloudflare_r2_data_policy_change",
            "cloudflare_kv_session_or_presence_change",
            "cloudflare_worker_route_or_binding_change",
            "environment_secret_change",
        ],
        "must_remain_false_in_this_step": {
            "business_source_written": False,
            "website_source_written": False,
            "git_commit": False,
            "git_push": False,
            "cloudflare_deploy": False,
            "deploy": False,
        },
        "candidate_files": candidate_files,
    }

    if hard_blocks:
        contract_status = "blocked"
        recommended_next_action = "fix_deployment_route_contract_inputs"
        contract_audit_allowed = False
    else:
        contract_status = "deployment_route_contract_ready_for_audit"
        recommended_next_action = "run_deployment_route_contract_auditor_dry_run"
        contract_audit_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "controlled_source_change_real_write_request_auditor_source": str(real_write_request_auditor_path),
        "controlled_source_change_real_write_request_source": str(real_write_request_path),
        "contract_status": contract_status,
        "recommended_next_action": recommended_next_action,
        "deployment_route_contract": deployment_route_contract,
        "candidate_file_count": len(candidate_files),
        "contract_audit_allowed": contract_audit_allowed,
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
    json_path = REPORT_DIR / f"learning-v2-deployment-route-contract-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-deployment-route-contract-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Deployment Route Contract Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- contract_status: `{contract_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- website_source_of_truth: `{EXPECTED_SOURCE_OF_TRUTH}`")
    md.append(f"- github_repo: `{EXPECTED_REPO}`")
    md.append(f"- github_branch: `{EXPECTED_BRANCH}`")
    md.append(f"- deployment_platform: `{EXPECTED_DEPLOYMENT_PLATFORM}`")
    md.append(f"- contract_audit_allowed: `{str(contract_audit_allowed).lower()}`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- git_push: `false`")
    md.append(f"- cloudflare_deploy: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Required Route")
    md.append("")
    md.append("- local controlled source change")
    md.append("- git commit")
    md.append("- git push origin main")
    md.append("- Cloudflare Pages builds from GitHub main")
    md.append("- Cloudflare API may check/trigger/rollback/purge, but may not bypass GitHub")
    md.append("")
    md.append("## Forbidden Routes")
    md.append("")
    for x in deployment_route_contract["forbidden_routes"]:
        md.append(f"- `{x}`")
    md.append("")
    md.append("## Separate Gate Required For")
    md.append("")
    for x in deployment_route_contract["separate_gate_required_for"]:
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

    print("deployment_route_contract = ok")
    print("mode = dry_run")
    print("contract_status =", contract_status)
    print("recommended_next_action =", recommended_next_action)
    print("github_repo =", EXPECTED_REPO)
    print("github_branch =", EXPECTED_BRANCH)
    print("deployment_platform =", EXPECTED_DEPLOYMENT_PLATFORM)
    print("contract_audit_allowed =", str(contract_audit_allowed).lower())
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
