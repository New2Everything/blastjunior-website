#!/usr/bin/env python3
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-controlled-source-change-cloudflare-pages-status-check-v0"

EXPECTED_REPO = "New2Everything/blastjunior-website"
EXPECTED_BRANCH = "main"
EXPECTED_PLATFORM = "cloudflare_pages"
EXPECTED_TRIGGER = "github_main_branch_build"
EXPECTED_SITE_HINTS = ["blastjunior-website", "blastjunior.com", "blastjunior-website.pages.dev"]

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

def run_git(args):
    p = subprocess.run(
        ["git"] + args,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "args": ["git"] + args,
        "returncode": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is dry-run only and never deploys.")
    args = ap.parse_args()

    git_push_gate_path = latest_report("learning-v2-controlled-source-change-git-push-gate-dry-run-*.json")
    git_commit_gate_path = latest_report("learning-v2-controlled-source-change-git-commit-gate-dry-run-*.json")
    git_diff_audit_path = latest_report("learning-v2-controlled-source-change-git-diff-audit-dry-run-*.json")
    post_validation_path = latest_report("learning-v2-controlled-source-change-post-write-validation-dry-run-*.json")
    route_auditor_path = latest_report("learning-v2-deployment-route-contract-auditor-dry-run-*.json")

    for label, path in [
        ("git push gate", git_push_gate_path),
        ("git commit gate", git_commit_gate_path),
        ("git diff audit", git_diff_audit_path),
        ("post-write validation", post_validation_path),
        ("deployment route contract auditor", route_auditor_path),
    ]:
        if not path:
            raise SystemExit(f"no {label} report found")

    git_push_gate = load_json(git_push_gate_path, {})
    git_commit_gate = load_json(git_commit_gate_path, {})
    git_diff_audit = load_json(git_diff_audit_path, {})
    post_validation = load_json(post_validation_path, {})
    route_auditor = load_json(route_auditor_path, {})

    hard_blocks = []
    warnings = []

    if git_push_gate.get("gate_status") != "controlled_source_change_git_push_gate_ready_for_cloudflare_pages_status_check_dry_run":
        hard_blocks.append("git_push_gate_not_ready_for_cloudflare_pages_status_check")
    if git_push_gate.get("cloudflare_pages_status_check_dry_run_allowed") is not True:
        hard_blocks.append("cloudflare_pages_status_check_dry_run_not_allowed")
    if git_push_gate.get("git_push_allowed") is not False:
        hard_blocks.append("git_push_gate_allows_push_too_early")
    if git_push_gate.get("cloudflare_deploy_allowed") is not False:
        hard_blocks.append("git_push_gate_allows_cloudflare_deploy_too_early")
    if git_push_gate.get("deploy_allowed") is not False:
        hard_blocks.append("git_push_gate_allows_deploy_too_early")
    if git_push_gate.get("actual_source_written") is not False:
        hard_blocks.append("git_push_gate_says_actual_source_written")
    if git_push_gate.get("hard_blocks"):
        hard_blocks.append("git_push_gate_report_has_hard_blocks")

    if git_commit_gate.get("gate_status") != "controlled_source_change_git_commit_gate_ready_for_git_push_gate_dry_run":
        hard_blocks.append("git_commit_gate_not_ready")
    if git_diff_audit.get("audit_status") != "controlled_source_change_git_diff_audit_ready_for_git_commit_gate_dry_run":
        hard_blocks.append("git_diff_audit_not_ready")
    if post_validation.get("validation_status") != "controlled_source_change_post_write_validation_ready_for_git_diff_audit_dry_run":
        hard_blocks.append("post_write_validation_not_ready")

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

    route = git_push_gate.get("deployment_route") or {}
    if route.get("github_repo") != EXPECTED_REPO:
        hard_blocks.append("git_push_gate_route_github_repo_mismatch")
    if route.get("github_branch") != EXPECTED_BRANCH:
        hard_blocks.append("git_push_gate_route_github_branch_mismatch")
    if route.get("deployment_platform") != EXPECTED_PLATFORM:
        hard_blocks.append("git_push_gate_route_platform_mismatch")
    if route.get("deployment_trigger") != EXPECTED_TRIGGER:
        hard_blocks.append("git_push_gate_route_trigger_mismatch")

    git_branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    git_status_branch = run_git(["status", "-sb"])
    git_log_head = run_git(["log", "-1", "--oneline", "--decorate"])
    git_remote = run_git(["remote", "-v"])

    for label, result in [
        ("git_branch", git_branch),
        ("git_status_branch", git_status_branch),
        ("git_log_head", git_log_head),
        ("git_remote", git_remote),
    ]:
        if result.get("returncode") != 0:
            hard_blocks.append(f"{label}_failed")

    branch_name = git_branch.get("stdout", "").strip()
    if branch_name != EXPECTED_BRANCH:
        hard_blocks.append(f"branch_mismatch:{branch_name}")

    remote_text = git_remote.get("stdout", "")
    if "github.com/New2Everything/blastjunior-website" not in remote_text:
        hard_blocks.append("github_remote_mismatch")

    candidate_files = git_push_gate.get("candidate_files") or []
    candidate_count = len(candidate_files)
    if not candidate_files:
        hard_blocks.append("missing_candidate_files")

    cloudflare_status_check = {
        "mode": "dry_run",
        "deployment_platform": EXPECTED_PLATFORM,
        "deployment_trigger": EXPECTED_TRIGGER,
        "expected_github_repo": EXPECTED_REPO,
        "expected_github_branch": EXPECTED_BRANCH,
        "expected_site_hints": EXPECTED_SITE_HINTS,
        "cloudflare_api_called": False,
        "cloudflare_deploy_triggered": False,
        "pages_project_changed": False,
        "status_check_semantics": "verify route contract only; do not trigger deployment",
    }

    if hard_blocks:
        check_status = "blocked"
        recommended_next_action = "fix_cloudflare_pages_status_check_inputs"
        lifecycle_completion_dry_run_allowed = False
    else:
        check_status = "controlled_source_change_cloudflare_pages_status_check_ready_for_lifecycle_completion_dry_run"
        recommended_next_action = "run_controlled_source_change_lifecycle_completion_dry_run"
        lifecycle_completion_dry_run_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "git_push_gate_source": str(git_push_gate_path),
        "git_commit_gate_source": str(git_commit_gate_path),
        "git_diff_audit_source": str(git_diff_audit_path),
        "post_write_validation_source": str(post_validation_path),
        "deployment_route_contract_auditor_source": str(route_auditor_path),
        "check_status": check_status,
        "recommended_next_action": recommended_next_action,
        "candidate_file_count": candidate_count,
        "candidate_files": candidate_files,
        "cloudflare_status_check": cloudflare_status_check,
        "git_branch_stdout": git_branch.get("stdout", ""),
        "git_status_branch_stdout": git_status_branch.get("stdout", ""),
        "git_log_head_stdout": git_log_head.get("stdout", ""),
        "git_remote_stdout": git_remote.get("stdout", ""),
        "lifecycle_completion_dry_run_allowed": lifecycle_completion_dry_run_allowed,
        "git_commit_allowed": False,
        "git_push_allowed": False,
        "cloudflare_deploy_allowed": False,
        "actual_source_written": False,
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "deployment_route": {
            "github_repo": EXPECTED_REPO,
            "github_branch": EXPECTED_BRANCH,
            "deployment_platform": EXPECTED_PLATFORM,
            "deployment_trigger": EXPECTED_TRIGGER,
        },
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
    json_path = REPORT_DIR / f"learning-v2-controlled-source-change-cloudflare-pages-status-check-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-controlled-source-change-cloudflare-pages-status-check-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Cloudflare Pages Status Check Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- check_status: `{check_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- lifecycle_completion_dry_run_allowed: `{str(lifecycle_completion_dry_run_allowed).lower()}`")
    md.append(f"- cloudflare_api_called: `false`")
    md.append(f"- cloudflare_deploy_triggered: `false`")
    md.append(f"- git_commit_allowed: `false`")
    md.append(f"- git_push_allowed: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Deployment Route")
    md.append("")
    for k, v in payload["deployment_route"].items():
        md.append(f"- {k}: `{v}`")
    md.append("")
    md.append("## Site Hints")
    md.append("")
    for x in EXPECTED_SITE_HINTS:
        md.append(f"- `{x}`")
    md.append("")
    md.append("## Hard Blocks")
    md.append("")
    if hard_blocks:
        for x in hard_blocks:
            md.append(f"- {x}")
    else:
        md.append("- none")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("controlled_source_change_cloudflare_pages_status_check = ok")
    print("mode = dry_run")
    print("check_status =", check_status)
    print("recommended_next_action =", recommended_next_action)
    print("candidate_file_count =", candidate_count)
    print("lifecycle_completion_dry_run_allowed =", str(lifecycle_completion_dry_run_allowed).lower())
    print("github_repo =", EXPECTED_REPO)
    print("github_branch =", EXPECTED_BRANCH)
    print("deployment_platform =", EXPECTED_PLATFORM)
    print("deployment_trigger =", EXPECTED_TRIGGER)
    print("cloudflare_api_called = false")
    print("cloudflare_deploy_triggered = false")
    print("git_commit_allowed = false")
    print("git_push_allowed = false")
    print("cloudflare_deploy_allowed = false")
    print("deploy_allowed = false")
    print("actual_source_written = false")
    print("hard_blocks =", json.dumps(hard_blocks, ensure_ascii=False))
    print("warnings =", json.dumps(warnings, ensure_ascii=False))
    print("report_json =", json_path)
    print("report_md =", md_path)

if __name__ == "__main__":
    raise SystemExit(main())
