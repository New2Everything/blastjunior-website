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

STATUS_ID = "learning-v2-compact-status-v0"

IMPORTANT_KEYS = {
    "learning_v2_fast_status",
    "system_integrity",
    "learning_v2_agent_status",
    "stable_outcome",
    "confidence",
    "planning_status",
    "source_change_decision",
    "source_change_gate_opened",
    "accept_transition_simulator",
    "accept_transition_contract_auditor",
    "report_dependency_cycle_auditor",
    "report_dependency_cycle_detected_cycle_count",
    "steps_total",
    "steps_ok",
    "drift_count",
    "deploy",
    "failure_count",
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

def latest_integrity_summary():
    reports = sorted(REPORT_DIR.glob("system-integrity-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        return {}
    data = json.loads(reports[0].read_text(encoding="utf-8"))
    steps = data.get("steps", [])
    return {
        "integrity_report": str(reports[0]),
        "integrity_result": data.get("result"),
        "integrity_steps_total": len(steps),
        "report_cycle_step_ok": any(
            s.get("name") == "report_dependency_cycle_auditor" and s.get("ok") is True
            for s in steps
        ),
    }

def git_headline():
    p = subprocess.run(
        ["git", "status", "-sb"],
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    first = (p.stdout.splitlines() or [""])[0]
    return first.strip()

def main():
    fast = run(["python3", "scripts/learning-v2-fast-status.py"])
    integrity = run(["python3", "scripts/learning-v2-system-integrity.py"])
    agent = run(["python3", "scripts/learning-v2-agent-status.py"])

    fast_kv = parse_kv(fast["stdout"] + fast["stderr"])
    integrity_kv = parse_kv(integrity["stdout"] + integrity["stderr"])
    agent_kv = parse_kv(agent["stdout"] + agent["stderr"])
    latest_integrity = latest_integrity_summary()

    merged = {}
    merged.update(fast_kv)
    merged.update(integrity_kv)
    merged.update(agent_kv)

    result = "ok"
    failures = []

    checks = [
        ("fast_status", fast["returncode"], fast_kv.get("learning_v2_fast_status")),
        ("system_integrity", integrity["returncode"], integrity_kv.get("system_integrity")),
        ("agent_status", agent["returncode"], agent_kv.get("learning_v2_agent_status")),
    ]

    for name, rc, value in checks:
        if rc != 0 or value != "ok":
            failures.append(f"{name}_not_ok:rc={rc},value={value}")

    if merged.get("deploy") != "false":
        failures.append(f"deploy_not_false:{merged.get('deploy')}")

    if failures:
        result = "blocked"

    payload = {
        "generated_at": now_iso(),
        "status_id": STATUS_ID,
        "result": result,
        "git": git_headline(),
        "fast_status_returncode": fast["returncode"],
        "system_integrity_returncode": integrity["returncode"],
        "agent_status_returncode": agent["returncode"],
        "summary": {k: merged.get(k) for k in sorted(IMPORTANT_KEYS) if k in merged},
        "latest_integrity": latest_integrity,
        "failures": failures,
        "policy": {
            "website_files_changed": False,
            "git_add": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
    }

    out_json = REPORT_DIR / f"learning-v2-compact-status-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-compact-status-{stamp()}.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Compact Status",
        "",
        f"- result: `{result}`",
        f"- git: `{payload['git']}`",
        f"- fast_status: `{fast_kv.get('learning_v2_fast_status')}`",
        f"- system_integrity: `{integrity_kv.get('system_integrity')}`",
        f"- agent_status: `{agent_kv.get('learning_v2_agent_status')}`",
        f"- stable_outcome: `{merged.get('stable_outcome')}`",
        f"- source_change_gate_opened: `{merged.get('source_change_gate_opened')}`",
        f"- report_dependency_cycle_auditor: `{merged.get('report_dependency_cycle_auditor')}`",
        f"- report_dependency_cycle_detected_cycle_count: `{merged.get('report_dependency_cycle_detected_cycle_count')}`",
        f"- deploy: `{merged.get('deploy')}`",
        "",
        "## Failures",
    ]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("compact_status =", result)
    print("git =", payload["git"])
    print("fast_status =", fast_kv.get("learning_v2_fast_status"))
    print("system_integrity =", integrity_kv.get("system_integrity"))
    print("agent_status =", agent_kv.get("learning_v2_agent_status"))
    print("stable_outcome =", merged.get("stable_outcome"))
    print("source_change_gate_opened =", merged.get("source_change_gate_opened"))
    print("report_dependency_cycle_auditor =", merged.get("report_dependency_cycle_auditor"))
    print("report_dependency_cycle_detected_cycle_count =", merged.get("report_dependency_cycle_detected_cycle_count"))
    print("deploy =", merged.get("deploy"))
    print("failure_count =", len(failures))
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if failures:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
