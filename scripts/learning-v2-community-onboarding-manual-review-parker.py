#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FAMILY = "community.onboarding_experience"
PARKER_ID = "learning-v2-community-onboarding-autonomous-policy-review-parker-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def latest_report(pattern):
    files = sorted(REPORT_DIR.glob(pattern))
    if not files:
        return None, {}
    p = files[-1]
    return p, load_json(p, default={})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="park autonomous-policy-review item and return system to idle; never modifies website source")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    plan_path, plan = latest_report("community-onboarding-controlled-source-change-plan-*.json")
    proposal_path, proposal = latest_report("community-onboarding-proposal-planner-*.json")

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("current_topic") != "community-experience":
        failures.append(f"current_topic_not_community_experience:{state.get('current_topic')}")

    if state.get("current_stage") != "community_onboarding_autonomous_policy_required":
        failures.append(f"current_stage_not_autonomous_policy_review_required:{state.get('current_stage')}")

    if state.get("current_target_family") != TARGET_FAMILY:
        failures.append(f"target_family_mismatch:{state.get('current_target_family')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if not plan_path:
        failures.append("missing_community_onboarding_controlled_plan_report")

    if plan.get("result") != "ok":
        failures.append(f"controlled_plan_not_ok:{plan.get('result')}")

    policy_item = {
        "at": now_iso(),
        "item_id": f"autonomous-policy-review-{TARGET_FAMILY}-{stamp()}",
        "target_family": TARGET_FAMILY,
        "topic": "community-experience",
        "stage_before": "community_onboarding_autonomous_policy_required",
        "status": "pending_autonomous_policy_review",
        "reason": "controlled source change plan requires autonomous policy review before source_change_gate can open",
        "plan_report": str(plan_path) if plan_path else None,
        "proposal_report": str(proposal_path) if proposal_path else None,
        "recommended_next_step": plan.get("recommended_next_step"),
        "source_change_allowed_now": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "parker_id": PARKER_ID,
        "result": result,
        "target_family": TARGET_FAMILY,
        "autonomous_policy_review_item": policy_item,
        "stage_after": "idle",
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "source_change_gate_opened": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "autonomous_policy_review_parking_only": True,
        },
        "failures": failures,
    }

    suffix = "apply" if args.apply else "dry-run"
    out_json = REPORT_DIR / f"community-onboarding-autonomous-policy-review-parker-{suffix}-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"community-onboarding-autonomous-policy-review-parker-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Community Onboarding Manual Review Parker",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- parker_id: `{PARKER_ID}`",
        f"- mode: `{'apply' if args.apply else 'dry-run'}`",
        f"- result: `{result}`",
        f"- target_family: `{TARGET_FAMILY}`",
        f"- stage_after: `{payload['stage_after']}`",
        f"- plan_report: `{policy_item['plan_report']}`",
        f"- proposal_report: `{policy_item['proposal_report']}`",
        "- source_change_gate_opened: `false`",
        f"- state_written: `{'true' if args.apply and result == 'ok' else 'false'}`",
        "- business_source_written: `false`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
        "",
        "## Manual review item",
        "",
        "```json",
        json.dumps(policy_item, ensure_ascii=False, indent=2),
        "```",
    ]

    if failures:
        lines += ["", "## Failures"]
        lines += [f"- {x}" for x in failures]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("community_onboarding_autonomous_policy_review_parker =", result)
    print("mode =", "apply" if args.apply else "dry_run")
    print("target_family =", TARGET_FAMILY)
    print("policy_item_id =", policy_item["item_id"])
    print("plan_report =", policy_item["plan_report"])
    print("proposal_report =", policy_item["proposal_report"])
    print("would_set_stage = idle")
    print("source_change_gate_opened = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("report_json =", out_json)
    print("report_md =", out_md)

    if failures:
        print("state_written = false")
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    if not args.apply:
        print("state_written = false")
        print("state_updated = false")
        return 0

    state.setdefault("autonomous_policy_review_items", [])
    existing = {
        x.get("target_family")
        for x in state["autonomous_policy_review_items"]
        if isinstance(x, dict) and x.get("status") == "pending_autonomous_policy_review"
    }
    if TARGET_FAMILY not in existing:
        state["autonomous_policy_review_items"].append(policy_item)

    state.setdefault("disabled_target_families", [])
    if TARGET_FAMILY not in state["disabled_target_families"]:
        state["disabled_target_families"].append(TARGET_FAMILY)

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "community_onboarding_autonomous_policy_review_parker",
        "stage_before": "community_onboarding_autonomous_policy_required",
        "stage_after": "idle",
        "target_family": TARGET_FAMILY,
        "policy_item_id": policy_item["item_id"],
        "plan_report": policy_item["plan_report"],
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    })

    state["last_community_onboarding_autonomous_policy_review_parker"] = {
        "at": now_iso(),
        "result": "idle",
        "target_family": TARGET_FAMILY,
        "policy_item_id": policy_item["item_id"],
        "plan_report": policy_item["plan_report"],
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }

    state["current_topic"] = None
    state["current_stage"] = None
    state["current_target_family"] = None
    state["next_action"] = "Manual-review item parked. Run selector to continue autonomous learning with a new target."
    state["updated_at"] = now_iso()

    save_json(STATE, state)

    print("state_written = true")
    print("state_updated = true")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
