#!/usr/bin/env python3
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
HANDLER = WORKSPACE / "scripts" / "learning-v2-next-action-dry-run-handler.py"
POLICY = WORKSPACE / "projects" / "BLXST-registry-update-proposal-policy.json"
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

def run_handler_simulation(name):
    p = subprocess.run(
        ["python3", str(HANDLER), "--simulate", name],
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
        raise RuntimeError("handler_failed_or_report_missing\nSTDOUT:\n" + p.stdout + "\nSTDERR:\n" + p.stderr)
    return Path(report), load_json(report)

def load_handler_report(args):
    if args.simulate:
        return run_handler_simulation(args.simulate)
    if args.input_report:
        p = Path(args.input_report)
        return p, load_json(p)
    p = latest("learning-v2-next-action-dry-run-handler-*.json")
    if not p:
        raise SystemExit("BLOCKED: no next-action handler report found")
    return p, load_json(p)

def build_proposal(handler_payload, policy):
    hp = handler_payload.get("handler_proposal") or {}
    family = hp.get("handler_family")
    result = hp.get("handler_result")

    warnings = []
    blockers = []

    if family != "update_resource_registry":
        blockers.append("handler_family_not_update_resource_registry:" + str(family))
        proposal_status = "not_applicable_review_required"
    elif result != "registry_update_proposal_created":
        blockers.append("handler_result_not_registry_update_proposal_created:" + str(result))
        proposal_status = "not_applicable_review_required"
    else:
        proposal_status = "registry_update_proposal_ready"

    required_fields = policy.get("required_fields_before_apply_non_exhaustive") or []
    targets = policy.get("proposal_targets_non_exhaustive") or {}

    proposal = {
        "proposal_status": proposal_status,
        "proposal_only": True,
        "registry_write_allowed": False,
        "mutation_allowed": False,
        "source_handler_family": family,
        "source_handler_result": result,
        "recommended_update_targets": targets,
        "required_fields_before_apply_non_exhaustive": required_fields,
        "candidate_update_shape": {
            "resource_registry_patch": {
                "status": "draft_only",
                "must_include": required_fields,
                "write_now": False
            },
            "routing_rule_patch": {
                "status": "draft_only",
                "must_include": [
                    "operation_intent",
                    "resource_type",
                    "resource_scope",
                    "gate_policy_family",
                    "unknown_resource_review_rule"
                ],
                "write_now": False
            },
            "gate_policy_patch": {
                "status": "draft_only",
                "must_include": [
                    "resource_type_or_family",
                    "risk_level",
                    "required_gate_families",
                    "provenance_requirement",
                    "review_status"
                ],
                "write_now": False
            }
        },
        "blockers": blockers,
        "warnings": warnings,
        "next_safe_action": "review_registry_update_proposal" if not blockers else "run_review_gate",
        "why_not_apply": "Registry updates require separate review/apply rehearsal; this stage is proposal-only."
    }
    return proposal

def write_report(source, proposal, policy):
    ts = stamp()
    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-registry-update-proposal-dry-run-v0",
        "mode": "dry_run",
        "source_handler_report": str(source),
        "policy": {
            "path": str(POLICY),
            "policy_id": policy.get("policy_id"),
            "policy_driven": policy.get("policy_driven"),
            "examples_are_non_exhaustive": policy.get("examples_are_non_exhaustive"),
            "not_auto_repair": policy.get("not_auto_repair")
        },
        "registry_update_proposal": proposal,
        "safety": {
            "dry_run_only": True,
            "proposal_only": True,
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
    jp = REPORT_DIR / f"learning-v2-registry-update-proposal-dry-run-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-registry-update-proposal-dry-run-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Registry Update Proposal Dry-run\n\n"
        f"- proposal_status: `{proposal['proposal_status']}`\n"
        "- registry_write_allowed: `false`\n"
        "- mutation_allowed: `false`\n"
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
    source, handler_payload = load_handler_report(args)
    proposal = build_proposal(handler_payload, policy)
    jp, mp = write_report(source, proposal, policy)

    print("registry_update_proposal_dry_run = ok")
    print("proposal_status =", proposal["proposal_status"])
    print("next_safe_action =", proposal["next_safe_action"])
    print("registry_write_allowed = false")
    print("mutation_allowed = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
