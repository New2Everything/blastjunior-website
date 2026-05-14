#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

PACKET_ID = "learning-v2-human-design-review-packet-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def latest_json(pattern):
    files = sorted(REPORT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None, {}
    p = files[0]
    try:
        return p, json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return p, {"__load_error__": str(e)}

def policy_value(payload, key):
    return (payload.get("policy") or {}).get(key)

def main():
    failures = []
    warnings = []

    proposal_path, proposal = latest_json("opportunity-proposal-*.json")
    validation_path, validation = latest_json("opportunity-validation-gate-*.json")
    plan_path, plan = latest_json("opportunity-controlled-change-plan-*.json")
    readiness_path, readiness = latest_json("learning-v2-design-review-implementation-readiness-*.json")
    next_action_path, next_action = latest_json("learning-v2-next-action-*.json")
    sequence_path, sequence = latest_json("learning-v2-lifecycle-sequence-verifier-*.json")

    required = {
        "proposal": (proposal_path, proposal),
        "validation": (validation_path, validation),
        "controlled_change_plan": (plan_path, plan),
        "readiness": (readiness_path, readiness),
        "next_action": (next_action_path, next_action),
        "sequence": (sequence_path, sequence),
    }

    for name, (path, payload) in required.items():
        if not path:
            failures.append(f"missing_report:{name}")
        if payload.get("__load_error__"):
            failures.append(f"{name}_load_error:{payload.get('__load_error__')}")

    target_family_values = [
        proposal.get("target_family"),
        validation.get("target_family"),
        plan.get("target_family"),
        readiness.get("target_family"),
        next_action.get("target_family"),
        sequence.get("target_family"),
    ]
    unique_targets = sorted(set(x for x in target_family_values if x))
    target_family = unique_targets[0] if len(unique_targets) == 1 else None

    if len(unique_targets) != 1:
        failures.append(f"target_family_mismatch:{target_family_values}")

    if proposal.get("result") != "built":
        failures.append(f"proposal_result_not_built:{proposal.get('result')}")
    if validation.get("result") != "ok":
        failures.append(f"validation_result_not_ok:{validation.get('result')}")
    if plan.get("result") != "ok":
        failures.append(f"controlled_plan_result_not_ok:{plan.get('result')}")
    if readiness.get("result") != "ok":
        failures.append(f"readiness_result_not_ok:{readiness.get('result')}")
    if next_action.get("result") != "ok":
        failures.append(f"next_action_result_not_ok:{next_action.get('result')}")
    if sequence.get("result") != "ok":
        failures.append(f"sequence_result_not_ok:{sequence.get('result')}")

    if readiness.get("readiness_decision") != "design_review_ready_implementation_not_opened":
        failures.append(f"readiness_decision_unexpected:{readiness.get('readiness_decision')}")
    if readiness.get("next_safe_action") != "prepare_human_design_review_packet":
        failures.append(f"readiness_next_safe_action_unexpected:{readiness.get('next_safe_action')}")

    for name, payload in [
        ("proposal", proposal),
        ("validation", validation),
        ("controlled_change_plan", plan),
        ("readiness", readiness),
        ("next_action", next_action),
        ("sequence", sequence),
    ]:
        for key in ["website_files_changed", "git_commit", "git_push", "deploy"]:
            if policy_value(payload, key) is not False:
                failures.append(f"{name}_policy_{key}_not_false:{policy_value(payload, key)}")

    if policy_value(readiness, "implementation_gate_opened") is not False:
        failures.append(f"implementation_gate_opened_not_false:{policy_value(readiness, 'implementation_gate_opened')}")
    if policy_value(readiness, "source_change_gate_opened") is not False:
        failures.append(f"source_change_gate_opened_not_false:{policy_value(readiness, 'source_change_gate_opened')}")

    proposal_obj = proposal.get("proposal") if isinstance(proposal.get("proposal"), dict) else {}
    proposal_id = proposal.get("proposal_id") or proposal_obj.get("proposal_id") or proposal_obj.get("id")
    preferred_option = proposal.get("preferred_option") or proposal_obj.get("preferred_option") or proposal_obj.get("preferred_design_option")
    files_to_change = proposal.get("files_to_change") or proposal_obj.get("files_to_change") or []

    if not proposal_id:
        failures.append("proposal_id_missing")
    if not preferred_option:
        failures.append("preferred_option_missing")

    result = "ok" if not failures else "blocked"

    checklist = [
        "Human confirms event.storytelling_path is strategically worth implementing.",
        "Human confirms proposed storytelling path matches HADO / BLXST positioning.",
        "Human confirms no website source change should happen before separate implementation gate.",
        "Human confirms implementation should remain blocked unless source-change gate opens later.",
        "Human confirms deployment remains blocked.",
    ]

    payload = {
        "generated_at": now_iso(),
        "packet_id": PACKET_ID,
        "result": result,
        "target_family": target_family,
        "proposal": {
            "report": str(proposal_path) if proposal_path else None,
            "proposal_id": proposal_id,
            "preferred_option": preferred_option,
            "recommended_next_stage": proposal.get("recommended_next_stage"),
            "files_to_change": files_to_change,
        },
        "validation": {
            "report": str(validation_path) if validation_path else None,
            "result": validation.get("result"),
            "recommended_next_stage": validation.get("recommended_next_stage"),
        },
        "controlled_change_plan": {
            "report": str(plan_path) if plan_path else None,
            "result": plan.get("result"),
            "change_type": (plan.get("plan") or {}).get("change_type"),
            "target_file": (plan.get("plan") or {}).get("target_file"),
            "recommended_next_stage": plan.get("recommended_next_stage"),
        },
        "readiness": {
            "report": str(readiness_path) if readiness_path else None,
            "result": readiness.get("result"),
            "readiness_decision": readiness.get("readiness_decision"),
            "next_safe_action": readiness.get("next_safe_action"),
            "human_message": readiness.get("human_message"),
        },
        "gates": {
            "implementation_gate_opened": False,
            "source_change_gate_opened": False,
            "deploy_gate_opened": False,
            "human_review_required": True,
        },
        "human_review_checklist": checklist,
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "dry_run_only": True,
            "website_files_changed": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
            "implementation_gate_opened": False,
            "source_change_gate_opened": False,
        },
    }

    out_json = REPORT_DIR / f"learning-v2-human-design-review-packet-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-human-design-review-packet-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Human Design Review Packet",
        "",
        f"- result: `{result}`",
        f"- target_family: `{target_family}`",
        f"- proposal_id: `{payload['proposal']['proposal_id']}`",
        f"- preferred_option: `{payload['proposal']['preferred_option']}`",
        f"- readiness_decision: `{payload['readiness']['readiness_decision']}`",
        f"- next_safe_action: `{payload['readiness']['next_safe_action']}`",
        f"- implementation_gate_opened: `False`",
        f"- source_change_gate_opened: `False`",
        f"- deploy: `False`",
        "",
        "## Human Review Checklist",
    ]
    lines += [f"- [ ] {x}" for x in checklist]
    lines += ["", "## Failures"]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    lines += ["", "## Warnings"]
    lines += [f"- {x}" for x in warnings] if warnings else ["- none"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("human_design_review_packet =", result)
    print("target_family =", target_family)
    print("proposal_id =", payload["proposal"]["proposal_id"])
    print("preferred_option =", payload["proposal"]["preferred_option"])
    print("readiness_decision =", payload["readiness"]["readiness_decision"])
    print("next_safe_action =", payload["readiness"]["next_safe_action"])
    print("implementation_gate_opened = false")
    print("source_change_gate_opened = false")
    print("failure_count =", len(failures))
    print("warning_count =", len(warnings))
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("website_files_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if failures:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
