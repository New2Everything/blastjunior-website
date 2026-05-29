#!/usr/bin/env python3
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
FACTORY = WORKSPACE / "scripts" / "learning-v2-content-proposal-factory-dry-run.py"
POLICY = WORKSPACE / "projects" / "BLXST-content-review-apply-policy.json"
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

def run_factory(origin, text):
    p = subprocess.run(
        ["python3", str(FACTORY), "--origin", origin, "--text", text],
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
        raise RuntimeError("factory_failed_or_report_missing\nSTDOUT:\n" + p.stdout + "\nSTDERR:\n" + p.stderr)
    return Path(report), load_json(report)

def load_factory_report(args):
    if args.input_report:
        p = Path(args.input_report)
        return p, load_json(p)
    return run_factory(args.origin, args.text)

def review(source, payload, policy):
    proposal = payload.get("content_proposal") or {}
    proposal_type = proposal.get("proposal_type")
    rules = policy.get("proposal_review_rules_non_exhaustive") or {}
    spec = rules.get(proposal_type)

    warnings = []
    blockers = []

    if not spec:
        spec = rules.get("review_gate_proposal", {})
        warnings.append("unknown_proposal_type_defaulted_to_review:" + str(proposal_type))
        blockers.append("unknown_proposal_type")

    if proposal.get("mutation_allowed") is not False:
        blockers.append("proposal_mutation_allowed_not_false")
    if proposal.get("deploy_allowed") is not False:
        blockers.append("proposal_deploy_allowed_not_false")
    if not proposal.get("provenance_ref"):
        blockers.append("provenance_ref_missing")
    if proposal.get("review_status") != "review_required":
        warnings.append("unexpected_review_status:" + str(proposal.get("review_status")))

    base_result = spec.get("review_result", "content_review_safe_stop_clarification_required")
    if blockers:
        result = "content_review_blocked"
        apply_allowed = False
    elif base_result == "content_review_ready_for_apply_rehearsal":
        result = base_result
        apply_allowed = True
    elif base_result == "content_review_handoff_to_registry_chain":
        result = base_result
        apply_allowed = False
    else:
        result = base_result
        apply_allowed = False

    return {
        "review_result": result,
        "proposal_type": proposal_type,
        "apply_rehearsal_allowed": apply_allowed,
        "apply_rehearsal_family": spec.get("apply_rehearsal_family", "none"),
        "real_apply_allowed": False,
        "mutation_allowed": False,
        "deploy_allowed": False,
        "source_content_proposal_report": str(source),
        "provenance_ref": proposal.get("provenance_ref"),
        "blockers": blockers,
        "warnings": warnings,
        "next_safe_action": "content_apply_rehearsal_dry_run" if apply_allowed else "review_or_registry_handoff_before_apply"
    }

def write_report(source, result, policy):
    ts = stamp()
    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-content-proposal-review-gate-v0",
        "mode": "dry_run",
        "policy": {
            "path": str(POLICY),
            "policy_id": policy.get("policy_id"),
            "policy_driven": policy.get("policy_driven"),
            "examples_are_non_exhaustive": policy.get("examples_are_non_exhaustive")
        },
        "content_review": result,
        "safety": {
            "dry_run_only": True,
            "review_only": True,
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
    jp = REPORT_DIR / f"learning-v2-content-proposal-review-gate-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-content-proposal-review-gate-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Content Proposal Review Gate\n\n"
        f"- review_result: `{result['review_result']}`\n"
        f"- proposal_type: `{result['proposal_type']}`\n"
        f"- apply_rehearsal_allowed: `{str(result['apply_rehearsal_allowed']).lower()}`\n"
        "- real_apply_allowed: `false`\n"
        "- deploy: `false`\n",
        encoding="utf-8"
    )
    return jp, mp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-report")
    ap.add_argument("--origin", default="user_direct_with_/blxst")
    ap.add_argument("--text", default="/blxst 这是HPL最新比赛记录：A队 5:3 B队，请创建赛事独立页面并更新积分。")
    args = ap.parse_args()

    policy = load_json(POLICY)
    source, payload = load_factory_report(args)
    result = review(source, payload, policy)
    jp, mp = write_report(source, result, policy)

    print("content_proposal_review_gate = ok")
    print("review_result =", result["review_result"])
    print("proposal_type =", result["proposal_type"])
    print("apply_rehearsal_allowed =", str(result["apply_rehearsal_allowed"]).lower())
    print("real_apply_allowed = false")
    print("mutation_allowed = false")
    print("deploy = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    raise SystemExit(0)

if __name__ == "__main__":
    main()
