#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
OUTCOMES = BASE / "outcomes.jsonl"
PATTERNS = BASE / "patterns.jsonl"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

CHECKER_ID = "learning-v2-design-loop-contract-checker-v0"

STAGES = [
    "learn_observe",
    "design_opportunity",
    "evidence_packet",
    "design_hypothesis",
    "proposal",
    "validation_gate",
    "controlled_change_plan",
    "controlled_apply",
    "post_apply_validation",
    "outcome_recording",
    "track_completion",
]

OPPORTUNITY_TYPES = [
    "bug_fix",
    "experience_friction",
    "missing_capability",
]

REPORT_PATTERNS = {
    "learn_observe": [
        "research-*.json",
        "research-*.md",
        "*research*.json",
        "*research*.md",
        "*state-check*.md",
    ],
    "design_opportunity": [
        "*probe-design*.json",
        "*family-design*.json",
        "*target*.json",
        "*selector*.json",
    ],
    "evidence_packet": [
        "*probe*.json",
        "*audit*.json",
        "*state-check*.md",
        "*research*.json",
    ],
    "design_hypothesis": [
        "*probe-design*.json",
        "*family-design*.json",
        "*design*.json",
        "*design*.md",
    ],
    "proposal": [
        "*proposal*.json",
        "*proposal*.md",
        "*proposal-planner*.json",
        "*proposal-finalizer*.md",
    ],
    "validation_gate": [
        "*validator*.json",
        "*validation*.json",
        "*policy-gate*.json",
        "*gate-readiness*.json",
    ],
    "controlled_change_plan": [
        "*controlled-source-change-plan*.json",
        "*source-change-dry-run*.json",
        "*dry-run*.json",
        "*dry-run*.diff",
    ],
    "controlled_apply": [
        "*apply-apply*.json",
        "*source-change-apply-apply*.json",
        "*controlled-change*apply*.json",
    ],
    "post_apply_validation": [
        "*post-apply-validator*.json",
        "*isolated-post-apply-validator*.json",
        "*validator*.json",
    ],
    "outcome_recording": [
        "*outcome*.json",
        "*track-complete*.json",
        "*closure*.json",
    ],
    "track_completion": [
        "*track-complete*.json",
        "*closure*.json",
        "*closed*.md",
        "*complete*.md",
    ],
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def count_jsonl(path):
    if not path.exists():
        return 0
    return len([line for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()])

def latest_files(patterns, limit=5):
    files = []
    for pattern in patterns:
        files.extend(REPORT_DIR.glob(pattern))
        files.extend(SNAPSHOT_DIR.glob(pattern))
    unique = sorted(set(files), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return [str(p) for p in unique[:limit]]

def infer_active_loop(state):
    return {
        "current_mode": state.get("current_mode"),
        "current_topic": state.get("current_topic"),
        "current_stage": state.get("current_stage"),
        "current_target_family": state.get("current_target_family"),
        "has_active_loop": bool(
            state.get("current_topic")
            or state.get("current_stage")
            or state.get("current_target_family")
        ),
    }

def classify_stage_status(stage, state, active_loop):
    files = latest_files(REPORT_PATTERNS.get(stage, []), limit=5)
    status = "missing"
    reason = "no matching artifact found"

    if files:
        status = "available"
        reason = "matching artifact exists"

    # A few state-derived checks.
    if stage == "design_opportunity":
        if active_loop["current_target_family"]:
            status = "active"
            reason = "current_target_family is set in state"
    elif stage == "track_completion":
        applied = state.get("applied_targets") or []
        if applied:
            status = "available"
            reason = "applied_targets exists in state"
    elif stage == "outcome_recording":
        if count_jsonl(OUTCOMES) > 0:
            status = "available"
            reason = "outcomes.jsonl has records"
    elif stage == "learn_observe":
        if count_jsonl(PATTERNS) > 0:
            status = "available"
            reason = "patterns.jsonl has records"

    return {
        "stage": stage,
        "status": status,
        "reason": reason,
        "sample_artifacts": files,
    }

def recommend_next_stage(stage_results, active_loop):
    missing = [x for x in stage_results if x["status"] == "missing"]

    if not active_loop["has_active_loop"]:
        return {
            "next_stage": "design_opportunity",
            "recommendation": (
                "No active loop is selected. Start by discovering or selecting one design opportunity. "
                "Prefer missing_capability when no obvious bug exists."
            ),
            "allowed_action": "dry_run_only",
        }

    if missing:
        first = missing[0]["stage"]
        return {
            "next_stage": first,
            "recommendation": f"Active loop exists, but required artifact is missing for stage: {first}.",
            "allowed_action": "dry_run_only",
        }

    return {
        "next_stage": "track_completion_or_next_loop",
        "recommendation": "All v0 contract stages have at least one artifact. Consider closing current loop or selecting next opportunity.",
        "allowed_action": "dry_run_only",
    }

def main():
    state = load_json(STATE, default={}) or {}
    active_loop = infer_active_loop(state)

    stage_results = [
        classify_stage_status(stage, state, active_loop)
        for stage in STAGES
    ]

    applied_targets = state.get("applied_targets") or []
    disabled_target_families = state.get("disabled_target_families") or []

    missing_stages = [x["stage"] for x in stage_results if x["status"] == "missing"]
    available_stages = [x["stage"] for x in stage_results if x["status"] != "missing"]

    recommendation = recommend_next_stage(stage_results, active_loop)

    result = "needs_next_loop_selection" if not active_loop["has_active_loop"] else (
        "incomplete" if missing_stages else "complete"
    )

    payload = {
        "generated_at": now_iso(),
        "checker_id": CHECKER_ID,
        "result": result,
        "objective": "self_learning_self_evolving_website_design_system",
        "not_a_maintenance_only_system": True,
        "opportunity_types": OPPORTUNITY_TYPES,
        "active_loop": active_loop,
        "applied_targets_count": len(applied_targets),
        "disabled_target_families_count": len(disabled_target_families),
        "outcomes_count": count_jsonl(OUTCOMES),
        "patterns_count": count_jsonl(PATTERNS),
        "stage_results": stage_results,
        "missing_stages": missing_stages,
        "available_stages": available_stages,
        "recommendation": recommendation,
        "policy": {
            "dry_run_only": True,
            "website_files_changed": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
        },
    }

    out_json = REPORT_DIR / f"design-loop-contract-check-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"design-loop-contract-check-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Design Loop Contract Check",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- checker_id: `{CHECKER_ID}`",
        f"- result: `{result}`",
        f"- objective: `{payload['objective']}`",
        f"- active_loop: `{str(active_loop['has_active_loop']).lower()}`",
        f"- current_topic: `{active_loop['current_topic']}`",
        f"- current_stage: `{active_loop['current_stage']}`",
        f"- current_target_family: `{active_loop['current_target_family']}`",
        f"- applied_targets_count: `{payload['applied_targets_count']}`",
        f"- disabled_target_families_count: `{payload['disabled_target_families_count']}`",
        f"- outcomes_count: `{payload['outcomes_count']}`",
        f"- patterns_count: `{payload['patterns_count']}`",
        "",
        "## Opportunity Types",
        "",
    ]

    for t in OPPORTUNITY_TYPES:
        lines.append(f"- `{t}`")

    lines += [
        "",
        "## Stage Results",
        "",
    ]

    for item in stage_results:
        lines.append(f"- `{item['stage']}`: `{item['status']}` — {item['reason']}")
        for art in item["sample_artifacts"][:3]:
            lines.append(f"  - {art}")

    lines += [
        "",
        "## Missing Stages",
        "",
    ]

    if missing_stages:
        for stage in missing_stages:
            lines.append(f"- `{stage}`")
    else:
        lines.append("- none")

    lines += [
        "",
        "## Recommendation",
        "",
        f"- next_stage: `{recommendation['next_stage']}`",
        f"- allowed_action: `{recommendation['allowed_action']}`",
        "",
        recommendation["recommendation"],
        "",
        "## Safety",
        "",
        "- website_files_changed: `false`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
        "- restore_cloudflare_auto_deploy: `false`",
        "",
    ]

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("design_loop_contract_check =", result)
    print("active_loop =", str(active_loop["has_active_loop"]).lower())
    print("current_topic =", active_loop["current_topic"])
    print("current_stage =", active_loop["current_stage"])
    print("current_target_family =", active_loop["current_target_family"])
    print("missing_stages =", json.dumps(missing_stages, ensure_ascii=False))
    print("next_stage =", recommendation["next_stage"])
    print("allowed_action =", recommendation["allowed_action"])
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
