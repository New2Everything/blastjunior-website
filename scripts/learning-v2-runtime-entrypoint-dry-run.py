#!/usr/bin/env python3
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
ORCHESTRATOR = WORKSPACE / "scripts" / "learning-v2-autonomous-e2e-dry-run-orchestrator.py"
ORIGIN_POLICY = WORKSPACE / "projects" / "BLXST-runtime-origin-policy.json"
REPORT_DIR = WORKSPACE / "learning-v2" / "reports"
SNAPSHOT_DIR = WORKSPACE / "learning-v2" / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def load_origin_policy():
    return json.loads(ORIGIN_POLICY.read_text(encoding="utf-8"))

def authorized_origins_from_policy():
    policy = load_origin_policy()
    return policy, set((policy.get("authorized_origins") or {}).keys())

def run_orchestrator(origin, text):
    p = subprocess.run(
        ["python3", str(ORCHESTRATOR), "--origin", origin, "--text", text],
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
        return None, p.stdout, p.stderr, p.returncode
    return Path(report), p.stdout, p.stderr, p.returncode

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", required=True)
    ap.add_argument("--text", required=True)
    args = ap.parse_args()

    warnings = []
    origin_policy, authorized_origins = authorized_origins_from_policy()
    origin_spec = (origin_policy.get("authorized_origins") or {}).get(args.origin) or {}
    if args.origin not in authorized_origins:
        warnings.append("origin_not_in_authorized_runtime_origins")
    if origin_spec.get("requires_prefix") == "/blxst" and not args.text.strip().startswith("/blxst"):
        warnings.append("user_direct_origin_without_blxst_prefix")

    report, stdout, stderr, rc = run_orchestrator(args.origin, args.text)

    if report:
        payload = load_json(report)
        runtime_status = payload.get("final_status")
        hard_failures = list(payload.get("hard_failures") or [])
        ready = bool(payload.get("ready_for_later_controlled_context"))
    else:
        payload = {}
        runtime_status = "runtime_orchestrator_failed"
        hard_failures = ["orchestrator_failed"]
        ready = False

    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-runtime-entrypoint-dry-run-v0",
        "mode": "dry_run",
        "input": {
            "origin": args.origin,
            "text": args.text
        },
        "authorized_origin_known": args.origin in authorized_origins,
        "origin_policy": {"path": str(ORIGIN_POLICY), "policy_driven": origin_policy.get("policy_driven")},
        "runtime_status": runtime_status,
        "ready_for_later_controlled_context": ready,
        "source_orchestrator_report": str(report) if report else None,
        "warnings": warnings,
        "hard_failures": hard_failures,
        "stdout_tail": "\n".join(stdout.splitlines()[-10:]) if stdout else "",
        "stderr_tail": "\n".join(stderr.splitlines()[-10:]) if stderr else "",
        "safety": {
            "dry_run_only": True,
            "runtime_entrypoint_only": True,
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
    jp = REPORT_DIR / f"learning-v2-runtime-entrypoint-dry-run-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-runtime-entrypoint-dry-run-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Runtime Entrypoint Dry-run\n\n"
        f"- runtime_status: `{runtime_status}`\n"
        f"- ready_for_later_controlled_context: `{str(ready).lower()}`\n"
        f"- hard_failure_count: `{len(hard_failures)}`\n"
        "- deploy: `false`\n",
        encoding="utf-8"
    )

    print("learning_v2_runtime_entrypoint = ok" if not hard_failures else "learning_v2_runtime_entrypoint = blocked")
    print("runtime_status =", runtime_status)
    print("ready_for_later_controlled_context =", str(ready).lower())
    print("hard_failure_count =", len(hard_failures))
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    raise SystemExit(0 if not hard_failures else 1)

if __name__ == "__main__":
    main()
