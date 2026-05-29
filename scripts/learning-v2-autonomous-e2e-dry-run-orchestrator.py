#!/usr/bin/env python3
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
POLICY = WORKSPACE / "projects" / "BLXST-autonomous-e2e-orchestrator-policy.json"
REPORT_DIR = WORKSPACE / "learning-v2" / "reports"
SNAPSHOT_DIR = WORKSPACE / "learning-v2" / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPTS = {
    "gate_plan": WORKSPACE / "scripts" / "learning-v2-gate-plan-dry-run.py",
    "resolver": WORKSPACE / "scripts" / "learning-v2-failure-context-resolver.py",
    "dispatcher": WORKSPACE / "scripts" / "learning-v2-autonomous-next-action-dispatcher.py",
    "handler": WORKSPACE / "scripts" / "learning-v2-next-action-dry-run-handler.py",
    "proposal": WORKSPACE / "scripts" / "learning-v2-registry-update-proposal-dry-run.py",
    "review": WORKSPACE / "scripts" / "learning-v2-registry-update-proposal-review-gate.py",
    "apply": WORKSPACE / "scripts" / "learning-v2-registry-update-apply-rehearsal.py",
    "explicit_apply": WORKSPACE / "scripts" / "learning-v2-registry-update-explicit-apply-gate.py"
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def run_step(name, args):
    cmd = ["python3", str(SCRIPTS[name])] + args
    p = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    report = None
    for line in p.stdout.splitlines():
        if line.startswith("report_json ="):
            report = line.split("=", 1)[1].strip()
    ok = (p.returncode == 0 and report)
    return {
        "step": name,
        "ok": bool(ok),
        "returncode": p.returncode,
        "report_json": report,
        "stdout_tail": "\n".join(p.stdout.splitlines()[-12:]),
        "stderr_tail": "\n".join(p.stderr.splitlines()[-12:])
    }

def unsafe_flags(payload):
    safety = payload.get("safety") or {}
    bad = []
    for key in [
        "registry_written","website_source_written","d1_written","r2_written","kv_written",
        "worker_changed","cloudflare_mutation","git_commit","git_push","deploy"
    ]:
        if safety.get(key) is not False and safety.get(key) is not None:
            bad.append(f"{key}:{safety.get(key)}")
    return bad

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", required=True)
    ap.add_argument("--text", required=True)
    args = ap.parse_args()

    policy = load_json(POLICY)
    steps = []
    hard_failures = []

    # 1 gate plan
    s = run_step("gate_plan", ["--origin", args.origin, "--text", args.text])
    steps.append(s)
    if not s["ok"]:
        hard_failures.append("gate_plan_failed")
        return finish(policy, args, steps, hard_failures, "e2e_blocked_gate_plan_failed")
    gate_payload = load_json(s["report_json"])

    # 2 resolver
    s = run_step("resolver", ["--input-report", steps[-1]["report_json"]])
    steps.append(s)
    if not s["ok"]:
        hard_failures.append("resolver_failed")
        return finish(policy, args, steps, hard_failures, "e2e_blocked_resolver_failed")
    resolver_payload = load_json(s["report_json"])

    # 3 dispatcher
    s = run_step("dispatcher", ["--input-report", steps[-1]["report_json"]])
    steps.append(s)
    if not s["ok"]:
        hard_failures.append("dispatcher_failed")
        return finish(policy, args, steps, hard_failures, "e2e_blocked_dispatcher_failed")
    dispatcher_payload = load_json(s["report_json"])

    # 4 handler
    s = run_step("handler", ["--input-report", steps[-1]["report_json"]])
    steps.append(s)
    if not s["ok"]:
        hard_failures.append("handler_failed")
        return finish(policy, args, steps, hard_failures, "e2e_blocked_handler_failed")
    handler_payload = load_json(s["report_json"])

    hp = handler_payload.get("handler_proposal") or {}
    family = hp.get("handler_family")
    result = hp.get("handler_result")

    final_status = "e2e_safe_stop_or_recommendation_only"
    branch = family

    # Registry branch only if policy selected update_resource_registry.
    if family == "update_resource_registry" and result == "registry_update_proposal_created":
        for step_name in ["proposal", "review", "apply", "explicit_apply"]:
            s = run_step(step_name, ["--input-report", steps[-1]["report_json"]])
            steps.append(s)
            if not s["ok"]:
                hard_failures.append(step_name + "_failed")
                return finish(policy, args, steps, hard_failures, "e2e_blocked_" + step_name + "_failed")

        explicit_payload = load_json(steps[-1]["report_json"])
        gate = explicit_payload.get("explicit_apply_gate") or {}
        if gate.get("explicit_apply_gate_status") == "explicit_apply_gate_ready":
            final_status = "e2e_ready_for_later_controlled_apply_context"
        else:
            final_status = "e2e_registry_branch_blocked_before_controlled_apply"
    elif family == "request_authorized_context":
        final_status = "e2e_safe_stop_authorization_required"
    elif family in {"triage_unknown_state", "fix_failed_step"}:
        final_status = "e2e_safe_stop_triage_required"
    elif family in {"run_review_gate", "do_not_mutate"}:
        final_status = "e2e_safe_stop_review_or_safety_stop"
    elif family in {"rerun_gate_plan", "rerun_classifier"}:
        final_status = "e2e_next_dry_run_recommendation_only"

    # Check all produced report safety.
    for st in steps:
        if st.get("report_json"):
            try:
                payload = load_json(st["report_json"])
                for bad in unsafe_flags(payload):
                    hard_failures.append(st["step"] + ":unsafe_flag:" + bad)
            except Exception as e:
                hard_failures.append(st["step"] + ":report_read_failed:" + str(e))

    if hard_failures:
        final_status = "e2e_blocked_safety_or_step_failure"

    return finish(policy, args, steps, hard_failures, final_status, branch)

def finish(policy, args, steps, hard_failures, final_status, branch=None):
    ts = stamp()
    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-autonomous-e2e-dry-run-orchestrator-v0",
        "mode": "dry_run",
        "input": {"origin": args.origin, "text": args.text},
        "policy": {
            "path": str(POLICY),
            "policy_id": policy.get("policy_id"),
            "policy_driven": policy.get("policy_driven"),
            "examples_are_non_exhaustive": policy.get("examples_are_non_exhaustive"),
            "not_real_apply": policy.get("not_real_apply")
        },
        "branch": branch,
        "final_status": final_status,
        "step_count": len(steps),
        "steps": steps,
        "hard_failures": hard_failures,
        "ready_for_later_controlled_context": final_status == "e2e_ready_for_later_controlled_apply_context",
        "real_apply_allowed_now": False,
        "safety": {
            "dry_run_only": True,
            "orchestration_only": True,
            "execution_allowed": False,
            "mutation_allowed": False,
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
    jp = REPORT_DIR / f"learning-v2-autonomous-e2e-dry-run-orchestrator-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-autonomous-e2e-dry-run-orchestrator-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Autonomous E2E Dry-run Orchestrator\n\n"
        f"- final_status: `{final_status}`\n"
        f"- step_count: `{len(steps)}`\n"
        f"- hard_failure_count: `{len(hard_failures)}`\n"
        f"- ready_for_later_controlled_context: `{str(out['ready_for_later_controlled_context']).lower()}`\n"
        "- real_apply_allowed_now: `false`\n"
        "- deploy: `false`\n",
        encoding="utf-8"
    )

    print("autonomous_e2e_dry_run_orchestrator =", "ok" if not hard_failures else "blocked")
    print("final_status =", final_status)
    print("step_count =", len(steps))
    print("hard_failure_count =", len(hard_failures))
    print("ready_for_later_controlled_context =", str(out["ready_for_later_controlled_context"]).lower())
    print("real_apply_allowed_now = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    raise SystemExit(0 if not hard_failures else 1)

if __name__ == "__main__":
    main()
