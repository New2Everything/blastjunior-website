#!/usr/bin/env python3
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
CONTEXT = WORKSPACE / "scripts" / "learning-v2-content-controlled-apply-context-gate.py"
EXECUTOR = WORKSPACE / "scripts" / "learning-v2-content-controlled-apply-executor.py"
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

def run(cmd):
    p = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    report = None
    for line in p.stdout.splitlines():
        if line.startswith("report_json ="):
            report = line.split("=", 1)[1].strip()
    return p.returncode, report, p.stdout, p.stderr

def main():
    failures = []

    rc, context_report, out, err = run([
        "python3", str(CONTEXT),
        "--simulate-ready",
        "--authorized-context", "controlled_content_apply_phase",
        "--apply-scope", "content_d1_r2_source"
    ])
    if rc != 0 or not context_report:
        failures.append("content_context_gate_failed")
        context_status = None
    else:
        context_payload = load_json(context_report)
        context_status = (context_payload.get("content_controlled_apply_context") or {}).get("content_controlled_apply_context_status")
        if context_status != "content_controlled_apply_context_ready_dry_run":
            failures.append("unexpected_context_status:" + str(context_status))

    rc2, exec_report, out2, err2 = run(["python3", str(EXECUTOR), "--input-report", context_report or "missing", "--allow-real-apply"])
    if rc2 != 0 or not exec_report:
        failures.append("content_executor_skeleton_failed")
        executor_status = None
    else:
        exec_payload = load_json(exec_report)
        executor_status = exec_payload.get("executor_status")
        if exec_payload.get("real_apply_executed") is not False:
            failures.append("executor_real_apply_executed_not_false")
        if exec_payload.get("content_written") is not False:
            failures.append("executor_content_written_not_false")
        if exec_payload.get("d1_written") is not False:
            failures.append("executor_d1_written_not_false")
        if exec_payload.get("r2_written") is not False:
            failures.append("executor_r2_written_not_false")
        if exec_payload.get("website_source_written") is not False:
            failures.append("executor_source_written_not_false")

    status = "ok" if not failures else "blocked"

    outp = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-content-controlled-apply-readiness-smoke-v0",
        "mode": "dry_run",
        "content_controlled_apply_readiness_smoke": status,
        "context_status": context_status,
        "executor_status": executor_status,
        "hard_failures": failures,
        "future_content_apply_pipeline_guarded": status == "ok",
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
    jp = REPORT_DIR / f"learning-v2-content-controlled-apply-readiness-smoke-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-content-controlled-apply-readiness-smoke-{ts}.md"
    jp.write_text(json.dumps(outp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Content Controlled Apply Readiness Smoke\n\n"
        f"- content_controlled_apply_readiness_smoke: `{status}`\n"
        f"- context_status: `{context_status}`\n"
        f"- executor_status: `{executor_status}`\n"
        "- real_apply_allowed_now: `false`\n"
        "- deploy: `false`\n",
        encoding="utf-8"
    )

    print("content_controlled_apply_readiness_smoke =", status)
    print("context_status =", context_status)
    print("executor_status =", executor_status)
    print("hard_failure_count =", len(failures))
    print("real_apply_allowed_now = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    raise SystemExit(0 if status == "ok" else 1)

if __name__ == "__main__":
    main()
