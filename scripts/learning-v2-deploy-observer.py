#!/usr/bin/env python3
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
SNAPSHOT_DIR = BASE / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def run(cmd, timeout=15):
    try:
        r = subprocess.run(
            cmd,
            cwd=str(WORKSPACE),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": " ".join(cmd),
            "returncode": r.returncode,
            "stdout": r.stdout.strip(),
            "stderr": r.stderr.strip(),
        }
    except Exception as e:
        return {
            "cmd": " ".join(cmd),
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
        }

def read_file(path, limit=12000):
    p = WORKSPACE / path
    if not p.exists() or not p.is_file():
        return None
    text = p.read_text(encoding="utf-8", errors="ignore")
    return text[:limit]

def list_files(path):
    p = WORKSPACE / path
    if not p.exists():
        return []
    return [str(x.relative_to(WORKSPACE)) for x in sorted(p.rglob("*")) if x.is_file()]

def detect_github_repo(remote_url):
    if not remote_url:
        return None

    # Supports:
    # git@github.com:owner/repo.git
    # https://github.com/owner/repo.git
    m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?", remote_url)
    if not m:
        return None

    return {
        "owner": m.group("owner"),
        "repo": m.group("repo"),
        "url_hint": f"https://github.com/{m.group('owner')}/{m.group('repo')}",
    }

def detect_cloudflare_config():
    files = [
        "wrangler.toml",
        "wrangler.json",
        "wrangler.jsonc",
        "package.json",
        ".github/workflows",
    ]

    result = {}
    for f in files:
        if f == ".github/workflows":
            result[f] = list_files(f)
        else:
            result[f] = read_file(f)

    return result

def detect_wrangler():
    checks = []

    checks.append(run(["bash", "-lc", "command -v wrangler || true"]))
    checks.append(run(["bash", "-lc", "wrangler --version 2>/dev/null || true"]))
    checks.append(run(["bash", "-lc", "npx --no-install wrangler --version 2>/dev/null || true"], timeout=20))

    return checks

