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

STATUS_ID = "learning-v2-compact-push-readiness-v0"

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

def git_headline():
    p = subprocess.run(
        ["git", "status", "-sb"],
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return (p.stdout.splitlines() or [""])[0].strip()

def main():
    compact = run(["python3", "scripts/learning-v2-compact-status.py"])
    approval = run(["python3", "scripts/learning-v2-push-approval-gate.py"])
    safety = run(["python3", "scripts/learning-v2-push-deploy-safety-gate.py"])

    compact_kv = parse_kv(compact["stdout"] + compact["stderr"])
    approval_kv = parse_kv(approval["stdout"] + approval["stderr"])
    safety_kv = parse_kv(safety["stdout"] + safety["stderr"])

    failures = []

    ahead_count = safety_kv.get("ahead_count") or approval_kv.get("ahead_count")
    push_should_block = safety_kv.get("push_should_block") or approval_kv.get("push_should_block")
    no_push_needed = ahead_count == "0" and push_should_block == "false"

    if compact["returncode"] != 0 or compact_kv.get("compact_status") != "ok":
        failures.append(f"compact_status_not_ok:rc={compact['returncode']},value={compact_kv.get('compact_status')}")

    if approval["returncode"] != 0 or approval_kv.get("push_approval_gate") != "ok":
        if no_push_needed:
            pass
        else:
            failures.append(f"push_approval_gate_not_ok:rc={approval['returncode']},value={approval_kv.get('push_approval_gate')}")

    if safety["returncode"] != 0 or safety_kv.get("push_deploy_safety_gate") != "ok":
        failures.append(f"push_deploy_safety_gate_not_ok:rc={safety['returncode']},value={safety_kv.get('push_deploy_safety_gate')}")

    deploy_value = safety_kv.get("deploy") or approval_kv.get("deploy") or compact_kv.get("deploy")
    if deploy_value != "false":
        failures.append(f"deploy_not_false:{deploy_value}")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "status_id": STATUS_ID,
        "result": result,
        "git": git_headline(),
        "compact_status": compact_kv.get("compact_status"),
        "fast_status": compact_kv.get("fast_status"),
        "system_integrity": compact_kv.get("system_integrity"),
        "agent_status": compact_kv.get("agent_status"),
        "push_approval_gate": approval_kv.get("push_approval_gate"),
        "push_deploy_safety_gate": safety_kv.get("push_deploy_safety_gate"),
        "ahead_count": ahead_count,
        "push_readiness_mode": "no_push_needed" if no_push_needed else "push_candidate",
        "push_has_website_impact": safety_kv.get("push_has_website_impact") or approval_kv.get("push_has_website_impact"),
        "push_should_block": push_should_block,
        "remote_contains_token": safety_kv.get("remote_contains_token") or approval_kv.get("remote_contains_token"),
        "deploy": deploy_value,
        "failures": failures,
        "policy": {
            "git_push": False,
            "deploy": False,
            "read_only": True,
        },
    }

    out_json = REPORT_DIR / f"learning-v2-compact-push-readiness-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-compact-push-readiness-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Compact Push Readiness",
        "",
        f"- result: `{result}`",
        f"- git: `{payload['git']}`",
        f"- compact_status: `{payload['compact_status']}`",
        f"- fast_status: `{payload['fast_status']}`",
        f"- system_integrity: `{payload['system_integrity']}`",
        f"- agent_status: `{payload['agent_status']}`",
        f"- push_approval_gate: `{payload['push_approval_gate']}`",
        f"- push_deploy_safety_gate: `{payload['push_deploy_safety_gate']}`",
        f"- ahead_count: `{payload['ahead_count']}`",
        f"- push_readiness_mode: `{payload['push_readiness_mode']}`",
        f"- push_has_website_impact: `{payload['push_has_website_impact']}`",
        f"- push_should_block: `{payload['push_should_block']}`",
        f"- remote_contains_token: `{payload['remote_contains_token']}`",
        f"- deploy: `{payload['deploy']}`",
        "",
        "## Failures",
    ]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("compact_push_readiness =", result)
    print("git =", payload["git"])
    print("compact_status =", payload["compact_status"])
    print("fast_status =", payload["fast_status"])
    print("system_integrity =", payload["system_integrity"])
    print("agent_status =", payload["agent_status"])
    print("push_approval_gate =", payload["push_approval_gate"])
    print("push_deploy_safety_gate =", payload["push_deploy_safety_gate"])
    print("ahead_count =", payload["ahead_count"])
    print("push_readiness_mode =", payload["push_readiness_mode"])
    print("push_has_website_impact =", payload["push_has_website_impact"])
    print("push_should_block =", payload["push_should_block"])
    print("remote_contains_token =", payload["remote_contains_token"])
    print("deploy =", payload["deploy"])
    print("failure_count =", len(failures))
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("git_push = false")
    print("deploy = false")

    if failures:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
