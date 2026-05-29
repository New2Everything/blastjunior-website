#!/usr/bin/env python3
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
APPLY_GATE = WORKSPACE / "scripts" / "learning-v2-registry-update-explicit-apply-gate.py"
POLICY = WORKSPACE / "projects" / "BLXST-registry-explicit-apply-policy.json"
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

def run_gate(name):
    p = subprocess.run(
        ["python3", str(APPLY_GATE), "--simulate", name],
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
        raise RuntimeError("apply_gate_failed_or_report_missing\nSTDOUT:\n" + p.stdout + "\nSTDERR:\n" + p.stderr)
    return Path(report), load_json(report)

def build_rollback(gate_payload, policy):
    gate = gate_payload.get("explicit_apply_gate") or {}
    ready = gate.get("explicit_apply_gate_status") == "explicit_apply_gate_ready"
    status = "rollback_rehearsal_ready" if ready else "rollback_rehearsal_blocked"
    return {
        "rollback_rehearsal_status": status,
        "source_explicit_apply_gate_status": gate.get("explicit_apply_gate_status"),
        "rollback_only": True,
        "rollback_execute_allowed": False,
        "registry_write_allowed": False,
        "mutation_allowed": False,
        "draft_restore_strategy": {
            "status": "draft_only",
            "restore_sources_non_exhaustive": [
                "git previous commit",
                "baseline snapshot",
                "registry file diff",
                "validation report"
            ],
            "execute_now": False
        },
        "post_rollback_validation_plan": {
            "status": "draft_only",
            "checks_non_exhaustive": [
                "json_valid",
                "system_integrity_ok",
                "classifier_unknown_resource_behavior_preserved",
                "no_cloudflare_mutation"
            ],
            "execute_now": False
        },
        "requirements_checked_non_exhaustive": policy.get("rollback_rehearsal_requirements_non_exhaustive") or [],
        "next_safe_action": "controlled_apply_context_required" if ready else "return_to_explicit_apply_gate"
    }

def write_report(source, rollback, policy):
    ts = stamp()
    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-registry-update-rollback-rehearsal-v0",
        "mode": "dry_run",
        "source_explicit_apply_gate_report": str(source),
        "policy_id": policy.get("policy_id"),
        "rollback_rehearsal": rollback,
        "safety": {
            "dry_run_only": True,
            "rollback_execute_allowed": False,
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
    jp = REPORT_DIR / f"learning-v2-registry-update-rollback-rehearsal-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-registry-update-rollback-rehearsal-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Registry Update Rollback Rehearsal\n\n"
        f"- rollback_rehearsal_status: `{rollback['rollback_rehearsal_status']}`\n"
        "- rollback_execute_allowed: `false`\n"
        "- registry_write_allowed: `false`\n"
        "- deploy: `false`\n",
        encoding="utf-8"
    )
    return jp, mp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulate", choices=["unknown_resource","no_auth","unexpected_status"], default="unknown_resource")
    args = ap.parse_args()
    policy = load_json(POLICY)
    source, gate_payload = run_gate(args.simulate)
    rb = build_rollback(gate_payload, policy)
    jp, mp = write_report(source, rb, policy)
    print("registry_update_rollback_rehearsal = ok")
    print("rollback_rehearsal_status =", rb["rollback_rehearsal_status"])
    print("rollback_execute_allowed = false")
    print("registry_write_allowed = false")
    print("mutation_allowed = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
