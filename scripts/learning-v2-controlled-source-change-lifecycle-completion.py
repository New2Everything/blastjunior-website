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

SCRIPT_ID = "learning-v2-controlled-source-change-lifecycle-completion-v0"

EXPECTED_REPO = "New2Everything/blastjunior-website"
EXPECTED_BRANCH = "main"
EXPECTED_PLATFORM = "cloudflare_pages"
EXPECTED_TRIGGER = "github_main_branch_build"

CHAIN_REPORTS = [
    ("cloudflare pages status check", "learning-v2-controlled-source-change-cloudflare-pages-status-check-dry-run-*.json"),
    ("git push gate", "learning-v2-controlled-source-change-git-push-gate-dry-run-*.json"),
    ("git commit gate", "learning-v2-controlled-source-change-git-commit-gate-dry-run-*.json"),
    ("git diff audit", "learning-v2-controlled-source-change-git-diff-audit-dry-run-*.json"),
    ("post-write validation", "learning-v2-controlled-source-change-post-write-validation-dry-run-*.json"),
    ("actual write executor auditor", "learning-v2-controlled-source-change-actual-write-executor-auditor-dry-run-*.json"),
    ("actual write executor", "learning-v2-controlled-source-change-actual-write-executor-dry-run-*.json"),
    ("actual source-write gate opener auditor", "learning-v2-controlled-source-change-actual-source-write-gate-opener-auditor-dry-run-*.json"),
    ("actual source-write gate opener", "learning-v2-controlled-source-change-actual-source-write-gate-opener-dry-run-*.json"),
    ("actual source-write gate request auditor", "learning-v2-controlled-source-change-actual-source-write-gate-request-auditor-dry-run-*.json"),
    ("actual source-write gate request", "learning-v2-controlled-source-change-actual-source-write-gate-request-dry-run-*.json"),
    ("deployment route contract auditor", "learning-v2-deployment-route-contract-auditor-dry-run-*.json"),
]

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

