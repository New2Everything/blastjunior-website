#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
REPORT_DIR = WORKSPACE / "learning-v2" / "reports"
SNAPSHOT_DIR = WORKSPACE / "learning-v2" / "snapshots"
SECRET_ENV = Path("/root/.openclaw/secrets/cloudflare-pages.env")

DEFAULT_LIVE_URL = "https://blastjunior.com/news"
DEFAULT_MARKERS = [
    "一场比赛，不只是比分",
    "news-story-path",
    "先看比赛瞬间",
]

def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def stamp():
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")

def run(cmd, check=False):
    p = subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed: {cmd}\nstdout={p.stdout}\nstderr={p.stderr}")
    return p

def load_env_file(path):
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

def cf_request(method, path, body=None):
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not token:
        raise RuntimeError("CLOUDFLARE_API_TOKEN missing")
    if not account:
        raise RuntimeError("CLOUDFLARE_ACCOUNT_ID missing")

    url = f"https://api.cloudflare.com/client/v4/accounts/{account}{path}"
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_project(project):
    return cf_request("GET", f"/pages/projects/{project}")

def create_deployment(project):
    return cf_request("POST", f"/pages/projects/{project}/deployments", body={})

def get_deployment(project, deployment_id):
    return cf_request("GET", f"/pages/projects/{project}/deployments/{deployment_id}")

def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "learning-v2-controlled-pages-deploy"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")

def marker_present(text, markers):
    return all(m in text for m in markers)

def project_summary(data):
    r = data.get("result") or {}
    cfg = ((r.get("source") or {}).get("config") or {})
    return {
        "success": data.get("success"),
        "name": r.get("name"),
        "id": r.get("id"),
        "production_branch": r.get("production_branch"),
        "domains": r.get("domains"),
        "source_type": (r.get("source") or {}).get("type"),
        "repo_owner": cfg.get("owner"),
        "repo_name": cfg.get("repo_name"),
        "source_production_branch": cfg.get("production_branch"),
        "production_deployments_enabled": cfg.get("production_deployments_enabled"),
        "deployments_enabled": cfg.get("deployments_enabled"),
        "preview_deployment_setting": cfg.get("preview_deployment_setting"),
        "errors": data.get("errors"),
    }

