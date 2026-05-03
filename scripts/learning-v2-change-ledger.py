#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
SNAPSHOT_DIR = BASE / "snapshots"
POLICY = BASE / "deployment-policy.json"
STATE = BASE / "state.json"

SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def run(cmd):
    r = subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "cmd": " ".join(cmd),
        "returncode": r.returncode,
        "stdout": r.stdout.strip(),
        "stderr": r.stderr.strip(),
    }

def load_state():
    if not STATE.exists():
        return {}
    return json.loads(STATE.read_text(encoding="utf-8"))

def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def parse_status_line(line):
    if not line.strip():
        return None

    status = line[:2]
    path = line[3:].strip()

    # Rename format: old -> new
    if " -> " in path:
        old, new = path.split(" -> ", 1)
        path = new.strip()

    return {
        "raw": line,
        "status": status,
        "path": path,
    }

def category_for(path):
    if path.startswith("learning-v2/") or path.startswith("scripts/learning-v2-"):
        return "learning_v2_system"

    if path.startswith("public/") or path.startswith("components/"):
        return "website_source"

    if path.startswith(".github/"):
        return "github_workflow"

    if path in ["wrangler.toml", "wrangler.json", "wrangler.jsonc", "package.json", "package-lock.json"]:
        return "deployment_config"

    if path.startswith("worker/") or path.endswith("wrangler.toml"):
        return "cloudflare_worker_or_config"

    if path.startswith("projects/") or path in ["USER.md", "MEMORY.md", "SOUL.md", "AGENTS.md"]:
        return "workspace_docs"

    if path.startswith("sql/") or path.endswith(".sql"):
        return "database_schema"

    if path.startswith("artifacts/") or path.startswith("harness/") or path.startswith("blxst/"):
        return "generated_or_experimental"

    if path.endswith(".png") or path.endswith(".jpg") or path.endswith(".jpeg") or path.endswith(".webp"):
        return "media_or_verification_artifact"

    return "other"

def risk_for(item):
    status = item["status"]
    path = item["path"]
    category = item["category"]

    if status.strip().startswith("D"):
        return "high_delete"

    if category == "website_source":
        return "medium_website_source"

    if category in ["deployment_config", "cloudflare_worker_or_config", "github_workflow"]:
        return "high_deployment_related"

    if category == "learning_v2_system":
        return "low_system_build"

    if status.startswith("??"):
        return "medium_untracked"

    return "medium_review"

def expand_untracked_directory_item(item):
    """
    git status --short may show an entire untracked directory as one line, e.g.:
      ?? learning-v2/

    Important:
    Use `git ls-files --others --exclude-standard -- <path>` instead of Path.rglob().
    That respects .git/info/exclude and .gitignore, so runtime artifacts such as
    learning-v2/reports/, snapshots/, backups/, state.json, outcomes.jsonl are not counted.
    """
    path = item["path"]
    status = item["status"]

    if not status.startswith("??"):
        return [item]

    full = WORKSPACE / path
    if not full.exists() or not full.is_dir():
        return [item]

    r = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", path],
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    files = [x.strip() for x in r.stdout.splitlines() if x.strip()]

    expanded = []
    for rel in files:
        expanded.append({
            "raw": f"?? {rel}",
            "status": "??",
            "path": rel,
        })

    return expanded

def enrich_item(item):
    item["category"] = category_for(item["path"])
    item["risk"] = risk_for(item)
    return item

def build_policy(git_info):
    return {
        "generated_at": now_iso(),
        "mode": "observer_only",
        "repo": {
            "owner": "New2Everything",
            "name": "blastjunior-website",
            "branch": git_info["branch"]["stdout"],
            "upstream": git_info["upstream"]["stdout"],
            "deploy_trigger_assumption": "Cloudflare Pages likely deploys when GitHub branch receives a push",
        },
        "permissions_available_note": "OpenClaw may have API permissions, but this policy keeps commit/push/deploy disabled until explicitly enabled.",
        "commit_policy": {
            "allow_commit": False,
            "allow_push": False,
            "allow_deploy": False,
            "reason": "worktree is dirty and learning-v2 is in system_build_only mode",
        },
        "release_gate": {
            "require_change_ledger": True,
            "require_clean_or_approved_dirty_baseline": True,
            "require_human_named_release_intent": True,
            "require_pre_deploy_doctor_ok": True,
            "require_backup_for_source_changes": True,
            "require_post_deploy_observer": True,
        },
        "allowed_now": [
            "observer reports",
            "doctor reports",
            "deployment policy design",
            "change ledger snapshots",
            "learning-v2 system scripts",
        ],
        "blocked_now": [
            "git commit",
            "git push",
            "Cloudflare Pages deploy",
            "wrangler deploy",
            "Cloudflare API mutation",
            "new website source auto-apply",
        ],
    }

