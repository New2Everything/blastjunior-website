#!/usr/bin/env python3
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
ORCHESTRATOR = WORKSPACE / "scripts" / "learning-v2-autonomous-e2e-dry-run-orchestrator.py"
POLICY = WORKSPACE / "projects" / "BLXST-controlled-apply-context-policy.json"
REPORT_DIR = WORKSPACE / "learning-v2" / "reports"
SNAPSHOT_DIR = WORKSPACE / "learning-v2" / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))

def latest(pattern):
    files = sorted(REPORT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None

def run_e2e_ready():
    p = subprocess.run(
        ["python3", str(ORCHESTRATOR), "--origin", "user_direct_with_/blxst", "--text", "/blxst 新增一个赛事数据表，用来记录未来HPL每一轮详细战报"],
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
        raise RuntimeError("e2e_orchestrator_failed_or_report_missing\nSTDOUT:\n" + p.stdout + "\nSTDERR:\n" + p.stderr)
    return Path(report), load_json(report)

def load_e2e_report(args):
    if args.simulate_ready:
        return run_e2e_ready()
    if args.input_report:
        p = Path(args.input_report)
        return p, load_json(p)
    p = latest("learning-v2-autonomous-e2e-dry-run-orchestrator-*.json")
    if not p:
        raise SystemExit("BLOCKED: no e2e orchestrator report found")
    return p, load_json(p)

def git_clean():
    p = subprocess.run(["git", "status", "--porcelain"], cwd=str(WORKSPACE), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode == 0 and not p.stdout.strip()

def integrity_ok():
    p = subprocess.run(["python3", "scripts/learning-v2-system-integrity.py"], cwd=str(WORKSPACE), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode == 0 and "system_integrity = ok" in p.stdout

def evaluate_context(e2e_payload, args, policy):
    blockers = []
    ready = bool(e2e_payload.get("ready_for_later_controlled_context"))
    final_status = e2e_payload.get("final_status")

    if not ready:
        blockers.append("e2e_not_ready_for_later_controlled_context:" + str(final_status))
    if not integrity_ok():
        blockers.append("system_integrity_not_ok")
    if not git_clean():
        blockers.append("worktree_not_clean")
    if args.authorized_context != "controlled_registry_apply_phase":
        blockers.append("authorized_context_not_controlled_registry_apply_phase:" + str(args.authorized_context))
    if args.apply_scope not in {"registry_policy_routing_only"}:
        blockers.append("apply_scope_not_allowed:" + str(args.apply_scope))
    if args.real_apply_enabled:
        blockers.append("real_apply_enabled_true_not_allowed_in_this_phase")

    status = "controlled_apply_context_ready_dry_run" if not blockers else "controlled_apply_context_blocked"

    return {
        "controlled_apply_context_status": status,
        "future_executor_context_candidate": status == "controlled_apply_context_ready_dry_run",
        "real_apply_allowed_now": False,
        "registry_write_allowed_now": False,
        "mutation_allowed": False,
        "blockers": blockers,
        "source_e2e_final_status": final_status,
        "source_ready_for_later_controlled_context": ready,
        "authorized_context": args.authorized_context,
        "apply_scope": args.apply_scope,
        "requirements_checked_non_exhaustive": policy.get("controlled_apply_context_requirements_non_exhaustive") or [],
        "why_not_apply_now": "This phase validates context gate only; real apply remains disabled."
    }

def write_report(source, context, policy):
    ts = stamp()
    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-controlled-apply-context-gate-v0",
        "mode": "dry_run",
        "source_e2e_report": str(source),
        "policy": {
            "path": str(POLICY),
            "policy_id": policy.get("policy_id"),
            "policy_driven": policy.get("policy_driven"),
            "real_apply_default": policy.get("real_apply_default")
        },
        "controlled_apply_context": context,
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
    jp = REPORT_DIR / f"learning-v2-controlled-apply-context-gate-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-controlled-apply-context-gate-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Controlled Apply Context Gate\n\n"
        f"- controlled_apply_context_status: `{context['controlled_apply_context_status']}`\n"
        f"- future_executor_context_candidate: `{str(context['future_executor_context_candidate']).lower()}`\n"
        "- real_apply_allowed_now: `false`\n"
        "- registry_write_allowed_now: `false`\n"
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
    source, e2e_payload = load_e2e_report(args)
    context = evaluate_context(e2e_payload, args, policy)
    jp, mp = write_report(source, context, policy)

    print("controlled_apply_context_gate = ok")
    print("controlled_apply_context_status =", context["controlled_apply_context_status"])
    print("future_executor_context_candidate =", str(context["future_executor_context_candidate"]).lower())
    print("real_apply_allowed_now = false")
    print("registry_write_allowed_now = false")
    print("mutation_allowed = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
