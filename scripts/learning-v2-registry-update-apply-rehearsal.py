#!/usr/bin/env python3
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
REVIEWER = WORKSPACE / "scripts" / "learning-v2-registry-update-proposal-review-gate.py"
POLICY = WORKSPACE / "projects" / "BLXST-registry-update-apply-rehearsal-policy.json"
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

def run_review_simulation(name):
    p = subprocess.run(
        ["python3", str(REVIEWER), "--simulate", name],
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
        raise RuntimeError("review_failed_or_report_missing\nSTDOUT:\n" + p.stdout + "\nSTDERR:\n" + p.stderr)
    return Path(report), load_json(report)

def load_review_report(args):
    if args.simulate:
        return run_review_simulation(args.simulate)
    if args.input_report:
        p = Path(args.input_report)
        return p, load_json(p)
    p = latest("learning-v2-registry-update-proposal-review-gate-*.json")
    if not p:
        raise SystemExit("BLOCKED: no registry review report found")
    return p, load_json(p)

def build_apply_rehearsal(review_payload, policy):
    review = review_payload.get("proposal_review") or {}
    allowed = bool(review.get("apply_rehearsal_allowed"))
    reasons = list(review.get("reasons") or [])
    warnings = list(review.get("warnings") or [])

    if allowed:
        status = "registry_apply_rehearsal_ready"
        next_safe_action = "explicit_registry_apply_gate_required"
        blockers = []
    else:
        status = "registry_apply_rehearsal_blocked"
        next_safe_action = "return_to_review_or_triage"
        blockers = ["apply_rehearsal_not_allowed_by_review_gate"]

    plan = {
        "apply_rehearsal_status": status,
        "apply_rehearsal_only": True,
        "real_apply_allowed": False,
        "registry_write_allowed": False,
        "mutation_allowed": False,
        "source_review_result": review.get("review_result"),
        "source_apply_rehearsal_allowed": allowed,
        "draft_apply_manifest": {
            "status": "draft_only",
            "candidate_operations_non_exhaustive": [
                "draft_resource_registry_patch",
                "draft_routing_rule_patch",
                "draft_gate_policy_patch",
                "draft_validation_plan",
                "draft_rollback_or_recovery_note"
            ],
            "write_now": False
        },
        "validation_plan": {
            "status": "draft_only",
            "checks_non_exhaustive": [
                "json_schema_valid",
                "contract_markers_present",
                "unknown_resource_no_longer_unclassified",
                "system_integrity_after_apply",
                "no_cloudflare_mutation"
            ],
            "execute_now": False
        },
        "rollback_or_recovery_note": {
            "status": "draft_only",
            "required_before_real_apply": True
        },
        "blockers": blockers,
        "reasons": reasons,
        "warnings": warnings,
        "next_safe_action": next_safe_action,
        "why_not_apply": "This is apply rehearsal only; real registry writes require separate explicit apply gate and rollback rehearsal."
    }
    return plan

def write_report(source, plan, policy):
    ts = stamp()
    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-registry-update-apply-rehearsal-v0",
        "mode": "dry_run",
        "source_review_report": str(source),
        "policy": {
            "path": str(POLICY),
            "policy_id": policy.get("policy_id"),
            "policy_driven": policy.get("policy_driven"),
            "examples_are_non_exhaustive": policy.get("examples_are_non_exhaustive"),
            "not_real_apply": policy.get("not_real_apply")
        },
        "registry_apply_rehearsal": plan,
        "safety": {
            "dry_run_only": True,
            "apply_rehearsal_only": True,
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
    jp = REPORT_DIR / f"learning-v2-registry-update-apply-rehearsal-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-registry-update-apply-rehearsal-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Registry Update Apply Rehearsal\n\n"
        f"- apply_rehearsal_status: `{plan['apply_rehearsal_status']}`\n"
        "- real_apply_allowed: `false`\n"
        "- registry_write_allowed: `false`\n"
        "- deploy: `false`\n",
        encoding="utf-8"
    )
    return jp, mp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-report")
    ap.add_argument("--simulate", choices=["ok","unknown_resource","no_auth","hard_failure","unexpected_status"])
    args = ap.parse_args()

    policy = load_json(POLICY)
    source, review_payload = load_review_report(args)
    plan = build_apply_rehearsal(review_payload, policy)
    jp, mp = write_report(source, plan, policy)

    print("registry_update_apply_rehearsal = ok")
    print("apply_rehearsal_status =", plan["apply_rehearsal_status"])
    print("next_safe_action =", plan["next_safe_action"])
    print("real_apply_allowed = false")
    print("registry_write_allowed = false")
    print("mutation_allowed = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
