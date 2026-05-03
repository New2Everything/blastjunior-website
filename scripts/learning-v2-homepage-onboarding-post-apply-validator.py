#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

VALIDATOR_ID = "learning-v2-homepage-onboarding-post-apply-validator-v0"
TARGET_FILE = "public/index.html"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def latest_report(pattern):
    reports = sorted(REPORT_DIR.glob(pattern))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def run(cmd):
    p = subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "cmd": cmd,
        "rc": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
    }

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    apply_path, apply_report = latest_report("homepage-onboarding-source-change-apply-apply-*.json")
    latest_probe_path, latest_probe = latest_report("community-onboarding-experience-probe-*.json")
    latest_resolver_path, latest_resolver = latest_report("community-onboarding-probe-resolver-*.json")
    latest_integrity_path, latest_integrity = latest_report("system-integrity-*.json")

    git_diff_name = run(["git", "diff", "--name-only"])
    git_diff_target = run(["git", "diff", "--", TARGET_FILE])

    changed_files = [
        x.strip()
        for x in git_diff_name["stdout"].splitlines()
        if x.strip()
    ]

    target_text = (WORKSPACE / TARGET_FILE).read_text(encoding="utf-8", errors="ignore")

    failures = []
    warnings = []

    if not apply_path:
        failures.append("missing_apply_report")

    if apply_report.get("result") != "ok":
        failures.append(f"apply_report_not_ok:{apply_report.get('result')}")

    if apply_report.get("source_written") is not True:
        failures.append("apply_report_source_written_not_true")

    if apply_report.get("target_file") != TARGET_FILE:
        failures.append(f"unexpected_apply_target:{apply_report.get('target_file')}")

    if not apply_report.get("backup_path"):
        failures.append("missing_backup_path")

    backup_path = apply_report.get("backup_path")
    if backup_path and not Path(backup_path).exists():
        failures.append(f"backup_path_not_found:{backup_path}")

    if "home-onboarding" not in target_text:
        failures.append("target_missing_home_onboarding")

    if "home-onboarding-title" not in target_text:
        failures.append("target_missing_home_onboarding_title")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_closed:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if policy.get("source_changes_allowed") is not False:
        failures.append(f"policy_source_changes_allowed_not_false:{policy.get('source_changes_allowed')}")

    if policy.get("git_commit_allowed") is not False:
        failures.append(f"policy_git_commit_allowed_not_false:{policy.get('git_commit_allowed')}")

    if policy.get("deploy_allowed") is not False:
        failures.append(f"policy_deploy_allowed_not_false:{policy.get('deploy_allowed')}")

    if TARGET_FILE not in changed_files:
        failures.append("git_diff_missing_target_file")

    unexpected_files = [f for f in changed_files if f != TARGET_FILE]
    if unexpected_files:
        warnings.append(f"unexpected_git_diff_files:{unexpected_files}")

    probe_ok = latest_probe.get("result") == "ok"
    resolver_ok = latest_resolver.get("result") == "ok"

    if not probe_ok:
        failures.append(f"post_apply_probe_not_ok:{latest_probe.get('result')}")

    if not resolver_ok:
        failures.append(f"post_apply_resolver_not_ok:{latest_resolver.get('result')}")

    integrity_expected_blocked = (
        latest_integrity.get("result") == "blocked"
        and latest_integrity.get("business_freeze_stable") is False
        and latest_integrity.get("drift_count") == 0
    )

    if not integrity_expected_blocked:
        warnings.append("latest_integrity_is_not_expected_business_freeze_block")

    payload = {
        "generated_at": now_iso(),
        "validator_id": VALIDATOR_ID,
        "result": "ok" if not failures else "blocked",
        "target_file": TARGET_FILE,
        "apply_report": str(apply_path) if apply_path else None,
        "post_apply_probe_report": str(latest_probe_path) if latest_probe_path else None,
        "post_apply_resolver_report": str(latest_resolver_path) if latest_resolver_path else None,
        "latest_integrity_report": str(latest_integrity_path) if latest_integrity_path else None,
        "changed_files": changed_files,
        "unexpected_files": unexpected_files,
        "git_diff_line_count": len(git_diff_target["stdout"].splitlines()),
        "backup_path": backup_path,
        "post_contains_home_onboarding": "home-onboarding" in target_text,
        "post_contains_home_onboarding_title": "home-onboarding-title" in target_text,
        "gate_closed": {
            "allow_source_changes": state.get("allow_source_changes"),
            "allow_git_commit": state.get("allow_git_commit"),
            "allow_deploy": state.get("allow_deploy"),
            "policy_source_changes_allowed": policy.get("source_changes_allowed"),
            "policy_git_commit_allowed": policy.get("git_commit_allowed"),
            "policy_deploy_allowed": policy.get("deploy_allowed"),
        },
        "probe_summary": {
            "finding_count": latest_probe.get("finding_count"),
            "review_or_missing_count": latest_probe.get("review_or_missing_count"),
            "high_or_medium_count": latest_probe.get("high_or_medium_count"),
        },
        "resolver_summary": {
            "decision": latest_resolver.get("decision"),
            "next_step": latest_resolver.get("next_step"),
            "review_or_missing_count": latest_resolver.get("review_or_missing_count"),
            "high_or_medium_count": latest_resolver.get("high_or_medium_count"),
        },
        "integrity_interpretation": {
            "latest_integrity_result": latest_integrity.get("result"),
            "business_freeze_stable": latest_integrity.get("business_freeze_stable"),
            "drift_count": latest_integrity.get("drift_count"),
            "expected_block_reason": "controlled_business_source_change_pending_ledger_acceptance",
            "system_scripts_drift_ok": latest_integrity.get("drift_count") == 0,
        },
        "policy": {
            "source_written_before_this_validator": True,
            "source_written_by_this_validator": False,
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "validator_only": True,
        },
        "warnings": warnings,
        "failures": failures,
    }

    out_json = REPORT_DIR / f"homepage-onboarding-post-apply-validator-{stamp()}.json"
    out_md = REPORT_DIR / f"homepage-onboarding-post-apply-validator-{stamp()}.md"
    ledger_md = SNAPSHOT_DIR / f"homepage-onboarding-controlled-change-ledger-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Homepage Onboarding Post-Apply Validator")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- validator_id: `{VALIDATOR_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- target_file: `{TARGET_FILE}`")
    lines.append(f"- changed_files: `{changed_files}`")
    lines.append(f"- backup_path: `{backup_path}`")
    lines.append(f"- post_contains_home_onboarding: `{str(payload['post_contains_home_onboarding']).lower()}`")
    lines.append(f"- post_contains_home_onboarding_title: `{str(payload['post_contains_home_onboarding_title']).lower()}`")
    lines.append(f"- integrity_interpretation: `controlled business source change pending ledger acceptance`")
    lines.append("- source_written_by_this_validator: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Probe summary")
    lines.append("")
    for k, v in payload["probe_summary"].items():
        lines.append(f"- {k}: `{v}`")
    lines.append("")
    lines.append("## Resolver summary")
    lines.append("")
    for k, v in payload["resolver_summary"].items():
        lines.append(f"- {k}: `{v}`")
    lines.append("")
    lines.append("## Integrity interpretation")
    lines.append("")
    for k, v in payload["integrity_interpretation"].items():
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

    text = "\n".join(lines)
    out_md.write_text(text, encoding="utf-8")
    ledger_md.write_text(text, encoding="utf-8")

    print("homepage_onboarding_post_apply_validator =", payload["result"])
    print("validator_id =", VALIDATOR_ID)
    print("target_file =", TARGET_FILE)
    print("validator_json =", out_json)
    print("validator_md =", out_md)
    print("ledger_md =", ledger_md)
    print("changed_files =", changed_files)
    print("unexpected_files =", unexpected_files)
    print("backup_path =", backup_path)
    print("post_contains_home_onboarding =", str(payload["post_contains_home_onboarding"]).lower())
    print("post_contains_home_onboarding_title =", str(payload["post_contains_home_onboarding_title"]).lower())
    print("gate_allow_source_changes =", state.get("allow_source_changes"))
    print("gate_allow_git_commit =", state.get("allow_git_commit"))
    print("gate_allow_deploy =", state.get("allow_deploy"))
    print("probe_review_or_missing_count =", latest_probe.get("review_or_missing_count"))
    print("probe_high_or_medium_count =", latest_probe.get("high_or_medium_count"))
    print("resolver_decision =", latest_resolver.get("decision"))
    print("latest_integrity_result =", latest_integrity.get("result"))
    print("latest_integrity_business_freeze_stable =", latest_integrity.get("business_freeze_stable"))
    print("latest_integrity_drift_count =", latest_integrity.get("drift_count"))
    print("source_written_by_this_validator = false")
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
