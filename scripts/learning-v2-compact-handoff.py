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

HANDOFF_ID = "learning-v2-compact-handoff-v0"

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
    )
    return {
        "cmd": cmd,
        "returncode": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
    }

def parse_kv(text):
    out = {}
    for line in text.splitlines():
        if " = " not in line:
            continue
        k, v = line.split(" = ", 1)
        out[k.strip()] = v.strip()
    return out

def git_one_line(args):
    p = subprocess.run(
        args,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return (p.stdout.splitlines() or [""])[0].strip()

def latest_commit():
    return git_one_line(["git", "--no-pager", "log", "-1", "--oneline", "--decorate"])

def git_status_headline():
    return git_one_line(["git", "status", "-sb"])

def main():
    compact = run(["python3", "scripts/learning-v2-compact-status.py"])
    push = run(["python3", "scripts/learning-v2-compact-push-readiness.py"])

    compact_kv = parse_kv(compact["stdout"] + compact["stderr"])
    push_kv = parse_kv(push["stdout"] + push["stderr"])

    failures = []

    if compact["returncode"] != 0 or compact_kv.get("compact_status") != "ok":
        failures.append(f"compact_status_not_ok:rc={compact['returncode']},value={compact_kv.get('compact_status')}")

    if push["returncode"] != 0 or push_kv.get("compact_push_readiness") != "ok":
        failures.append(f"compact_push_readiness_not_ok:rc={push['returncode']},value={push_kv.get('compact_push_readiness')}")

    deploy_value = push_kv.get("deploy") or compact_kv.get("deploy")
    if deploy_value != "false":
        failures.append(f"deploy_not_false:{deploy_value}")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "handoff_id": HANDOFF_ID,
        "result": result,
        "latest_commit": latest_commit(),
        "git": git_status_headline(),
        "compact_status": compact_kv.get("compact_status"),
        "fast_status": compact_kv.get("fast_status"),
        "system_integrity": compact_kv.get("system_integrity"),
        "agent_status": compact_kv.get("agent_status"),
        "stable_outcome": compact_kv.get("stable_outcome"),
        "source_change_gate_opened": compact_kv.get("source_change_gate_opened"),
        "report_dependency_cycle_auditor": compact_kv.get("report_dependency_cycle_auditor"),
        "report_dependency_cycle_detected_cycle_count": compact_kv.get("report_dependency_cycle_detected_cycle_count"),
        "compact_push_readiness": push_kv.get("compact_push_readiness"),
        "ahead_count": push_kv.get("ahead_count"),
        "push_readiness_mode": push_kv.get("push_readiness_mode"),
        "push_has_website_impact": push_kv.get("push_has_website_impact"),
        "push_should_block": push_kv.get("push_should_block"),
        "remote_contains_token": push_kv.get("remote_contains_token"),
        "deploy": deploy_value,
        "failures": failures,
        "policy": {
            "website_files_changed": False,
            "source_change_gate_opened": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
        },
    }

    out_json = REPORT_DIR / f"learning-v2-compact-handoff-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-compact-handoff-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Compact Handoff",
        "",
        "## Result",
        "",
        f"- compact_handoff: {result}",
        f"- generated_at: {payload['generated_at']}",
        f"- latest_commit: {payload['latest_commit']}",
        f"- git: {payload['git']}",
        "",
        "## Health",
        "",
        f"- compact_status: {payload['compact_status']}",
        f"- fast_status: {payload['fast_status']}",
        f"- system_integrity: {payload['system_integrity']}",
        f"- agent_status: {payload['agent_status']}",
        f"- stable_outcome: {payload['stable_outcome']}",
        f"- source_change_gate_opened: {payload['source_change_gate_opened']}",
        f"- report_dependency_cycle_auditor: {payload['report_dependency_cycle_auditor']}",
        f"- report_dependency_cycle_detected_cycle_count: {payload['report_dependency_cycle_detected_cycle_count']}",
        "",
        "## Push Readiness",
        "",
        f"- compact_push_readiness: {payload['compact_push_readiness']}",
        f"- ahead_count: {payload['ahead_count']}",
        f"- push_readiness_mode: {payload['push_readiness_mode']}",
        f"- push_has_website_impact: {payload['push_has_website_impact']}",
        f"- push_should_block: {payload['push_should_block']}",
        f"- remote_contains_token: {payload['remote_contains_token']}",
        f"- deploy: {payload['deploy']}",
        "",
        "## Boundary",
        "",
        "- Do not deploy.",
        "- Do not restore Cloudflare production auto-deploy.",
        "- Do not bulk commit unrelated dirty files.",
        "- Do not apply website changes while stable_outcome remains pending.",
        "- Do not treat planning readiness as source-change permission.",
        "- Do not reintroduce fast-status -> report -> fast-status dependency cycles.",
        "",
        "## Recommended Daily Commands",
        "",
        "Normal health:",
        "",
        "  python3 scripts/learning-v2-compact-status.py",
        "",
        "Push readiness:",
        "",
        "  python3 scripts/learning-v2-compact-push-readiness.py",
        "",
        "Compact handoff:",
        "",
        "  python3 scripts/learning-v2-compact-handoff.py",
        "",
        "## Failures",
    ]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("compact_handoff =", result)
    print("latest_commit =", payload["latest_commit"])
    print("git =", payload["git"])
    print("compact_status =", payload["compact_status"])
    print("compact_push_readiness =", payload["compact_push_readiness"])
    print("push_readiness_mode =", payload["push_readiness_mode"])
    print("ahead_count =", payload["ahead_count"])
    print("source_change_gate_opened =", payload["source_change_gate_opened"])
    print("deploy =", payload["deploy"])
    print("failure_count =", len(failures))
    print("handoff_json =", out_json)
    print("handoff_md =", out_md)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if failures:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