def main():
    git_info = {
        "branch": run(["git", "branch", "--show-current"]),
        "upstream": run(["bash", "-lc", "git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || true"]),
        "head": run(["git", "rev-parse", "HEAD"]),
        "last_commit": run(["git", "log", "-1", "--pretty=format:%h %ad %s", "--date=iso"]),
        "status_short": run(["git", "status", "--short"]),
        "diff_name_only": run(["git", "diff", "--name-only"]),
        "diff_stat": run(["git", "diff", "--stat"]),
        "untracked": run(["bash", "-lc", "git ls-files --others --exclude-standard"]),
    }

    raw_entries = []
    entries = []

    for line in git_info["status_short"]["stdout"].splitlines():
        item = parse_status_line(line)
        if not item:
            continue
        raw_entries.append(enrich_item(dict(item)))

        for expanded in expand_untracked_directory_item(item):
            entries.append(enrich_item(expanded))

    by_category = {}
    by_risk = {}

    for item in entries:
        by_category.setdefault(item["category"], []).append(item)
        by_risk.setdefault(item["risk"], []).append(item)

    policy = build_policy(git_info)
    POLICY.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ledger = {
        "generated_at": now_iso(),
        "mode": "change_ledger_observer_only",
        "source_changed": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "git": git_info,
        "dirty_file_count": len(entries),
        "raw_status_line_count": len(raw_entries),
        "raw_entries": raw_entries,
        "entries": entries,
        "by_category": by_category,
        "by_risk": by_risk,
        "deployment_policy_path": str(POLICY),
        "summary": {
            "learning_v2_system": len(by_category.get("learning_v2_system", [])),
            "website_source": len(by_category.get("website_source", [])),
            "deployment_related": (
                len(by_category.get("deployment_config", []))
                + len(by_category.get("cloudflare_worker_or_config", []))
                + len(by_category.get("github_workflow", []))
            ),
            "high_delete": len(by_risk.get("high_delete", [])),
            "high_deployment_related": len(by_risk.get("high_deployment_related", [])),
            "medium_website_source": len(by_risk.get("medium_website_source", [])),
            "medium_untracked": len(by_risk.get("medium_untracked", [])),
        },
        "recommended_next_step": (
            "Do not commit or push yet. Review dirty baseline, then create a controlled release plan "
            "that separates learning-v2 system changes from website source changes."
        ),
    }

    out_json = SNAPSHOT_DIR / f"learning-v2-change-ledger-{stamp()}.json"
    out_json.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out_md = SNAPSHOT_DIR / f"learning-v2-change-ledger-{stamp()}.md"
    lines = []
    lines.append("# Learning V2 Change Ledger")
    lines.append("")
    lines.append(f"- generated_at: `{ledger['generated_at']}`")
    lines.append("- mode: `observer_only`")
    lines.append("- source_changed: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append(f"- dirty_file_count: `{ledger['dirty_file_count']}`")
    lines.append(f"- raw_status_line_count: `{ledger['raw_status_line_count']}`")
    lines.append(f"- branch: `{git_info['branch']['stdout']}`")
    lines.append(f"- upstream: `{git_info['upstream']['stdout']}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    for k, v in ledger["summary"].items():
        lines.append(f"- {k}: `{v}`")
    lines.append("")
    lines.append("## Deployment policy")
    lines.append("")
    lines.append(f"- `{POLICY}`")
    lines.append("")
    lines.append("## Categories")
    lines.append("")
    for cat, items in sorted(by_category.items()):
        lines.append(f"### {cat} ({len(items)})")
        lines.append("")
        for item in items:
            lines.append(f"- `{item['status']}` `{item['path']}` risk=`{item['risk']}`")
        lines.append("")
    lines.append("## Recommended next step")
    lines.append("")
    lines.append(ledger["recommended_next_step"])
    lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")

    state = load_state()
    state["last_change_ledger"] = {
        "at": now_iso(),
        "snapshot_json": str(out_json),
        "snapshot_report": str(out_md),
        "deployment_policy_path": str(POLICY),
        "dirty_file_count": len(entries),
        "summary": ledger["summary"],
        "source_changed": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }
    state["deployment_policy_path"] = str(POLICY)
    state["next_action"] = "Review change ledger and build release policy. Do not commit/push/deploy yet."
    state["updated_at"] = now_iso()
    save_state(state)

    print("change_ledger_result = ok")
    print("source_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("deployment_policy =", POLICY)
    print("snapshot_json =", out_json)
    print("snapshot_report =", out_md)
    print("dirty_file_count =", len(entries))
    print("summary =", json.dumps(ledger["summary"], ensure_ascii=False))
    print("recommended_next_step =", ledger["recommended_next_step"])

if __name__ == "__main__":
    main()