def main():
    git = {
        "is_work_tree": run(["git", "rev-parse", "--is-inside-work-tree"]),
        "branch": run(["git", "branch", "--show-current"]),
        "head": run(["git", "rev-parse", "HEAD"]),
        "last_commit": run(["git", "log", "-1", "--pretty=format:%h %ad %s", "--date=iso"]),
        "remote_origin": run(["git", "remote", "get-url", "origin"]),
        "upstream": run(["bash", "-lc", "git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || true"]),
        "status_short": run(["git", "status", "--short"]),
        "diff_name_only": run(["git", "diff", "--name-only"]),
        "diff_stat": run(["git", "diff", "--stat"]),
        "untracked_files": run(["bash", "-lc", "git ls-files --others --exclude-standard | head -200"]),
    }

    remote_url = git["remote_origin"]["stdout"]
    github_repo = detect_github_repo(remote_url)

    workflows = list_files(".github/workflows")
    workflow_contents = {}
    for wf in workflows:
        workflow_contents[wf] = read_file(wf, limit=8000)

    cloudflare_config = detect_cloudflare_config()
    wrangler = detect_wrangler()

    local_changed_files = [
        x for x in git["status_short"]["stdout"].splitlines()
        if x.strip()
    ]

    deployment_risk = {
        "local_worktree_dirty": len(local_changed_files) > 0,
        "dirty_file_count": len(local_changed_files),
        "has_github_remote": github_repo is not None,
        "has_github_workflows": len(workflows) > 0,
        "has_wrangler_toml": cloudflare_config.get("wrangler.toml") is not None,
        "cloudflare_pages_note": (
            "If Cloudflare Pages is connected to GitHub, deployment is usually triggered by pushing to the configured branch. "
            "This observer does not push, commit, or deploy."
        ),
    }

    result = {
        "generated_at": now_iso(),
        "mode": "observer_only",
        "source_changed": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "github_repo": github_repo,
        "git": git,
        "workflows": workflows,
        "workflow_contents": workflow_contents,
        "cloudflare_config": cloudflare_config,
        "wrangler_checks": wrangler,
        "deployment_risk": deployment_risk,
        "recommended_next_step": (
            "Build a deployment-policy layer before enabling commit/push/deploy. "
            "For now, keep learning-v2 in system_build_only mode."
        ),
    }

    out_json = SNAPSHOT_DIR / f"learning-v2-deploy-observer-{stamp()}.json"
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out_md = SNAPSHOT_DIR / f"learning-v2-deploy-observer-{stamp()}.md"

    lines = []
    lines.append("# Learning V2 GitHub / Cloudflare Pages Observer")
    lines.append("")
    lines.append(f"- generated_at: `{result['generated_at']}`")
    lines.append("- mode: `observer_only`")
    lines.append("- source_changed: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")

    lines.append("## GitHub repository")
    lines.append("")
    if github_repo:
        lines.append(f"- owner: `{github_repo['owner']}`")
        lines.append(f"- repo: `{github_repo['repo']}`")
        lines.append(f"- url_hint: `{github_repo['url_hint']}`")
    else:
        lines.append("- not detected from origin remote")
    lines.append("")

    lines.append("## Git state")
    lines.append("")
    lines.append(f"- branch: `{git['branch']['stdout']}`")
    lines.append(f"- upstream: `{git['upstream']['stdout']}`")
    lines.append(f"- head: `{git['head']['stdout']}`")
    lines.append(f"- last_commit: `{git['last_commit']['stdout']}`")
    lines.append(f"- worktree_dirty: `{deployment_risk['local_worktree_dirty']}`")
    lines.append(f"- dirty_file_count: `{deployment_risk['dirty_file_count']}`")
    lines.append("")

    lines.append("### git status --short")
    lines.append("")
    lines.append("```")
    lines.append(git["status_short"]["stdout"] or "(empty)")
    lines.append("```")
    lines.append("")

    lines.append("### git diff --name-only")
    lines.append("")
    lines.append("```")
    lines.append(git["diff_name_only"]["stdout"] or "(empty)")
    lines.append("```")
    lines.append("")

    lines.append("## GitHub workflows")
    lines.append("")
    if workflows:
        for wf in workflows:
            lines.append(f"- `{wf}`")
    else:
        lines.append("- none detected")
    lines.append("")

    lines.append("## Cloudflare / Wrangler hints")
    lines.append("")
    lines.append(f"- wrangler.toml exists: `{cloudflare_config.get('wrangler.toml') is not None}`")
    lines.append(f"- package.json exists: `{cloudflare_config.get('package.json') is not None}`")
    lines.append("")

    lines.append("### Wrangler checks")
    lines.append("")
    for c in wrangler:
        lines.append(f"- `{c['cmd']}` → rc `{c['returncode']}`")
        if c["stdout"]:
            lines.append(f"  - stdout: `{c['stdout']}`")
        if c["stderr"]:
            lines.append(f"  - stderr: `{c['stderr']}`")
    lines.append("")

    lines.append("## Deployment risk")
    lines.append("")
    for k, v in deployment_risk.items():
        lines.append(f"- {k}: `{v}`")
    lines.append("")

    lines.append("## Recommended next step")
    lines.append("")
    lines.append(result["recommended_next_step"])
    lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("deploy_observer_result = ok")
    print("observer_mode = observer_only")
    print("source_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("snapshot_json =", out_json)
    print("snapshot_report =", out_md)
    print("github_repo =", github_repo)
    print("branch =", git["branch"]["stdout"])
    print("upstream =", git["upstream"]["stdout"])
    print("worktree_dirty =", deployment_risk["local_worktree_dirty"])
    print("dirty_file_count =", deployment_risk["dirty_file_count"])
    print("has_github_workflows =", deployment_risk["has_github_workflows"])
    print("has_wrangler_toml =", deployment_risk["has_wrangler_toml"])

if __name__ == "__main__":
    main()
