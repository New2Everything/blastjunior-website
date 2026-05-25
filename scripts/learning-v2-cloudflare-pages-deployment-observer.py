#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
RUNTIME_DIR = BASE / "runtime"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-cloudflare-pages-deployment-observer-v0"

ALLOWED_ENVIRONMENTS = {"production", "preview", "unknown"}
ALLOWED_STATUSES = {"Success", "Failed", "Skipped", "Building", "Unknown"}
ALLOWED_POLICY_RESULTS = {
    "policy_ok",
    "policy_violation",
    "policy_unknown",
    "manual_record_only",
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")

def main():
    ap = argparse.ArgumentParser(description="Read-only Cloudflare Pages deployment observer. v0 supports manual-record only.")
    ap.add_argument("--mode", choices=["manual-record"], required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--branch", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--environment", choices=sorted(ALLOWED_ENVIRONMENTS), required=True)
    ap.add_argument("--status", choices=sorted(ALLOWED_STATUSES), required=True)
    ap.add_argument("--url", default="")
    ap.add_argument("--alias", default="")
    ap.add_argument("--dashboard-time", default="")
    ap.add_argument("--policy-result", choices=sorted(ALLOWED_POLICY_RESULTS), default="manual_record_only")
    ap.add_argument("--notes", default="")
    args = ap.parse_args()

    hard_blocks = []
    warnings = []

    if args.environment == "production" and args.status == "Success" and args.policy_result != "policy_ok":
        warnings.append("production_success_recorded_without_policy_ok")

    if args.environment == "production" and args.status == "Skipped" and args.policy_result == "policy_violation":
        warnings.append("production_skipped_but_policy_violation_set")

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "observer_status": "observer_ok_manual_record",
        "mode": args.mode,
        "source": "cloudflare_dashboard_manual_observation",
        "project": args.project,
        "branch": args.branch,
        "commit": args.commit,
        "environment": args.environment,
        "deployment_status": args.status,
        "deployment_url": args.url,
        "alias": args.alias,
        "dashboard_time": args.dashboard_time,
        "policy_result": args.policy_result,
        "notes": args.notes,
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "safety": {
            "read_only": True,
            "cloudflare_api_called": False,
            "wrangler_called": False,
            "oauth_triggered": False,
            "cloudflare_mutation": False,
            "direct_cloudflare_deploy": False,
            "git_push": False,
            "deploy": False,
            "secret_values_printed": False
        },
        "recommended_next_action": "review_manual_record_and_later_add_read_only_api_mode_if_needed"
    }

    ts = stamp()
    json_path = REPORT_DIR / f"learning-v2-cloudflare-pages-deployment-observer-manual-record-{ts}.json"
    md_path = RUNTIME_DIR / f"learning-v2-cloudflare-pages-deployment-observer-manual-record-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = f"""# Learning V2 Cloudflare Pages Deployment Observer Manual Record

## Result

- observer_status: `{payload["observer_status"]}`
- project: `{args.project}`
- branch: `{args.branch}`
- commit: `{args.commit}`
- environment: `{args.environment}`
- deployment_status: `{args.status}`
- deployment_url: `{args.url}`
- alias: `{args.alias}`
- dashboard_time: `{args.dashboard_time}`
- policy_result: `{args.policy_result}`

## Notes

{args.notes}

## Safety

- read_only: `true`
- cloudflare_api_called: `false`
- wrangler_called: `false`
- oauth_triggered: `false`
- cloudflare_mutation: `false`
- direct_cloudflare_deploy: `false`
- git_push: `false`
- deploy: `false`
- secret_values_printed: `false`

"""
    md_path.write_text(md, encoding="utf-8")

    print("cloudflare_pages_deployment_observer =", payload["observer_status"])
    print("mode =", args.mode)
    print("project =", args.project)
    print("branch =", args.branch)
    print("commit =", args.commit)
    print("environment =", args.environment)
    print("deployment_status =", args.status)
    print("policy_result =", args.policy_result)
    print("json_report =", json_path)
    print("md_report =", md_path)
    print("cloudflare_api_called = false")
    print("wrangler_called = false")
    print("oauth_triggered = false")
    print("direct_cloudflare_deploy = false")
    print("git_push = false")
    print("deploy = false")

    if hard_blocks:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
