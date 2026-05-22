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

SCRIPT_ID = "learning-v2-controlled-source-change-git-diff-audit-v0"

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
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is dry-run only and never commits.")
    args = ap.parse_args()

    post_validation_path = latest_report("learning-v2-controlled-source-change-post-write-validation-dry-run-*.json")
    actual_write_executor_auditor_path = latest_report("learning-v2-controlled-source-change-actual-write-executor-auditor-dry-run-*.json")
    actual_write_executor_path = latest_report("learning-v2-controlled-source-change-actual-write-executor-dry-run-*.json")
    route_auditor_path = latest_report("learning-v2-deployment-route-contract-auditor-dry-run-*.json")

    for label, path in [
        ("post-write validation", post_validation_path),
        ("actual write executor auditor", actual_write_executor_auditor_path),
        ("actual write executor", actual_write_executor_path),
        ("deployment route contract auditor", route_auditor_path),
    ]:
        if not path:
            raise SystemExit(f"no {label} report found")

    post_validation = load_json(post_validation_path, {})
    actual_write_executor_auditor = load_json(actual_write_executor_auditor_path, {})
    actual_write_executor = load_json(actual_write_executor_path, {})
    route_auditor = load_json(route_auditor_path, {})

    hard_blocks = []
    warnings = []

    if post_validation.get("validation_status") != "controlled_source_change_post_write_validation_ready_for_git_diff_audit_dry_run":
        hard_blocks.append("post_write_validation_not_ready_for_git_diff_audit")
    if post_validation.get("git_diff_audit_dry_run_allowed") is not True:
        hard_blocks.append("git_diff_audit_dry_run_not_allowed")
    if post_validation.get("actual_source_written") is not False:
        hard_blocks.append("post_validation_says_actual_source_written")
    if post_validation.get("git_commit_allowed") is not False:
        hard_blocks.append("post_validation_git_commit_allowed_too_early")
    if post_validation.get("git_push_allowed") is not False:
        hard_blocks.append("post_validation_git_push_allowed_too_early")
    if post_validation.get("deploy_allowed") is not False:
        hard_blocks.append("post_validation_deploy_allowed_too_early")
    if post_validation.get("hard_blocks"):
        hard_blocks.append("post_validation_report_has_hard_blocks")

    if actual_write_executor_auditor.get("audit_status") != "controlled_source_change_actual_write_executor_ready_for_post_write_validation_dry_run":
        hard_blocks.append("actual_write_executor_auditor_not_ready")
    if actual_write_executor_auditor.get("actual_source_written") is not False:
        hard_blocks.append("actual_write_executor_auditor_says_source_written")

    if actual_write_executor.get("executor_status") != "controlled_source_change_actual_write_executor_dry_run_ready_for_audit":
        hard_blocks.append("actual_write_executor_not_ready")
    if actual_write_executor.get("actual_source_written") is not False:
        hard_blocks.append("actual_write_executor_says_source_written")

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

    validation_items = post_validation.get("validation_items") or []
    candidate_files = sorted(set(x.get("path") for x in validation_items if x.get("path")))

    if not candidate_files:
        hard_blocks.append("missing_candidate_files")

    audited_items = []
    for item in validation_items:
        rel = item.get("path")
        item_blocks = []
        item_warnings = []

        if not rel:
            item_blocks.append("missing_path")
        else:
            if not (WORKSPACE / rel).exists():
                item_blocks.append("source_missing")

        if item.get("source_exists") is not True:
            item_blocks.append("source_exists_not_true")
        if item.get("source_unchanged_since_dry_run") is not True:
            item_blocks.append("source_changed_since_dry_run")
        if item.get("actual_source_written") is not False:
            item_blocks.append("actual_source_written_not_false")
        if item.get("git_diff_audit_required_before_commit") is not True:
            item_blocks.append("git_diff_audit_required_before_commit_not_true")
        if item.get("github_main_push_required_before_cloudflare_pages_deploy") is not True:
            item_blocks.append("github_main_push_required_before_cloudflare_pages_deploy_not_true")
        if item.get("hard_blocks"):
            item_blocks.append("validation_item_has_hard_blocks")

        audited_items.append({
            "path": rel,
            "hard_blocks": item_blocks,
            "warnings": item_warnings,
        })

        hard_blocks.extend([f"{rel}:{x}" for x in item_blocks])
        warnings.extend([f"{rel}:{x}" for x in item_warnings])

    git_diff_name_only = {"stdout": "", "stderr": "", "returncode": 0}
    git_diff_stat = {"stdout": "", "stderr": "", "returncode": 0}
    git_status_candidates = {"stdout": "", "stderr": "", "returncode": 0}

    if candidate_files:
        git_diff_name_only = run_git(["diff", "--name-only", "--"] + candidate_files)
        git_diff_stat = run_git(["diff", "--stat", "--"] + candidate_files)
        git_status_candidates = run_git(["status", "--short", "--"] + candidate_files)

        if git_diff_name_only["returncode"] != 0:
            hard_blocks.append("git_diff_name_only_failed")
        if git_diff_stat["returncode"] != 0:
            hard_blocks.append("git_diff_stat_failed")
        if git_status_candidates["returncode"] != 0:
            hard_blocks.append("git_status_candidates_failed")

        changed_candidate_paths = [x for x in git_diff_name_only["stdout"].splitlines() if x.strip()]
        dirty_candidate_status = [x for x in git_status_candidates["stdout"].splitlines() if x.strip()]

        if changed_candidate_paths:
            hard_blocks.append("candidate_files_have_uncommitted_diff")
        if dirty_candidate_status:
            hard_blocks.append("candidate_files_dirty_in_git_status")
    else:
        changed_candidate_paths = []
        dirty_candidate_status = []

    if hard_blocks:
        audit_status = "blocked"
        recommended_next_action = "fix_git_diff_audit_inputs"
        git_commit_gate_dry_run_allowed = False
    else:
        audit_status = "controlled_source_change_git_diff_audit_ready_for_git_commit_gate_dry_run"
        recommended_next_action = "run_controlled_source_change_git_commit_gate_dry_run"
        git_commit_gate_dry_run_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "post_write_validation_source": str(post_validation_path),
        "actual_write_executor_auditor_source": str(actual_write_executor_auditor_path),
        "actual_write_executor_source": str(actual_write_executor_path),
        "deployment_route_contract_auditor_source": str(route_auditor_path),
        "audit_status": audit_status,
        "recommended_next_action": recommended_next_action,
        "candidate_file_count": len(candidate_files),
        "candidate_files": candidate_files,
        "audited_items": audited_items,
        "changed_candidate_paths": changed_candidate_paths,
        "dirty_candidate_status": dirty_candidate_status,
        "git_diff_name_only_stdout": git_diff_name_only.get("stdout", ""),
        "git_diff_stat_stdout": git_diff_stat.get("stdout", ""),
        "git_status_candidates_stdout": git_status_candidates.get("stdout", ""),
        "git_commit_gate_dry_run_allowed": git_commit_gate_dry_run_allowed,
        "git_commit_allowed": False,
        "git_push_allowed": False,
        "actual_source_write_allowed": False,
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
    json_path = REPORT_DIR / f"learning-v2-controlled-source-change-git-diff-audit-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-controlled-source-change-git-diff-audit-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Git Diff Audit Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- audit_status: `{audit_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- git_commit_gate_dry_run_allowed: `{str(git_commit_gate_dry_run_allowed).lower()}`")
    md.append(f"- git_commit_allowed: `false`")
    md.append(f"- git_push_allowed: `false`")
    md.append(f"- actual_source_written: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Candidate Files")
    md.append("")
    for x in candidate_files:
        md.append(f"- `{x}`")
    md.append("")
    md.append("## Git Diff")
    md.append("")
    if changed_candidate_paths:
        for x in changed_candidate_paths:
            md.append(f"- changed: `{x}`")
    else:
        md.append("- no candidate-file diff detected")
    md.append("")
    md.append("## Hard Blocks")
    md.append("")
    if hard_blocks:
        for x in hard_blocks:
            md.append(f"- {x}")
    else:
        md.append("- none")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("controlled_source_change_git_diff_audit = ok")
    print("mode = dry_run")
    print("audit_status =", audit_status)
    print("recommended_next_action =", recommended_next_action)
    print("candidate_file_count =", len(candidate_files))
    print("git_commit_gate_dry_run_allowed =", str(git_commit_gate_dry_run_allowed).lower())
    print("git_commit_allowed = false")
    print("git_push_allowed = false")
    print("actual_source_written = false")
    print("deploy_allowed = false")
    print("changed_candidate_paths =", json.dumps(changed_candidate_paths, ensure_ascii=False))
    print("dirty_candidate_status =", json.dumps(dirty_candidate_status, ensure_ascii=False))
    print("hard_blocks =", json.dumps(hard_blocks, ensure_ascii=False))
    print("warnings =", json.dumps(warnings, ensure_ascii=False))
    print("report_json =", json_path)
    print("report_md =", md_path)

if __name__ == "__main__":
    raise SystemExit(main())