def write_reports(payload):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = stamp()
    jp = REPORT_DIR / f"learning-v2-controlled-pages-deploy-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-controlled-pages-deploy-{ts}.md"
    jp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Controlled Pages Deploy",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- mode: `{payload['mode']}`",
        f"- result: `{payload['result']}`",
        f"- deploy_post_called: `{str(payload['deploy_post_called']).lower()}`",
        f"- live_marker_present_after: `{str(payload.get('live_marker_present_after')).lower()}`",
        f"- production_deployments_enabled_after: `{payload.get('project_after', {}).get('production_deployments_enabled')}`",
        "",
        "## Summary",
        "",
        f"- project: `{payload.get('project')}`",
        f"- live_url: `{payload.get('live_url')}`",
        f"- deployment_id: `{payload.get('deployment_id')}`",
        f"- deployment_url: `{payload.get('deployment_url')}`",
        "",
        "## Safety",
        "",
        "- does not git add/commit/push",
        "- deploys only in real mode",
        "- confirms production auto-deploy remains false",
    ]
    mp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(jp), str(mp)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true", help="Actually POST one Cloudflare Pages deployment")
    ap.add_argument("--live-url", default=DEFAULT_LIVE_URL)
    ap.add_argument("--source-file", default="public/news.html")
    ap.add_argument("--project", default=os.environ.get("CLOUDFLARE_PAGES_PROJECT", "blastjunior-website"))
    ap.add_argument("--expected-project", default="blastjunior-website")
    ap.add_argument("--expected-branch", default="main")
    ap.add_argument("--poll-seconds", type=int, default=10)
    ap.add_argument("--poll-count", type=int, default=30)
    ap.add_argument("--marker", action="append", default=[])
    args = ap.parse_args()

    load_env_file(SECRET_ENV)
    markers = args.marker or DEFAULT_MARKERS
    mode = "real" if args.real else "dry_run"

    status = run(["git", "status", "--porcelain"])
    ahead = run(["git", "rev-list", "--left-right", "--count", "origin/main...HEAD"])
    head = run(["git", "rev-parse", "--short", "HEAD"])
    origin = run(["git", "rev-parse", "--short", "origin/main"])
    integrity = run(["python3", "scripts/learning-v2-system-integrity.py"])

    payload = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-controlled-pages-deploy-v0",
        "mode": mode,
        "project": args.project,
        "live_url": args.live_url,
        "markers": markers,
        "deploy_post_called": False,
        "git": {
            "status_porcelain": status.stdout.strip(),
            "ahead_behind": ahead.stdout.strip(),
            "head": head.stdout.strip(),
            "origin_main": origin.stdout.strip(),
        },
        "system_integrity_rc": integrity.returncode,
        "system_integrity_stdout_head": "\n".join(integrity.stdout.splitlines()[:20]),
    }

    failures = []
    if status.stdout.strip():
        failures.append("worktree_not_clean")
    if ahead.stdout.strip() != "0\t0":
        failures.append(f"head_not_aligned:{ahead.stdout.strip()}")
    if head.stdout.strip() != origin.stdout.strip():
        failures.append("head_origin_mismatch")
    if integrity.returncode != 0 or "system_integrity = ok" not in integrity.stdout:
        failures.append("system_integrity_not_ok")

    source_path = WORKSPACE / args.source_file
    source_text = source_path.read_text(encoding="utf-8", errors="replace")
    payload["source_marker_present"] = marker_present(source_text, markers)
    if not payload["source_marker_present"]:
        failures.append("source_marker_missing")

    live_before = fetch_text(args.live_url)
    payload["live_marker_present_before"] = marker_present(live_before, markers)

    project_before = project_summary(get_project(args.project))
    payload["project_before"] = project_before

    if project_before.get("success") is not True:
        failures.append("cloudflare_project_read_failed")
    if project_before.get("name") != args.expected_project:
        failures.append("unexpected_project")
    if project_before.get("production_branch") != args.expected_branch:
        failures.append("unexpected_production_branch")
    if project_before.get("deployments_enabled") is not True:
        failures.append("deployments_not_enabled")
    if project_before.get("production_deployments_enabled") is not False:
        failures.append("production_auto_deploy_not_false")

    payload["preflight_failures"] = failures

    deployment_id = None
    deployment_url = None
    deployment_status = None

    if failures:
        payload["result"] = "blocked"
    elif not args.real:
        payload["result"] = "dry_run_ok"
    else:
        deploy = create_deployment(args.project)
        payload["deploy_post_called"] = True
        payload["deploy_response_success"] = deploy.get("success")
        payload["deploy_response_errors"] = deploy.get("errors")
        r = deploy.get("result") or {}
        deployment_id = r.get("id")
        deployment_url = r.get("url")
        payload["deployment_id"] = deployment_id
        payload["deployment_url"] = deployment_url
        if deploy.get("success") is not True or not deployment_id:
            payload["result"] = "deploy_post_failed"
        else:
            for i in range(1, args.poll_count + 1):
                time.sleep(args.poll_seconds)
                st = get_deployment(args.project, deployment_id)
                rr = st.get("result") or {}
                stage = rr.get("latest_stage") or {}
                deployment_status = stage.get("status")
                payload.setdefault("polls", []).append({
                    "poll": i,
                    "success": st.get("success"),
                    "stage": stage.get("name"),
                    "status": deployment_status,
                    "url": rr.get("url"),
                })
                if deployment_status in ("success", "failure", "canceled"):
                    break
            payload["deployment_final_status"] = deployment_status
            live_after = fetch_text(args.live_url)
            payload["live_marker_present_after"] = marker_present(live_after, markers)
            project_after = project_summary(get_project(args.project))
            payload["project_after"] = project_after
            if deployment_status == "success" and payload["live_marker_present_after"] and project_after.get("production_deployments_enabled") is False:
                payload["result"] = "real_deploy_ok"
            else:
                payload["result"] = "real_deploy_incomplete"

    if "project_after" not in payload:
        payload["project_after"] = project_summary(get_project(args.project))
    if "live_marker_present_after" not in payload:
        payload["live_marker_present_after"] = payload["live_marker_present_before"]

    report_json, report_md = write_reports(payload)
    payload["report_json"] = report_json
    payload["report_md"] = report_md

    print("controlled_pages_deploy =", payload["result"])
    print("mode =", payload["mode"])
    print("deploy_post_called =", str(payload["deploy_post_called"]).lower())
    print("preflight_failures =", payload["preflight_failures"])
    print("live_marker_present_before =", str(payload["live_marker_present_before"]).lower())
    print("live_marker_present_after =", str(payload["live_marker_present_after"]).lower())
    print("production_deployments_enabled_before =", payload["project_before"].get("production_deployments_enabled"))
    print("production_deployments_enabled_after =", payload["project_after"].get("production_deployments_enabled"))
    print("deployment_id =", payload.get("deployment_id"))
    print("report_json =", report_json)
    print("report_md =", report_md)

    if payload["result"] in ("blocked", "deploy_post_failed", "real_deploy_incomplete"):
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
