#!/usr/bin/env python3
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
APPLY_GATE = WORKSPACE / "scripts" / "learning-v2-registry-update-explicit-apply-gate.py"
ROLLBACK = WORKSPACE / "scripts" / "learning-v2-registry-update-rollback-rehearsal.py"
REPORT_DIR = WORKSPACE / "learning-v2" / "reports"
SNAPSHOT_DIR = WORKSPACE / "learning-v2" / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCENARIOS = {
    "unknown_resource": {
        "gate": "explicit_apply_gate_ready",
        "rollback": "rollback_rehearsal_ready"
    },
    "no_auth": {
        "gate": "explicit_apply_gate_blocked",
        "rollback": "rollback_rehearsal_blocked"
    },
    "unexpected_status": {
        "gate": "explicit_apply_gate_blocked",
        "rollback": "rollback_rehearsal_blocked"
    }
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def run_cmd(cmd):
    p = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    report = None
    for line in p.stdout.splitlines():
        if line.startswith("report_json ="):
            report = line.split("=", 1)[1].strip()
    if p.returncode != 0 or not report:
        return None, p.stdout, p.stderr
    return Path(report), p.stdout, p.stderr

def run_scenario(name):
    failures = []

    gate_report, out, err = run_cmd(["python3", str(APPLY_GATE), "--simulate", name])
    if not gate_report:
        return {"scenario": name, "ok": False, "failures": ["apply_gate_failed"], "stdout": out, "stderr": err}
    gate_payload = load_json(gate_report)
    gate_status = (gate_payload.get("explicit_apply_gate") or {}).get("explicit_apply_gate_status")

    rollback_report, out2, err2 = run_cmd(["python3", str(ROLLBACK), "--simulate", name])
    if not rollback_report:
        return {"scenario": name, "ok": False, "failures": ["rollback_rehearsal_failed"], "stdout": out2, "stderr": err2}
    rollback_payload = load_json(rollback_report)
    rb_status = (rollback_payload.get("rollback_rehearsal") or {}).get("rollback_rehearsal_status")

    expected = SCENARIOS[name]
    if gate_status != expected["gate"]:
        failures.append("unexpected_gate_status:" + str(gate_status))
    if rb_status != expected["rollback"]:
        failures.append("unexpected_rollback_status:" + str(rb_status))

    for payload_name, payload in [("gate", gate_payload), ("rollback", rollback_payload)]:
        safety = payload.get("safety") or {}
        for k in ["registry_written","website_source_written","d1_written","r2_written","kv_written","worker_changed","cloudflare_mutation","git_commit","git_push","deploy"]:
            if safety.get(k) is not False:
                failures.append(f"{payload_name}:unsafe_flag:{k}:{safety.get(k)}")

    return {
        "scenario": name,
        "ok": not failures,
        "gate_report": str(gate_report),
        "rollback_report": str(rollback_report),
        "gate_status": gate_status,
        "rollback_status": rb_status,
        "failures": failures
    }

def main():
    results = [run_scenario(x) for x in SCENARIOS]
    hard = [f"{r['scenario']}:{f}" for r in results for f in r["failures"]]
    status = "ok" if not hard else "blocked"

    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-registry-chain-readiness-matrix-v0",
        "mode": "dry_run",
        "registry_chain_readiness": status,
        "scenario_results": results,
        "hard_failures": hard,
        "ready_for_later_controlled_apply_context": status == "ok",
        "real_apply_allowed_now": False,
        "safety": {
            "dry_run_only": True,
            "registry_written": False,
            "website_source_written": False,
            "d1_written": False,
            "r2_written": False,
            "kv_written": False,
            "worker_changed": False,
            "cloudflare_mutation": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False
        }
    }
    ts = stamp()
    jp = REPORT_DIR / f"learning-v2-registry-chain-readiness-matrix-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-registry-chain-readiness-matrix-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Registry Chain Readiness Matrix\n\n"
        f"- registry_chain_readiness: `{status}`\n"
        f"- hard_failure_count: `{len(hard)}`\n"
        f"- ready_for_later_controlled_apply_context: `{str(status == 'ok').lower()}`\n"
        "- real_apply_allowed_now: `false`\n"
        "- deploy: `false`\n",
        encoding="utf-8"
    )
    print("registry_chain_readiness_matrix =", status)
    print("scenario_count =", len(results))
    print("hard_failure_count =", len(hard))
    print("ready_for_later_controlled_apply_context =", str(status == "ok").lower())
    print("real_apply_allowed_now = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    raise SystemExit(0 if status == "ok" else 1)

if __name__ == "__main__":
    main()
