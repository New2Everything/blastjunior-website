#!/usr/bin/env python3
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
APPLY = WORKSPACE / "scripts" / "learning-v2-content-apply-rehearsal-dry-run.py"
POLICY = WORKSPACE / "projects" / "BLXST-content-controlled-apply-policy.json"
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

def run_apply_ready():
    p = subprocess.run(
        [
            "python3", str(APPLY),
            "--origin", "user_direct_with_/blxst",
            "--text", "/blxst 这是HPL最新比赛记录：A队 5:3 B队，请创建赛事独立页面并更新积分。"
        ],
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    report = None
    for line in p.stdout.splitlines():
        if line.startswith("report_json ="):
            report = line.split("=", 1)[1].strip()
    if p.returncode != 0 or not report:
        raise RuntimeError("content_apply_rehearsal_failed_or_report_missing\nSTDOUT:\n" + p.stdout + "\nSTDERR:\n" + p.stderr)
    return Path(report), load_json(report)

def load_apply_report(args):
    if args.simulate_ready:
        return run_apply_ready()
    if args.input_report:
        p = Path(args.input_report)
        return p, load_json(p)
    raise SystemExit("BLOCKED: provide --input-report or --simulate-ready")

def git_clean():
    p = subprocess.run(["git", "status", "--porcelain"], cwd=str(WORKSPACE), text=True, stdout=subprocess.PIPE)
    return p.returncode == 0 and not p.stdout.strip()

def integrity_ok():
    p = subprocess.run(["python3", "scripts/learning-v2-system-integrity.py"], cwd=str(WORKSPACE), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode == 0 and "system_integrity = ok" in p.stdout

def evaluate_context(source, payload, args, policy):
    plan = payload.get("content_apply_rehearsal") or {}
    blockers = []
    allowed_scopes = set(policy.get("allowed_apply_scopes_non_exhaustive") or [])

    if plan.get("apply_rehearsal_status") != "content_apply_rehearsal_ready":
        blockers.append("content_apply_rehearsal_not_ready:" + str(plan.get("apply_rehearsal_status")))
    if not plan.get("rollback_or_recovery_note"):
        blockers.append("rollback_or_recovery_note_missing")
    if not integrity_ok():
        blockers.append("system_integrity_not_ok")
    if not git_clean():
        blockers.append("worktree_not_clean")
    if args.authorized_context != "controlled_content_apply_phase":
        blockers.append("authorized_context_not_controlled_content_apply_phase:" + str(args.authorized_context))
    if args.apply_scope not in allowed_scopes:
        blockers.append("apply_scope_not_allowed:" + str(args.apply_scope))
    if args.real_apply_enabled:
        blockers.append("real_apply_enabled_true_not_allowed_in_this_phase")
    if plan.get("real_apply_allowed") is not False:
        blockers.append("source_rehearsal_real_apply_allowed_not_false")
    if plan.get("mutation_allowed") is not False:
        blockers.append("source_rehearsal_mutation_allowed_not_false")

    status = "content_controlled_apply_context_ready_dry_run" if not blockers else "content_controlled_apply_context_blocked"

    return {
        "content_controlled_apply_context_status": status,
        "future_executor_context_candidate": status == "content_controlled_apply_context_ready_dry_run",
        "real_apply_allowed_now": False,
        "content_write_allowed_now": False,
        "mutation_allowed": False,
        "deploy_allowed": False,
        "blockers": blockers,
        "source_content_apply_rehearsal_report": str(source),
        "source_apply_rehearsal_status": plan.get("apply_rehearsal_status"),
        "source_apply_rehearsal_family": plan.get("apply_rehearsal_family"),
        "authorized_context": args.authorized_context,
        "apply_scope": args.apply_scope,
        "requirements_checked_non_exhaustive": policy.get("controlled_content_apply_context_requirements_non_exhaustive") or [],
        "why_not_apply_now": "This phase validates context gate only; real content apply remains disabled."
    }

def write_report(source, context, policy):
    ts = stamp()
    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-content-controlled-apply-context-gate-v0",
        "mode": "dry_run",
        "source_content_apply_rehearsal_report": str(source),
        "policy": {
            "path": str(POLICY),
            "policy_id": policy.get("policy_id"),
            "policy_driven": policy.get("policy_driven"),
            "real_apply_default": policy.get("real_apply_default")
        },
        "content_controlled_apply_context": context,
        "safety": {
            "dry_run_only": True,
            "context_gate_only": True,
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
    jp = REPORT_DIR / f"learning-v2-content-controlled-apply-context-gate-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-content-controlled-apply-context-gate-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Content Controlled Apply Context Gate\n\n"
        f"- content_controlled_apply_context_status: `{context['content_controlled_apply_context_status']}`\n"
        f"- future_executor_context_candidate: `{str(context['future_executor_context_candidate']).lower()}`\n"
        "- real_apply_allowed_now: `false`\n"
        "- content_write_allowed_now: `false`\n"
        "- deploy: `false`\n",
        encoding="utf-8"
    )
    return jp, mp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-report")
    ap.add_argument("--simulate-ready", action="store_true")
    ap.add_argument("--authorized-context", default="manual_probe")
    ap.add_argument("--apply-scope", default="none")
    ap.add_argument("--real-apply-enabled", action="store_true")
    args = ap.parse_args()

    policy = load_json(POLICY)
    source, payload = load_apply_report(args)
    context = evaluate_context(source, payload, args, policy)
    jp, mp = write_report(source, context, policy)

    print("content_controlled_apply_context_gate = ok")
    print("content_controlled_apply_context_status =", context["content_controlled_apply_context_status"])
    print("future_executor_context_candidate =", str(context["future_executor_context_candidate"]).lower())
    print("real_apply_allowed_now = false")
    print("content_write_allowed_now = false")
    print("mutation_allowed = false")
    print("deploy = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    raise SystemExit(0)

if __name__ == "__main__":
    main()
