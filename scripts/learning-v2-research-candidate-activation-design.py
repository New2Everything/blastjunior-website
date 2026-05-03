#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
RESEARCH_DIR = BASE / "research"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TEST_CANDIDATES = RESEARCH_DIR / "target-family-candidates-test.jsonl"
REAL_CANDIDATES = RESEARCH_DIR / "target-family-candidates.jsonl"

DESIGN_ID = "learning-v2-research-candidate-activation-design-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def load_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows

def build_activation_plan(candidate):
    target_family = candidate.get("target_family")
    topic = candidate.get("topic")
    stage = candidate.get("recommended_stage")
    probe_script = candidate.get("recommended_probe_script")

    return {
        "target_family": target_family,
        "topic": topic,
        "activation_status": "design_only",
        "recommended_stage": stage,
        "recommended_probe_script": probe_script,
        "source_candidate_id": candidate.get("candidate_id"),
        "source_pattern_principle": candidate.get("principle"),
        "risk": candidate.get("risk"),
        "observe_only_first": True,
        "required_scripts": [
            {
                "script": f"scripts/{probe_script}",
                "purpose": "Read-only probe for the candidate target-family.",
                "must_default_dry_run": True,
                "writes_state": False,
                "writes_business_source": False,
            },
            {
                "script": "scripts/learning-v2-topic-selector.py",
                "purpose": "Later add selector awareness only after probe exists and passes dry-run.",
                "must_default_dry_run": True,
                "writes_state_only_with_apply": True,
                "writes_business_source": False,
            },
            {
                "script": "scripts/learning-v2-dispatch.py",
                "purpose": "Later add dispatch route with target-family guard.",
                "must_default_dry_run": True,
                "writes_business_source": False,
                "source_write_risk": False,
            },
        ],
        "activation_sequence": [
            "design_probe_script",
            "probe_dry_run",
            "baseline_probe",
            "integrity_green",
            "selector_dry_run_route",
            "dispatch_sandbox_verification",
            "selector_apply_only_when_idle",
            "dispatch_apply_probe_only",
            "resolver_review_proposal_finalizer_chain",
            "track_complete_finalizer_to_idle",
        ],
        "hard_blocks": [
            "Do not activate directly from research candidate.",
            "Do not create apply_ready.",
            "Do not modify website source.",
            "Do not commit.",
            "Do not push.",
            "Do not deploy.",
            "Do not skip dispatch sandbox verification.",
        ],
    }

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    test_candidates = load_jsonl(TEST_CANDIDATES)
    real_candidates = load_jsonl(REAL_CANDIDATES)

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("current_topic") is not None:
        failures.append(f"current_topic_not_idle:{state.get('current_topic')}")

    if state.get("current_stage") is not None:
        failures.append(f"current_stage_not_idle:{state.get('current_stage')}")

    if state.get("current_target_family") is not None:
        failures.append(f"current_target_family_not_idle:{state.get('current_target_family')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if not test_candidates:
        failures.append("missing_test_target_family_candidates")

    if real_candidates:
        failures.append(f"real_target_family_candidates_not_empty:{len(real_candidates)}")

    plans = [build_activation_plan(c) for c in test_candidates]
    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "design_id": DESIGN_ID,
        "result": result,
        "failures": failures,
        "test_candidate_count": len(test_candidates),
        "real_candidate_count": len(real_candidates),
        "activation_plan_count": len(plans),
        "activation_plans": plans,
        "guardrails": {
            "design_only": True,
            "do_not_write_state": True,
            "do_not_modify_website_source": True,
            "do_not_commit": True,
            "do_not_push": True,
            "do_not_deploy": True,
            "candidate_activation_requires_probe_first": True,
            "selector_route_requires_probe_and_dispatch_sandbox": True,
        },
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
    }

    out_json = REPORT_DIR / f"research-candidate-activation-design-{stamp()}.json"
    out_md = REPORT_DIR / f"research-candidate-activation-design-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Research Candidate Activation Design")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- design_id: `{DESIGN_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- test_candidate_count: `{len(test_candidates)}`")
    lines.append(f"- real_candidate_count: `{len(real_candidates)}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Activation plans")
    lines.append("")

    for plan in plans:
        lines.append(f"### `{plan['target_family']}`")
        lines.append("")
        lines.append(f"- topic: `{plan['topic']}`")
        lines.append(f"- recommended_stage: `{plan['recommended_stage']}`")
        lines.append(f"- recommended_probe_script: `{plan['recommended_probe_script']}`")
        lines.append(f"- risk: `{plan['risk']}`")
        lines.append(f"- observe_only_first: `{str(plan['observe_only_first']).lower()}`")
        lines.append("")
        lines.append("Activation sequence:")
        for step in plan["activation_sequence"]:
            lines.append(f"- {step}")
        lines.append("")
        lines.append("Hard blocks:")
        for block in plan["hard_blocks"]:
            lines.append(f"- {block}")
        lines.append("")

    lines.append("## Guardrails")
    lines.append("")
    for k, v in payload["guardrails"].items():
        lines.append(f"- `{k}` = `{str(v).lower()}`")
    lines.append("")

    if failures:
        lines.append("## Failures")
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("research_candidate_activation_design =", result)
    print("design_id =", DESIGN_ID)
    print("design_json =", out_json)
    print("design_md =", out_md)
    print("test_candidate_count =", len(test_candidates))
    print("real_candidate_count =", len(real_candidates))
    print("activation_plan_count =", len(plans))

    for plan in plans:
        print()
        print("target_family =", plan["target_family"])
        print("topic =", plan["topic"])
        print("recommended_stage =", plan["recommended_stage"])
        print("recommended_probe_script =", plan["recommended_probe_script"])
        print("activation_status =", plan["activation_status"])

    print()
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
