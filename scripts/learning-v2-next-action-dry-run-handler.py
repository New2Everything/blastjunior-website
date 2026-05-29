#!/usr/bin/env python3
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
DISPATCHER = WORKSPACE / "scripts" / "learning-v2-autonomous-next-action-dispatcher.py"
POLICY = WORKSPACE / "projects" / "BLXST-next-action-handler-policy.json"
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

def run_dispatcher_simulation(name):
    p = subprocess.run(
        ["python3", str(DISPATCHER), "--simulate", name],
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
        raise RuntimeError("dispatcher_failed_or_report_missing\nSTDOUT:\n" + p.stdout + "\nSTDERR:\n" + p.stderr)
    return Path(report), load_json(report)

def load_dispatcher_report(args):
    if args.simulate:
        return run_dispatcher_simulation(args.simulate)
    if args.input_report:
        p = Path(args.input_report)
        return p, load_json(p)
    p = latest("learning-v2-autonomous-next-action-dispatcher-*.json")
    if not p:
        raise SystemExit("BLOCKED: no dispatcher report found")
    return p, load_json(p)

def handle(dispatch, policy):
    selected = dispatch.get("selected_next_action") or {}
    family = selected.get("family")
    handlers = policy.get("handler_families_non_exhaustive") or {}
    spec = handlers.get(family)

    warnings = []
    if not spec:
        family = "triage_unknown_state"
        spec = handlers.get(family, {
            "handler_result": "unknown_state_triage_report_created",
            "allowed_effect": "triage_report_only",
            "forbidden_effects": ["continue_execution", "auto_patch", "deploy"]
        })
        warnings.append("unknown_handler_family_defaulted_to_triage")

    result = spec.get("handler_result")
    allowed_effect = spec.get("allowed_effect")

    proposal = {
        "handler_family": family,
        "handler_result": result,
        "allowed_effect": allowed_effect,
        "forbidden_effects": spec.get("forbidden_effects") or [],
        "source_dispatcher_status": (dispatch.get("resolver_resolution") or {}).get("resolved_status"),
        "source_selected_action": selected,
        "proposal_only": True,
        "requires_later_rehearsal_for_mutation": True
    }

    if family == "update_resource_registry":
        proposal["proposal_summary"] = "Create a registry/routing-rule update proposal from unknown resource context; do not write registry yet."
        proposal["next_safe_command_family"] = "registry_update_proposal_dry_run"
    elif family == "run_review_gate":
        proposal["proposal_summary"] = "Create a review gate report; do not approve mutation."
        proposal["next_safe_command_family"] = "review_gate_dry_run"
    elif family == "request_authorized_context":
        proposal["proposal_summary"] = "Request /blxst or verify scheduled/autonomous/controlled-deploy context; do not assume authorization."
        proposal["next_safe_command_family"] = "authorization_context_request"
    elif family == "fix_failed_step":
        proposal["proposal_summary"] = "Create failure triage report from failed step; do not auto-patch."
        proposal["next_safe_command_family"] = "failure_triage_dry_run"
    elif family == "triage_unknown_state":
        proposal["proposal_summary"] = "Triage unknown/future state; do not continue execution."
        proposal["next_safe_command_family"] = "unknown_state_triage_dry_run"
    elif family == "rerun_classifier":
        proposal["proposal_summary"] = "Recommend classifier rerun; no mutation."
        proposal["next_safe_command_family"] = "classifier_rerun_dry_run"
    elif family == "rerun_gate_plan":
        proposal["proposal_summary"] = "Recommend gate plan rerun; no mutation."
        proposal["next_safe_command_family"] = "gate_plan_rerun_dry_run"
    else:
        proposal["proposal_summary"] = "Safety stop; do not mutate."
        proposal["next_safe_command_family"] = "safety_stop"

    return proposal, warnings

def write_report(source, dispatch, proposal, warnings):
    ts = stamp()
    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-next-action-dry-run-handler-v0",
        "mode": "dry_run",
        "source_dispatcher_report": str(source),
        "policy": {
            "path": str(POLICY),
            "policy_driven": True,
            "examples_are_non_exhaustive": True,
            "not_auto_repair": True
        },
        "handler_proposal": proposal,
        "warnings": sorted(set(warnings)),
        "safety": {
            "dry_run_only": True,
            "proposal_only": True,
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
    jp = REPORT_DIR / f"learning-v2-next-action-dry-run-handler-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-next-action-dry-run-handler-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Next-Action Dry-run Handler\n\n"
        f"- handler_family: `{proposal['handler_family']}`\n"
        f"- handler_result: `{proposal['handler_result']}`\n"
        "- proposal_only: `true`\n"
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
    source, dispatch = load_dispatcher_report(args)
    proposal, warnings = handle(dispatch, policy)
    jp, mp = write_report(source, dispatch, proposal, warnings)

    print("next_action_dry_run_handler = ok")
    print("handler_family =", proposal["handler_family"])
    print("handler_result =", proposal["handler_result"])
    print("proposal_only = true")
    print("execution_allowed = false")
    print("mutation_allowed = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
