#!/usr/bin/env python3
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
APPLY = WORKSPACE / "scripts" / "learning-v2-registry-update-apply-rehearsal.py"
REPORT_DIR = WORKSPACE / "learning-v2" / "reports"
SNAPSHOT_DIR = WORKSPACE / "learning-v2" / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCENARIOS = {
    "unknown_resource": "registry_apply_rehearsal_ready",
    "no_auth": "registry_apply_rehearsal_blocked",
    "unexpected_status": "registry_apply_rehearsal_blocked"
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def run_apply(name):
    p = subprocess.run(
        ["python3", str(APPLY), "--simulate", name],
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    report = None
    for line in p.stdout.splitlines():
        if line.startswith("report_json ="):
            report = line.split("=", 1)[1].strip()
    if p.returncode != 0 or not report:
        return {"scenario": name, "ok": False, "status": None, "failures": ["apply_rehearsal_failed"]}
    payload = load_json(report)
    status = ((payload.get("registry_apply_rehearsal") or {}).get("apply_rehearsal_status"))
    safety = payload.get("safety") or {}
    failures = []
    if status != SCENARIOS[name]:
        failures.append("unexpected_status:" + str(status))
    for k in ["registry_written","website_source_written","d1_written","r2_written","kv_written","worker_changed","cloudflare_mutation","git_commit","git_push","deploy"]:
        if safety.get(k) is not False:
            failures.append("unsafe_flag:" + k + ":" + str(safety.get(k)))
    return {"scenario": name, "ok": not failures, "status": status, "report": report, "failures": failures}

def main():
    results = [run_apply(x) for x in SCENARIOS]
    hard = [f"{r['scenario']}:{f}" for r in results for f in r["failures"]]
    status = "ok" if not hard else "blocked"
    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-autonomous-chain-smoke-v0",
        "mode": "dry_run",
        "chain_smoke": status,
        "scenario_results": results,
        "hard_failures": hard,
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
    jp = REPORT_DIR / f"learning-v2-autonomous-chain-smoke-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-autonomous-chain-smoke-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text("# Learning V2 Autonomous Chain Smoke\n\nstatus: `%s`\n\nhard_failures: `%s`\n\ndeploy: `false`\n" % (status, len(hard)), encoding="utf-8")

    print("autonomous_chain_smoke =", status)
    print("scenario_count =", len(results))
    print("hard_failure_count =", len(hard))
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    raise SystemExit(0 if status == "ok" else 1)

if __name__ == "__main__":
    main()
