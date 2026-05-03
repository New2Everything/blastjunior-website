#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

READINESS_ID = "learning-v2-homepage-onboarding-source-change-gate-readiness-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def latest_dry_run():
    reports = sorted(REPORT_DIR.glob("homepage-onboarding-source-change-dry-run-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    dry_path, dry = latest_dry_run()

    failures = []
    warnings = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if integrity.get("drift_count") != 0:
        failures.append(f"drift_count_not_zero:{integrity.get('drift_count')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if state.get("allow_source_changes") is not False:
        warnings.append(f"allow_source_changes_already_not_false:{state.get('allow_source_changes')}")

    if not dry_path:
        failures.append("missing_homepage_onboarding_source_change_dry_run")

    if dry.get("result") != "ok":
        failures.append(f"dry_run_not_ok:{dry.get('result')}")

    if dry.get("target_file") != "public/index.html":
        failures.append(f"unexpected_target_file:{dry.get('target_file')}")

    if dry.get("changed_in_dry_run") is not True:
        failures.append(f"dry_run_not_changed:{dry.get('changed_in_dry_run')}")

    if dry.get("already_present") is True:
        failures.append("home_onboarding_block_already_present")

    if dry.get("diff_line_count", 0) <= 0:
        failures.append(f"empty_diff:{dry.get('diff_line_count')}")

    if dry.get("policy", {}).get("source_written") is not False:
        failures.append("dry_run_policy_claims_source_written")

    target = WORKSPACE / "public/index.html"
    if not target.exists():
        failures.append("target_missing:public/index.html")
    else:
        text = target.read_text(encoding="utf-8", errors="ignore")
        if "home-onboarding" in text or "home-onboarding-title" in text:
            failures.append("target_already_contains_home_onboarding_block")

    ready = not failures

    payload = {
        "generated_at": now_iso(),
        "readiness_id": READINESS_ID,
        "result": "ok" if ready else "blocked",
        "dry_run_report": str(dry_path) if dry_path else None,
        "ready_to_open_source_change_gate": ready,
        "recommended_gate": {
            "allow_source_changes": True,
            "allow_git_commit": False,
            "allow_deploy": False,
            "single_target_file": "public/index.html",
            "single_change_executor": "learning-v2-homepage-onboarding-source-change-apply.py",
            "must_backup_before_write": True,
            "must_run_post_apply_probe": True,
            "must_run_system_integrity": True
        },
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "readiness_only": True
        },
        "warnings": warnings,
        "failures": failures
    }

    out_json = REPORT_DIR / f"homepage-onboarding-source-change-gate-readiness-{stamp()}.json"
    out_md = REPORT_DIR / f"homepage-onboarding-source-change-gate-readiness-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Homepage Onboarding Source Change Gate Readiness")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- readiness_id: `{READINESS_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- dry_run_report: `{payload['dry_run_report']}`")
    lines.append(f"- ready_to_open_source_change_gate: `{str(ready).lower()}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Recommended gate")
    lines.append("")
    for k, v in payload["recommended_gate"].items():
        lines.append(f"- {k}: `{v}`")
    if warnings:
        lines.append("")
        lines.append("## Warnings")
        for w in warnings:
            lines.append(f"- {w}")
    if failures:
        lines.append("")
        lines.append("## Failures")
        for f in failures:
            lines.append(f"- {f}")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("homepage_onboarding_source_change_gate_readiness =", payload["result"])
    print("readiness_id =", READINESS_ID)
    print("dry_run_report =", dry_path)
    print("readiness_json =", out_json)
    print("readiness_md =", out_md)
    print("ready_to_open_source_change_gate =", str(ready).lower())
    print("single_target_file = public/index.html")
    print("allow_source_changes_recommended = true")
    print("allow_git_commit_recommended = false")
    print("allow_deploy_recommended = false")
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if warnings:
        print()
        print("warnings:")
        for w in warnings:
            print(" ", w)

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
