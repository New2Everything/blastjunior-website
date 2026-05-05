#!/usr/bin/env python3
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

GATE_ID = "learning-v2-push-deploy-safety-gate-v0"

EXPECTED_AHEAD_COMMITS = 4

WEBSITE_IMPACT_PREFIXES = (
    "public/",
    "components/",
    "worker/",
    "assets/",
    "functions/",
)

WEBSITE_IMPACT_EXACT = {
    "wrangler.toml",
    "package.json",
    "package-lock.json",
    "_headers",
    "_redirects",
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def run(cmd):
    p = subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def parse_name_status(out):
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        rows.append({
            "raw": line,
            "status": parts[0] if parts else "",
            "path": parts[-1] if parts else line.strip(),
        })
    return rows

def is_website_impact(path):
    return path in WEBSITE_IMPACT_EXACT or any(path.startswith(prefix) for prefix in WEBSITE_IMPACT_PREFIXES)

def load_latest(pattern):
    files = sorted(REPORT_DIR.glob(pattern))
    if not files:
        return None, {}
    p = files[-1]
    return p, json.loads(p.read_text(encoding="utf-8"))

def main():
    failures = []
    warnings = []

    rc_remote, remote_out, remote_err = run(["git", "remote", "-v"])
    remote_contains_token = ("@" in remote_out and "github.com" in remote_out and "https://" in remote_out)

    rc_status, status_out, status_err = run(["git", "status", "-sb"])
    rc_ahead, ahead_out, ahead_err = run(["git", "rev-list", "--count", "origin/main..HEAD"])
    ahead_count = int(ahead_out.strip() or "0") if rc_ahead == 0 else None

    rc_log, log_out, log_err = run(["git", "--no-pager", "log", "--oneline", "--decorate", "origin/main..HEAD"])
    ahead_commits = [line for line in log_out.splitlines() if line.strip()]

    rc_diff, diff_out, diff_err = run(["git", "--no-pager", "diff", "--name-status", "origin/main..HEAD"])
    committed_rows = parse_name_status(diff_out)
    website_impact_rows = [x for x in committed_rows if is_website_impact(x["path"])]

    rc_cached, cached_out, cached_err = run(["git", "diff", "--cached", "--name-status"])
    cached_rows = parse_name_status(cached_out)

    rc_release, release_out, release_err = run(["python3", "scripts/learning-v2-release-gate.py"])
    release_report_path, release_report = load_latest("release-gate-*.json")
    release_summary = release_report.get("summary") or {}

    rc_integrity, integrity_out, integrity_err = run(["python3", "scripts/learning-v2-system-integrity.py"])
    integrity_report_path, integrity_report = load_latest("system-integrity-*.json")
    integrity_result = integrity_report.get("result")

    pre_push = WORKSPACE / ".git" / "hooks" / "pre-push"
    pre_push_exists = pre_push.exists()
    pre_push_text = pre_push.read_text(encoding="utf-8", errors="ignore") if pre_push_exists else ""
    pre_push_blocks = (
        "git push blocked" in pre_push_text
        and "ok_for_deploy" in pre_push_text
        and "Cloudflare Pages" in pre_push_text
    )

    if remote_contains_token:
        failures.append("remote_url_contains_token")

    if ahead_count != EXPECTED_AHEAD_COMMITS:
        warnings.append(f"ahead_count_unexpected:{ahead_count}")

    if cached_rows:
        failures.append("git_index_not_empty")

    if release_summary.get("ok_for_deploy") is not False:
        failures.append(f"release_gate_deploy_not_false:{release_summary.get('ok_for_deploy')}")

    if release_summary.get("ok_for_commit") is not False:
        warnings.append(f"release_gate_commit_unexpectedly_true:{release_summary.get('ok_for_commit')}")

    if release_summary.get("business_source_dirty_count") != 0:
        failures.append(f"business_source_dirty_not_zero:{release_summary.get('business_source_dirty_count')}")

    if release_summary.get("business_freeze_stable") is not True:
        failures.append("business_freeze_not_stable")

    if integrity_result != "ok":
        failures.append(f"system_integrity_not_ok:{integrity_result}")

    if not pre_push_exists:
        failures.append("pre_push_missing")

    if not pre_push_blocks:
        failures.append("pre_push_not_confirmed_blocking")

    push_has_website_impact = bool(website_impact_rows)
    push_should_block = (
        push_has_website_impact
        and release_summary.get("ok_for_deploy") is False
    )

    result = "blocked" if push_should_block or failures else "ok"

    payload = {
        "generated_at": now_iso(),
        "gate_id": GATE_ID,
        "result": result,
        "mode": "push_deploy_safety_gate",
        "status_short_branch": status_out,
        "ahead_count": ahead_count,
        "expected_ahead_commits": EXPECTED_AHEAD_COMMITS,
        "ahead_commits": ahead_commits,
        "committed_rows": committed_rows,
        "website_impact_rows": website_impact_rows,
        "push_has_website_impact": push_has_website_impact,
        "push_should_block": push_should_block,
        "cached_rows": cached_rows,
        "remote_contains_token": remote_contains_token,
        "remote_output_sanitized": remote_out,
        "release_gate_report": str(release_report_path) if release_report_path else None,
        "release_gate_summary": release_summary,
        "system_integrity_report": str(integrity_report_path) if integrity_report_path else None,
        "system_integrity_result": integrity_result,
        "pre_push_exists": pre_push_exists,
        "pre_push_blocks": pre_push_blocks,
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "gate_only": True,
            "git_push": False,
            "deploy": False,
            "force_push": False,
        },
        "recommended_next_step": (
            "push blocked: committed public website paths may trigger deployment; review push/deploy policy first"
            if result == "blocked"
            else "push safety gate ok, but still require explicit human approval before push"
        ),
    }

    out_json = REPORT_DIR / f"learning-v2-push-deploy-safety-gate-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-push-deploy-safety-gate-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Push Deploy Safety Gate")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- ahead_count: `{ahead_count}`")
    lines.append(f"- push_has_website_impact: `{str(push_has_website_impact).lower()}`")
    lines.append(f"- push_should_block: `{str(push_should_block).lower()}`")
    lines.append(f"- remote_contains_token: `{str(remote_contains_token).lower()}`")
    lines.append(f"- pre_push_blocks: `{str(pre_push_blocks).lower()}`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Ahead commits")
    for line in ahead_commits:
        lines.append(f"- `{line}`")
    lines.append("")
    lines.append("## Website impact paths")
    if website_impact_rows:
        for item in website_impact_rows:
            lines.append(f"- `{item['raw']}`")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Failures")
    if failures:
        for f in failures:
            lines.append(f"- {f}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Warnings")
    if warnings:
        for w in warnings:
            lines.append(f"- {w}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Recommended next step")
    lines.append(payload["recommended_next_step"])
    lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("push_deploy_safety_gate =", result)
    print("ahead_count =", ahead_count)
    print("push_has_website_impact =", str(push_has_website_impact).lower())
    print("push_should_block =", str(push_should_block).lower())
    print("remote_contains_token =", str(remote_contains_token).lower())
    print("pre_push_blocks =", str(pre_push_blocks).lower())
    print("git_push = false")
    print("deploy = false")
    print("recommended_next_step =", payload["recommended_next_step"])
    print("report_json =", out_json)
    print("report_md =", out_md)

    if warnings:
        print("warnings =", json.dumps(warnings, ensure_ascii=False))
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))

    if result == "blocked":
        raise SystemExit(2)

if __name__ == "__main__":
    main()
