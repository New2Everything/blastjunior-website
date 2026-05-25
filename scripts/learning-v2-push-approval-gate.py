#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "push-approval-state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

GATE_ID = "learning-v2-push-approval-gate-v0"
EXPECTED_MIN_AHEAD_COMMITS = 1

REQUIRED_TRUE_FLAGS = [
    "public_changes_approved",
    "cloudflare_deploy_behavior_decided",
    "remaining_dirty_reviewed",
    "push_approved",
]

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

def load_latest(pattern):
    files = sorted(REPORT_DIR.glob(pattern))
    if not files:
        return None, {}
    p = files[-1]
    try:
        return p, json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return p, {}

def main():
    failures = []
    warnings = []

    if not STATE.exists():
        failures.append("push_approval_state_missing")
        state = {}
    else:
        state = json.loads(STATE.read_text(encoding="utf-8"))

    missing_true_flags = []

    token_resolved = state.get("token_revoked_or_rotated") is True
    token_risk_accepted = (
        state.get("token_risk_accepted") is True
        and state.get("token_handling_policy") == "accepted_risk_deferred_rotation"
    )

    if not (token_resolved or token_risk_accepted):
        missing_true_flags.append("token_revoked_or_rotated_or_token_risk_accepted")
        failures.append("token_blocker_not_resolved_or_accepted")

    for key in REQUIRED_TRUE_FLAGS:
        if state.get(key) is not True:
            missing_true_flags.append(key)

    deploy_ok = (
        state.get("deploy_approved") is True
        or state.get("deploy_intentionally_blocked") is True
    )
    if not deploy_ok:
        failures.append("deploy_not_approved_or_intentionally_blocked")

    for key in missing_true_flags:
        failures.append(f"approval_flag_not_true:{key}")

    rc_ahead, ahead_out, ahead_err = run(["git", "rev-list", "--count", "origin/main..HEAD"])
    ahead_count = int(ahead_out or "0") if rc_ahead == 0 else None
    if ahead_count is None or ahead_count < EXPECTED_MIN_AHEAD_COMMITS:
        failures.append(f"ahead_count_below_minimum:{ahead_count}")

    rc_cached, cached_out, cached_err = run(["git", "diff", "--cached", "--name-status"])
    if cached_out.strip():
        failures.append("git_index_not_empty")

    rc_remote, remote_out, remote_err = run(["git", "remote", "-v"])
    remote_contains_token = ("@" in remote_out and "github.com" in remote_out and "https://" in remote_out)
    if remote_contains_token:
        failures.append("remote_url_contains_token")

    rc_release, release_out, release_err = run(["python3", "scripts/learning-v2-release-gate.py"])
    release_report_path, release_report = load_latest("release-gate-*.json")
    release_summary = release_report.get("summary") or {}

    if release_summary.get("ok_for_system_build") is not True:
        failures.append(f"release_ok_for_system_build_not_true:{release_summary.get('ok_for_system_build')}")
    if release_summary.get("business_source_dirty_count") != 0:
        failures.append(f"business_source_dirty_not_zero:{release_summary.get('business_source_dirty_count')}")
    if release_summary.get("business_freeze_stable") is not True:
        failures.append("business_freeze_not_stable")
    if release_summary.get("ok_for_deploy") is not False:
        warnings.append(f"release_ok_for_deploy_unexpected:{release_summary.get('ok_for_deploy')}")

    rc_integrity, integrity_out, integrity_err = run(["python3", "scripts/learning-v2-system-integrity.py"])
    integrity_report_path, integrity_report = load_latest("system-integrity-*.json")
    integrity_result = integrity_report.get("result")
    if integrity_result != "ok":
        failures.append(f"system_integrity_not_ok:{integrity_result}")

    rc_safety, safety_out, safety_err = run(["python3", "scripts/learning-v2-push-deploy-safety-gate.py"])
    safety_report_path, safety_report = load_latest("learning-v2-push-deploy-safety-gate-*.json")

    safety_result = safety_report.get("result")
    push_should_block = safety_report.get("push_should_block")
    push_has_website_impact = safety_report.get("push_has_website_impact")
    pre_push_blocks = safety_report.get("pre_push_blocks")

    if safety_result not in ("ok", "blocked"):
        warnings.append(f"push_deploy_safety_gate_unknown_result:{safety_result}")

    if safety_result == "blocked" or push_should_block is True:
        failures.append(f"push_deploy_safety_gate_blocks_push:result={safety_result},push_should_block={push_should_block}")

    if pre_push_blocks is not True:
        failures.append("pre_push_not_confirmed_blocking")

    approved = not failures
    result = "ok" if approved else "blocked"

    payload = {
        "generated_at": now_iso(),
        "gate_id": GATE_ID,
        "result": result,
        "approved": approved,
        "state": state,
        "required_true_flags": REQUIRED_TRUE_FLAGS,
        "missing_true_flags": missing_true_flags,
        "deploy_ok": deploy_ok,
        "ahead_count": ahead_count,
        "expected_min_ahead_commits": EXPECTED_MIN_AHEAD_COMMITS,
        "remote_contains_token": remote_contains_token,
        "release_gate_report": str(release_report_path) if release_report_path else None,
        "release_gate_summary": release_summary,
        "system_integrity_report": str(integrity_report_path) if integrity_report_path else None,
        "system_integrity_result": integrity_result,
        "push_deploy_safety_gate_report": str(safety_report_path) if safety_report_path else None,
        "push_deploy_safety_gate_result": safety_result,
        "push_has_website_impact": push_has_website_impact,
        "push_should_block": push_should_block,
        "pre_push_blocks": pre_push_blocks,
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "gate_only": True,
            "git_push": False,
            "deploy": False,
            "force_push": False
        },
        "recommended_next_step": (
            "push approval blocked; resolve human approval flags before any push"
            if result == "blocked"
            else "push approval gate ok, but push still requires explicit human command"
        )
    }

    out_json = REPORT_DIR / f"learning-v2-push-approval-gate-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-push-approval-gate-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Push Approval Gate",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- result: `{result}`",
        f"- approved: `{str(approved).lower()}`",
        f"- ahead_count: `{ahead_count}`",
        f"- remote_contains_token: `{str(remote_contains_token).lower()}`",
        f"- push_has_website_impact: `{str(push_has_website_impact).lower()}`",
        f"- push_should_block: `{str(push_should_block).lower()}`",
        f"- pre_push_blocks: `{str(pre_push_blocks).lower()}`",
        "- git_push: `false`",
        "- deploy: `false`",
        "",
        "## Missing approval flags",
    ]

    if missing_true_flags:
        for key in missing_true_flags:
            lines.append(f"- `{key}`")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Failures")
    if failures:
        for item in failures:
            lines.append(f"- {item}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Warnings")
    if warnings:
        for item in warnings:
            lines.append(f"- {item}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Recommended next step")
    lines.append(payload["recommended_next_step"])
    lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("push_approval_gate =", result)
    print("approved =", str(approved).lower())
    print("ahead_count =", ahead_count)
    print("remote_contains_token =", str(remote_contains_token).lower())
    print("push_has_website_impact =", str(push_has_website_impact).lower())
    print("push_should_block =", str(push_should_block).lower())
    print("pre_push_blocks =", str(pre_push_blocks).lower())
    print("git_push = false")
    print("deploy = false")
    print("recommended_next_step =", payload["recommended_next_step"])
    print("report_json =", out_json)
    print("report_md =", out_md)

    if missing_true_flags:
        print("missing_true_flags =", json.dumps(missing_true_flags, ensure_ascii=False))
    if warnings:
        print("warnings =", json.dumps(warnings, ensure_ascii=False))
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))

    if result == "blocked":
        raise SystemExit(2)

if __name__ == "__main__":
    main()
