#!/usr/bin/env python3
import argparse, json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
CONTRACT = WORKSPACE / "projects" / "BLXST-failure-context-contract.json"
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

def simulation_payload(name):
    base_safety = {
        "planning_only": True,
        "website_source_written": False,
        "d1_written": False,
        "r2_written": False,
        "kv_written": False,
        "worker_changed": False,
        "cloudflare_mutation": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "mutation_allowed_by_planner": False
    }
    if name == "unknown_resource":
        return {"plan_status":"registry_update_or_review_required","authorized_context":True,"recommended_gate_families":["registry_update_gate","review_required_gate"],"warnings":["unknown_or_new_resource_requires_registry_update"],"safety":base_safety}
    if name == "no_auth":
        return {"plan_status":"analysis_or_clarification_only","authorized_context":False,"recommended_gate_families":["review_required_gate"],"warnings":["authorized_context_missing_mutation_blocked"],"safety":base_safety}
    if name == "hard_failure":
        return {"autonomous_path_rehearsal":"blocked","hard_failures":["example_step:unexpected_plan_status"],"warnings":[],"safety":{**base_safety, "state_written": False}}
    if name == "unexpected_status":
        return {"plan_status":"future_status_not_known_to_current_resolver","authorized_context":True,"recommended_gate_families":[],"warnings":["future_status_probe"],"safety":base_safety}
    return {"plan_status":"gate_plan_ready_for_next_dry_run","authorized_context":True,"recommended_gate_families":["resource_classifier_gate"],"warnings":[],"safety":base_safety}

def unsafe_flags(payload):
    safety = payload.get("safety") or {}
    bad = []
    for key in ["website_source_written","d1_written","r2_written","kv_written","worker_changed","cloudflare_mutation","git_commit","git_push","deploy"]:
        if safety.get(key) is not False:
            bad.append(f"{key}:{safety.get(key)}")
    return bad

def resolve(payload):
    contract = load_json(CONTRACT)
    hard_failures = list(payload.get("hard_failures") or [])
    warnings = list(payload.get("warnings") or [])
    plan_status = payload.get("plan_status")
    rehearsal_status = payload.get("autonomous_path_rehearsal")
    authorized = payload.get("authorized_context")
    gates = set(payload.get("recommended_gate_families") or [])
    bad_flags = unsafe_flags(payload)

    reasons = []
    actions = []

    known_continue = {"gate_plan_ready_for_next_dry_run"}
    known_review = {"analysis_or_clarification_only"}
    known_registry = {"registry_update_or_review_required"}

    if bad_flags:
        status = "safe_stop_failure_triage_required"
        reasons += ["unsafe_mutation_flags_present"] + bad_flags
        actions += ["fix_failed_step","do_not_mutate"]
    elif hard_failures or rehearsal_status == "blocked":
        status = "safe_stop_failure_triage_required"
        reasons += hard_failures or ["rehearsal_blocked"]
        actions += ["fix_failed_step","rerun_gate_plan","do_not_mutate"]
    elif authorized is False:
        status = "safe_stop_authorization_required"
        reasons += ["authorized_context_missing"]
        actions += ["request_authorized_context","do_not_mutate"]
    elif plan_status in known_registry or "registry_update_gate" in gates:
        status = "safe_stop_registry_update_required"
        reasons += ["registry_or_routing_update_required"]
        actions += ["update_resource_registry","run_review_gate","rerun_classifier","rerun_gate_plan","do_not_mutate"]
    elif plan_status in known_review or "review_required_gate" in gates:
        status = "safe_stop_review_required"
        reasons += ["review_or_clarification_required"]
        actions += ["run_review_gate","rerun_gate_plan","do_not_mutate"]
    elif plan_status in known_continue:
        status = "continue_allowed_next_dry_run"
        reasons += ["planning_report_clean"]
        actions += ["rerun_gate_plan"]
    else:
        status = "safe_stop_failure_triage_required"
        reasons += ["unknown_or_future_status:" + str(plan_status)]
        actions += ["triage_unknown_state","run_review_gate","do_not_mutate"]

    return {
        "resolved_status": status,
        "continue_allowed": status == "continue_allowed_next_dry_run",
        "mutation_allowed": False,
        "safe_stop": status != "continue_allowed_next_dry_run",
        "reasons": sorted(set(reasons)),
        "next_action_families": sorted(set(actions)),
        "warnings": sorted(set(warnings)),
        "contract_id": contract.get("contract_id"),
        "policy_driven": contract.get("policy_driven"),
        "examples_are_non_exhaustive": contract.get("examples_are_non_exhaustive"),
        "not_auto_repair": contract.get("not_auto_repair")
    }

def write_report(source, payload, resolution):
    ts = stamp()
    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-failure-context-resolver-v0",
        "mode": "dry_run",
        "source": source,
        "resolution": resolution,
        "safety": {
            "diagnostic_only": True,
            "state_written": False,
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
    jp = REPORT_DIR / f"learning-v2-failure-context-resolver-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-failure-context-resolver-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Failure Context Resolver\n\n"
        f"- status: `{resolution['resolved_status']}`\n"
        f"- continue_allowed: `{str(resolution['continue_allowed']).lower()}`\n"
        "- mutation_allowed: `false`\n"
        f"- next_actions: `{', '.join(resolution['next_action_families'])}`\n"
        "- deploy: `false`\n",
        encoding="utf-8"
    )
    return jp, mp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-report")
    ap.add_argument("--latest", choices=["gate_plan", "rehearsal"])
    ap.add_argument("--simulate", choices=["ok","unknown_resource","no_auth","hard_failure","unexpected_status"])
    args = ap.parse_args()

    if args.simulate:
        source = "simulation:" + args.simulate
        payload = simulation_payload(args.simulate)
    elif args.input_report:
        source = args.input_report
        payload = load_json(args.input_report)
    else:
        pattern = "learning-v2-autonomous-path-rehearsal-*.json" if args.latest == "rehearsal" else "learning-v2-gate-plan-dry-run-*.json"
        p = latest(pattern)
        if not p:
            raise SystemExit("BLOCKED: no report found for pattern " + pattern)
        source = str(p)
        payload = load_json(p)

    resolution = resolve(payload)
    jp, mp = write_report(source, payload, resolution)

    print("failure_context_resolver = ok")
    print("resolved_status =", resolution["resolved_status"])
    print("continue_allowed =", str(resolution["continue_allowed"]).lower())
    print("mutation_allowed = false")
    print("safe_stop =", str(resolution["safe_stop"]).lower())
    print("next_action_families =", ",".join(resolution["next_action_families"]))
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
