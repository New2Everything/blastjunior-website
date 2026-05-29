#!/usr/bin/env python3
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
APPLY = WORKSPACE / "scripts" / "learning-v2-registry-update-apply-rehearsal.py"
POLICY = WORKSPACE / "projects" / "BLXST-registry-explicit-apply-policy.json"
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

def latest(pattern):
    files = sorted(REPORT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None

def run_apply_simulation(name):
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
        raise RuntimeError("apply_rehearsal_failed_or_report_missing\nSTDOUT:\n" + p.stdout + "\nSTDERR:\n" + p.stderr)
    return Path(report), load_json(report)

def load_apply_report(args):
    if args.simulate:
        return run_apply_simulation(args.simulate)
    if args.input_report:
        p = Path(args.input_report)
        return p, load_json(p)
    p = latest("learning-v2-registry-update-apply-rehearsal-*.json")
    if not p:
        raise SystemExit("BLOCKED: no registry apply rehearsal report found")
    return p, load_json(p)

def check_gate(payload, policy):
    rehearsal = payload.get("registry_apply_rehearsal") or {}
    status = rehearsal.get("apply_rehearsal_status")
    manifest = rehearsal.get("draft_apply_manifest") or {}
    validation = rehearsal.get("validation_plan") or {}
    rollback = rehearsal.get("rollback_or_recovery_note") or {}

    blockers = []
    if status != "registry_apply_rehearsal_ready":
        blockers.append("apply_rehearsal_not_ready:" + str(status))
    if not manifest:
        blockers.append("draft_apply_manifest_missing")
    if not validation:
        blockers.append("validation_plan_missing")
    if not rollback:
        blockers.append("rollback_or_recovery_note_missing")

    gate_status = "explicit_apply_gate_ready" if not blockers else "explicit_apply_gate_blocked"
    return {
        "explicit_apply_gate_status": gate_status,
        "future_real_apply_candidate": gate_status == "explicit_apply_gate_ready",
        "real_apply_allowed_now": False,
        "registry_write_allowed": False,
        "mutation_allowed": False,
        "blockers": blockers,
        "source_apply_rehearsal_status": status,
        "requirements_checked_non_exhaustive": policy.get("explicit_apply_gate_requirements_non_exhaustive") or [],
        "next_safe_action": "rollback_rehearsal_then_controlled_apply_context" if not blockers else "return_to_apply_rehearsal_or_review",
        "why_not_apply_now": "This phase is dry-run only; real apply requires separate controlled apply context."
    }

def write_report(source, gate, policy):
    ts = stamp()
    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-registry-update-explicit-apply-gate-v0",
        "mode": "dry_run",
        "source_apply_rehearsal_report": str(source),
        "policy": {
            "path": str(POLICY),
            "policy_id": policy.get("policy_id"),
            "policy_driven": policy.get("policy_driven"),
            "examples_are_non_exhaustive": policy.get("examples_are_non_exhaustive"),
            "not_real_apply": policy.get("not_real_apply")
        },
        "explicit_apply_gate": gate,
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
    jp = REPORT_DIR / f"learning-v2-registry-update-explicit-apply-gate-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-registry-update-explicit-apply-gate-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Registry Update Explicit Apply Gate\n\n"
        f"- explicit_apply_gate_status: `{gate['explicit_apply_gate_status']}`\n"
        f"- future_real_apply_candidate: `{str(gate['future_real_apply_candidate']).lower()}`\n"
        "- real_apply_allowed_now: `false`\n"
        "- registry_write_allowed: `false`\n"
        "- deploy: `false`\n",
        encoding="utf-8"
    )
    return jp, mp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-report")
    ap.add_argument("--simulate", choices=["unknown_resource","no_auth","unexpected_status"])
    args = ap.parse_args()

    policy = load_json(POLICY)
    source, payload = load_apply_report(args)
    gate = check_gate(payload, policy)
    jp, mp = write_report(source, gate, policy)

    print("registry_update_explicit_apply_gate = ok")
    print("explicit_apply_gate_status =", gate["explicit_apply_gate_status"])
    print("future_real_apply_candidate =", str(gate["future_real_apply_candidate"]).lower())
    print("real_apply_allowed_now = false")
    print("registry_write_allowed = false")
    print("mutation_allowed = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