def safe_false(obj, key):
    return obj.get(key) is False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is dry-run only and never changes source, git, or deploys.")
    args = ap.parse_args()

    loaded = {}
    sources = {}
    for label, pattern in CHAIN_REPORTS:
        path = latest_report(pattern)
        if not path:
            raise SystemExit(f"no {label} report found")
        loaded[label] = load_json(path, {})
        sources[label] = str(path)

    cf = loaded["cloudflare pages status check"]
    git_push_gate = loaded["git push gate"]
    git_commit_gate = loaded["git commit gate"]
    git_diff_audit = loaded["git diff audit"]
    post_validation = loaded["post-write validation"]
    actual_write_auditor = loaded["actual write executor auditor"]
    route_auditor = loaded["deployment route contract auditor"]

    hard_blocks = []
    warnings = []

    if cf.get("check_status") != "controlled_source_change_cloudflare_pages_status_check_ready_for_lifecycle_completion_dry_run":
        hard_blocks.append("cloudflare_pages_status_check_not_ready_for_lifecycle_completion")
    if cf.get("lifecycle_completion_dry_run_allowed") is not True:
        hard_blocks.append("lifecycle_completion_dry_run_not_allowed")
    if cf.get("cloudflare_deploy_allowed") is not False:
        hard_blocks.append("cloudflare_deploy_allowed_too_early")
    if cf.get("deploy_allowed") is not False:
        hard_blocks.append("deploy_allowed_too_early")
    if cf.get("actual_source_written") is not False:
        hard_blocks.append("cloudflare_status_check_says_actual_source_written")
    if cf.get("hard_blocks"):
        hard_blocks.append("cloudflare_status_check_has_hard_blocks")

    nested_cf = cf.get("cloudflare_status_check") or {}
    if nested_cf.get("cloudflare_api_called") is not False:
        hard_blocks.append("cloudflare_api_called_unexpectedly")
    if nested_cf.get("cloudflare_deploy_triggered") is not False:
        hard_blocks.append("cloudflare_deploy_triggered_unexpectedly")

    if git_push_gate.get("gate_status") != "controlled_source_change_git_push_gate_ready_for_cloudflare_pages_status_check_dry_run":
        hard_blocks.append("git_push_gate_not_ready")
    if git_push_gate.get("git_push_allowed") is not False:
        hard_blocks.append("git_push_gate_allows_push_too_early")
    if git_push_gate.get("cloudflare_deploy_allowed") is not False:
        hard_blocks.append("git_push_gate_allows_cloudflare_deploy_too_early")

    if git_commit_gate.get("gate_status") != "controlled_source_change_git_commit_gate_ready_for_git_push_gate_dry_run":
        hard_blocks.append("git_commit_gate_not_ready")
    if git_commit_gate.get("git_commit_allowed") is not False:
        hard_blocks.append("git_commit_gate_allows_commit_too_early")

    if git_diff_audit.get("audit_status") != "controlled_source_change_git_diff_audit_ready_for_git_commit_gate_dry_run":
        hard_blocks.append("git_diff_audit_not_ready")
    if git_diff_audit.get("changed_candidate_paths"):
        hard_blocks.append("git_diff_audit_has_changed_candidate_paths")
    if git_diff_audit.get("dirty_candidate_status"):
        hard_blocks.append("git_diff_audit_has_dirty_candidate_status")

    if post_validation.get("validation_status") != "controlled_source_change_post_write_validation_ready_for_git_diff_audit_dry_run":
        hard_blocks.append("post_write_validation_not_ready")
    if post_validation.get("actual_source_written") is not False:
        hard_blocks.append("post_validation_says_actual_source_written")

    if actual_write_auditor.get("audit_status") != "controlled_source_change_actual_write_executor_ready_for_post_write_validation_dry_run":
        hard_blocks.append("actual_write_executor_auditor_not_ready")
    if actual_write_auditor.get("actual_source_written") is not False:
        hard_blocks.append("actual_write_executor_auditor_says_actual_source_written")

    if route_auditor.get("audit_status") != "deployment_route_contract_ready_for_real_write_executor_dry_run":
        hard_blocks.append("deployment_route_contract_auditor_not_ready")
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

    candidate_files = cf.get("candidate_files") or git_push_gate.get("candidate_files") or []
    if not candidate_files:
        hard_blocks.append("missing_candidate_files")

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

    route = cf.get("deployment_route") or {}
    if route.get("github_repo") != EXPECTED_REPO:
        hard_blocks.append("completion_route_github_repo_mismatch")
    if route.get("github_branch") != EXPECTED_BRANCH:
        hard_blocks.append("completion_route_github_branch_mismatch")
    if route.get("deployment_platform") != EXPECTED_PLATFORM:
        hard_blocks.append("completion_route_platform_mismatch")
    if route.get("deployment_trigger") != EXPECTED_TRIGGER:
        hard_blocks.append("completion_route_trigger_mismatch")

    chain_safety = {
        "business_source_written": False,
        "website_source_written": False,
        "actual_source_written": False,
        "git_commit": False,
        "git_push": False,
        "cloudflare_api_called": False,
        "cloudflare_deploy_triggered": False,
        "cloudflare_deploy": False,
        "deploy": False,
    }

    if hard_blocks:
        completion_status = "blocked"
        recommended_next_action = "fix_controlled_source_change_lifecycle_completion_inputs"
        lifecycle_closed = False
    else:
        completion_status = "controlled_source_change_lifecycle_completion_dry_run_complete"
        recommended_next_action = "commit_controlled_source_change_lifecycle_completion_routing"
        lifecycle_closed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "sources": sources,
        "completion_status": completion_status,
        "recommended_next_action": recommended_next_action,
        "lifecycle_closed": lifecycle_closed,
        "candidate_file_count": len(candidate_files),
        "candidate_files": candidate_files,
        "github_repo": EXPECTED_REPO,
        "github_branch": EXPECTED_BRANCH,
        "deployment_platform": EXPECTED_PLATFORM,
        "deployment_trigger": EXPECTED_TRIGGER,
        "git_branch_stdout": git_branch.get("stdout", ""),
        "git_status_branch_stdout": git_status_branch.get("stdout", ""),
        "git_log_head_stdout": git_log_head.get("stdout", ""),
        "git_remote_stdout": git_remote.get("stdout", ""),
        "actual_source_write_allowed": False,
        "actual_source_written": False,
        "git_commit_allowed": False,
        "git_push_allowed": False,
        "cloudflare_deploy_allowed": False,
        "deploy_allowed": False,
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "safety": {
            "state_written": False,
            **chain_safety,
        },
    }

    ts = stamp()
    json_path = REPORT_DIR / f"learning-v2-controlled-source-change-lifecycle-completion-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-controlled-source-change-lifecycle-completion-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Controlled Source-Change Lifecycle Completion Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- completion_status: `{completion_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- lifecycle_closed: `{str(lifecycle_closed).lower()}`")
    md.append(f"- actual_source_written: `false`")
    md.append(f"- git_commit: `false`")
    md.append(f"- git_push: `false`")
    md.append(f"- cloudflare_api_called: `false`")
    md.append(f"- cloudflare_deploy_triggered: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Deployment Route")
    md.append("")
    md.append(f"- github_repo: `{EXPECTED_REPO}`")
    md.append(f"- github_branch: `{EXPECTED_BRANCH}`")
    md.append(f"- deployment_platform: `{EXPECTED_PLATFORM}`")
    md.append(f"- deployment_trigger: `{EXPECTED_TRIGGER}`")
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
    md.append("## Sources")
    md.append("")
    for label, src in sources.items():
        md.append(f"- {label}: `{src}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("controlled_source_change_lifecycle_completion = ok")
    print("mode = dry_run")
    print("completion_status =", completion_status)
    print("recommended_next_action =", recommended_next_action)
    print("lifecycle_closed =", str(lifecycle_closed).lower())
    print("candidate_file_count =", len(candidate_files))
    print("github_repo =", EXPECTED_REPO)
    print("github_branch =", EXPECTED_BRANCH)
    print("deployment_platform =", EXPECTED_PLATFORM)
    print("deployment_trigger =", EXPECTED_TRIGGER)
    print("actual_source_write_allowed = false")
    print("actual_source_written = false")
    print("git_commit_allowed = false")
    print("git_push_allowed = false")
    print("cloudflare_api_called = false")
    print("cloudflare_deploy_triggered = false")
    print("cloudflare_deploy_allowed = false")
    print("deploy_allowed = false")
    print("hard_blocks =", json.dumps(hard_blocks, ensure_ascii=False))
    print("warnings =", json.dumps(warnings, ensure_ascii=False))
    print("report_json =", json_path)
    print("report_md =", md_path)

if __name__ == "__main__":
    raise SystemExit(main())
