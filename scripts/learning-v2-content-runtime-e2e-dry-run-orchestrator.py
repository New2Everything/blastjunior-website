#!/usr/bin/env python3
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
APPLY = WORKSPACE / "scripts" / "learning-v2-content-apply-rehearsal-dry-run.py"
CONTEXT = WORKSPACE / "scripts" / "learning-v2-content-controlled-apply-context-gate.py"
EXECUTOR = WORKSPACE / "scripts" / "learning-v2-content-controlled-apply-executor.py"
POLICY = WORKSPACE / "projects" / "BLXST-content-runtime-e2e-policy.json"
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

def run_cmd(cmd):
    p = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    report = None
    for line in p.stdout.splitlines():
        if line.startswith("report_json ="):
            report = line.split("=", 1)[1].strip()
    return {
        "cmd": cmd,
        "returncode": p.returncode,
        "report_json": report,
        "stdout_tail": "\n".join(p.stdout.splitlines()[-12:]),
        "stderr_tail": "\n".join(p.stderr.splitlines()[-12:])
    }

def unsafe_flags(payload):
    safety = payload.get("safety") or {}
    bad = []
    for k in [
        "registry_written",
        "website_source_written",
        "d1_written",
        "r2_written",
        "kv_written",
        "worker_changed",
        "cloudflare_mutation",
        "git_commit",
        "git_push",
        "deploy"
    ]:
        if safety.get(k) is not False and safety.get(k) is not None:
            bad.append(k + ":" + str(safety.get(k)))
    return bad

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", required=True)
    ap.add_argument("--text", required=True)
    args = ap.parse_args()

    policy = load_json(POLICY)
    steps = []
    hard = []

    apply_step = run_cmd(["python3", str(APPLY), "--origin", args.origin, "--text", args.text])
    steps.append({"step": "content_apply_rehearsal", **apply_step})
    if apply_step["returncode"] != 0 or not apply_step["report_json"]:
        hard.append("content_apply_rehearsal_failed")
        return finish(policy, args, steps, hard, "content_runtime_e2e_blocked")

    apply_payload = load_json(apply_step["report_json"])
    plan = apply_payload.get("content_apply_rehearsal") or {}
    for bad in unsafe_flags(apply_payload):
        hard.append("content_apply_rehearsal:unsafe_flag:" + bad)

    if plan.get("apply_rehearsal_status") != "content_apply_rehearsal_ready":
        final_status = "content_runtime_e2e_safe_stop_before_apply"
        return finish(policy, args, steps, hard, final_status)

    context_step = run_cmd([
        "python3", str(CONTEXT),
        "--input-report", apply_step["report_json"],
        "--authorized-context", "controlled_content_apply_phase",
        "--apply-scope", "content_d1_r2_source"
    ])
    steps.append({"step": "content_controlled_apply_context_gate", **context_step})
    if context_step["returncode"] != 0 or not context_step["report_json"]:
        hard.append("content_controlled_apply_context_gate_failed")
        return finish(policy, args, steps, hard, "content_runtime_e2e_blocked")

    context_payload = load_json(context_step["report_json"])
    ctx = context_payload.get("content_controlled_apply_context") or {}
    for bad in unsafe_flags(context_payload):
        hard.append("content_controlled_apply_context_gate:unsafe_flag:" + bad)

    if ctx.get("content_controlled_apply_context_status") != "content_controlled_apply_context_ready_dry_run":
        final_status = "content_runtime_e2e_safe_stop_before_apply"
        return finish(policy, args, steps, hard, final_status)

    executor_step = run_cmd(["python3", str(EXECUTOR), "--input-report", context_step["report_json"], "--allow-real-apply"])
    steps.append({"step": "content_disabled_executor", **executor_step})
    if executor_step["returncode"] != 0 or not executor_step["report_json"]:
        hard.append("content_disabled_executor_failed")
        return finish(policy, args, steps, hard, "content_runtime_e2e_blocked")

    executor_payload = load_json(executor_step["report_json"])
    for bad in unsafe_flags(executor_payload):
        hard.append("content_disabled_executor:unsafe_flag:" + bad)

    if executor_payload.get("real_apply_executed") is not False:
        hard.append("executor_real_apply_executed_not_false")
    if executor_payload.get("content_written") is not False:
        hard.append("executor_content_written_not_false")
    if executor_payload.get("d1_written") is not False:
        hard.append("executor_d1_written_not_false")
    if executor_payload.get("r2_written") is not False:
        hard.append("executor_r2_written_not_false")
    if executor_payload.get("website_source_written") is not False:
        hard.append("executor_source_written_not_false")

    final_status = "content_runtime_e2e_guarded_for_later_controlled_apply"
    if hard:
        final_status = "content_runtime_e2e_blocked"

    return finish(policy, args, steps, hard, final_status)

def finish(policy, args, steps, hard, final_status):
    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-content-runtime-e2e-dry-run-orchestrator-v0",
        "mode": "dry_run",
        "input": {
            "origin": args.origin,
            "text": args.text
        },
        "policy": {
            "path": str(POLICY),
            "policy_id": policy.get("policy_id"),
            "policy_driven": policy.get("policy_driven"),
            "examples_are_non_exhaustive": policy.get("examples_are_non_exhaustive"),
            "not_real_apply": policy.get("not_real_apply")
        },
        "final_status": final_status,
        "step_count": len(steps),
        "steps": steps,
        "hard_failures": hard,
        "ready_for_later_controlled_content_apply": final_status == "content_runtime_e2e_guarded_for_later_controlled_apply",
        "real_apply_allowed_now": False,
        "production_deploy_ready": False,
        "safety": {
            "dry_run_only": True,
            "content_runtime_e2e_only": True,
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
    jp = REPORT_DIR / f"learning-v2-content-runtime-e2e-dry-run-orchestrator-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-content-runtime-e2e-dry-run-orchestrator-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Content Runtime E2E Dry-run Orchestrator\n\n"
        f"- final_status: `{final_status}`\n"
        f"- step_count: `{len(steps)}`\n"
        f"- hard_failure_count: `{len(hard)}`\n"
        f"- ready_for_later_controlled_content_apply: `{str(out['ready_for_later_controlled_content_apply']).lower()}`\n"
        "- real_apply_allowed_now: `false`\n"
        "- deploy: `false`\n",
        encoding="utf-8"
    )

    print("content_runtime_e2e_dry_run_orchestrator =", "ok" if not hard else "blocked")
    print("final_status =", final_status)
    print("step_count =", len(steps))
    print("hard_failure_count =", len(hard))
    print("ready_for_later_controlled_content_apply =", str(out["ready_for_later_controlled_content_apply"]).lower())
    print("real_apply_allowed_now = false")
    print("production_deploy_ready = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    raise SystemExit(0 if not hard else 1)

if __name__ == "__main__":
    main()
