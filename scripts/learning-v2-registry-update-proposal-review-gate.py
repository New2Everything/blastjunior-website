#!/usr/bin/env python3
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
PROPOSAL = WORKSPACE / "scripts" / "learning-v2-registry-update-proposal-dry-run.py"
POLICY = WORKSPACE / "projects" / "BLXST-registry-update-review-policy.json"
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

def run_proposal_simulation(name):
    p = subprocess.run(
        ["python3", str(PROPOSAL), "--simulate", name],
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
        raise RuntimeError("proposal_failed_or_report_missing\nSTDOUT:\n" + p.stdout + "\nSTDERR:\n" + p.stderr)
    return Path(report), load_json(report)

def load_proposal_report(args):
    if args.simulate:
        return run_proposal_simulation(args.simulate)
    if args.input_report:
        p = Path(args.input_report)
        return p, load_json(p)
    p = latest("learning-v2-registry-update-proposal-dry-run-*.json")
    if not p:
        raise SystemExit("BLOCKED: no registry update proposal report found")
    return p, load_json(p)

def review(payload, policy):
    proposal = payload.get("registry_update_proposal") or {}
    status = proposal.get("proposal_status")
    blockers = list(proposal.get("blockers") or [])
    required = proposal.get("required_fields_before_apply_non_exhaustive") or []
    candidate = proposal.get("candidate_update_shape") or {}

    reasons = []
    warnings = []

    if not proposal:
        result = "proposal_review_not_applicable"
        reasons.append("registry_update_proposal_missing")
    elif status == "registry_update_proposal_ready" and not blockers:
        result = "proposal_review_ready"
        reasons.append("proposal_structurally_ready_for_later_apply_rehearsal")
    elif status == "not_applicable_review_required":
        result = "proposal_review_not_applicable"
        reasons.extend(blockers or ["proposal_not_applicable"])
    elif blockers:
        result = "proposal_review_blocked"
        reasons.extend(blockers)
    else:
        result = "proposal_review_triage_required"
        reasons.append("unknown_or_future_proposal_status:" + str(status))

    if not required:
        warnings.append("required_fields_list_missing_or_empty")
    if not candidate:
        warnings.append("candidate_update_shape_missing")

    return {
        "review_result": result,
        "apply_rehearsal_allowed": result == "proposal_review_ready",
        "real_apply_allowed": False,
        "registry_write_allowed": False,
        "mutation_allowed": False,
        "reasons": sorted(set(reasons)),
        "warnings": sorted(set(warnings)),
        "required_fields_reviewed_non_exhaustive": required,
        "candidate_update_shape_seen": bool(candidate),
        "next_safe_action": "registry_update_apply_rehearsal_dry_run" if result == "proposal_review_ready" else "review_or_triage_before_apply"
    }

def write_report(source, review_result, policy):
    ts = stamp()
    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-registry-update-proposal-review-gate-v0",
        "mode": "dry_run",
        "source_proposal_report": str(source),
        "policy": {
            "path": str(POLICY),
            "policy_id": policy.get("policy_id"),
            "policy_driven": policy.get("policy_driven"),
            "examples_are_non_exhaustive": policy.get("examples_are_non_exhaustive"),
            "not_auto_repair": policy.get("not_auto_repair"),
            "not_auto_approve": policy.get("not_auto_approve")
        },
        "proposal_review": review_result,
        "safety": {
            "dry_run_only": True,
            "review_only": True,
            "auto_approval": False,
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
    jp = REPORT_DIR / f"learning-v2-registry-update-proposal-review-gate-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-registry-update-proposal-review-gate-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Registry Update Proposal Review Gate\n\n"
        f"- review_result: `{review_result['review_result']}`\n"
        f"- apply_rehearsal_allowed: `{str(review_result['apply_rehearsal_allowed']).lower()}`\n"
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
    source, payload = load_proposal_report(args)
    result = review(payload, policy)
    jp, mp = write_report(source, result, policy)

    print("registry_update_proposal_review_gate = ok")
    print("review_result =", result["review_result"])
    print("apply_rehearsal_allowed =", str(result["apply_rehearsal_allowed"]).lower())
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
