#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
RESEARCH_DIR = BASE / "research"
REPORT_DIR = BASE / "reports"
RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PATTERNS = RESEARCH_DIR / "design-patterns.jsonl"
TEST_PATTERNS = RESEARCH_DIR / "design-patterns-test.jsonl"
CANDIDATES = RESEARCH_DIR / "target-family-candidates.jsonl"
TEST_CANDIDATES = RESEARCH_DIR / "target-family-candidates-test.jsonl"

BUILDER_ID = "learning-v2-research-target-family-candidate-builder-v0"

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

def candidate_from_pattern(pattern):
    family = pattern.get("suggested_target_family")
    topic = pattern.get("topic")
    risk = pattern.get("risk") or "medium"

    if family == "accessibility.navigation_button_semantics":
        recommended_stage = "accessibility_nav_button_probe"
        recommended_probe = "learning-v2-accessibility-nav-button-semantics-probe.py"
        rationale = "Pattern suggests explicit semantics for interactive navigation controls."
    elif family == "mobile_first.nav_density":
        recommended_stage = "mobile_nav_density_probe"
        recommended_probe = "learning-v2-mobile-nav-density-probe.py"
        rationale = "Pattern suggests observing mobile navigation density before source changes."
    else:
        recommended_stage = family.replace(".", "_") + "_probe"
        recommended_probe = f"learning-v2-{family.replace('.', '-')}-probe.py"
        rationale = "Pattern-derived observe-only target-family candidate."

    return {
        "candidate_id": f"candidate-{family}-{stamp()}",
        "target_family": family,
        "topic": topic,
        "source_pattern_id": pattern.get("pattern_id"),
        "source_digest_id": pattern.get("source_digest_id"),
        "principle": pattern.get("principle"),
        "evidence": pattern.get("evidence"),
        "applicability": pattern.get("applicability"),
        "risk": risk,
        "observe_only_first": True,
        "requires_new_probe": True,
        "requires_selector_route": True,
        "requires_dispatch_route": True,
        "recommended_stage": recommended_stage,
        "recommended_probe_script": recommended_probe,
        "rationale": rationale,
        "source_changes_allowed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "status": "candidate_only",
        "built_at": now_iso(),
        "builder_id": BUILDER_ID,
    }

def dedupe_candidates(candidates):
    seen = set()
    out = []
    for c in candidates:
        key = (c.get("target_family"), c.get("topic"))
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out

def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    mode = "test" if payload["test_mode"] else "real"
    out_json = REPORT_DIR / f"research-target-family-candidate-builder-{mode}-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-target-family-candidate-builder-{mode}-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Target-Family Candidate Builder v0")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- builder_id: `{BUILDER_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- test_mode: `{str(payload['test_mode']).lower()}`")
    lines.append(f"- input_pattern_count: `{payload['input_pattern_count']}`")
    lines.append(f"- candidate_count: `{payload['candidate_count']}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Candidate preview")
    lines.append("")
    for c in payload["candidates_preview"]:
        lines.append(f"### `{c.get('candidate_id')}`")
        lines.append("")
        lines.append(f"- target_family: `{c.get('target_family')}`")
        lines.append(f"- topic: `{c.get('topic')}`")
        lines.append(f"- recommended_stage: `{c.get('recommended_stage')}`")
        lines.append(f"- recommended_probe_script: `{c.get('recommended_probe_script')}`")
        lines.append(f"- risk: `{c.get('risk')}`")
        lines.append(f"- observe_only_first: `{str(c.get('observe_only_first')).lower()}`")
        lines.append(f"- principle: {c.get('principle')}")
        lines.append(f"- rationale: {c.get('rationale')}")
        lines.append("")
    lines.append("## Guardrails")
    lines.append("")
    for k, v in payload["guardrails"].items():
        lines.append(f"- `{k}` = `{str(v).lower()}`")
    lines.append("")

    if payload["failures"]:
        lines.append("## Failures")
        lines.append("")
        for f in payload["failures"]:
            lines.append(f"- {f}")
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")
    return out_json, out_md

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-mode", action="store_true", help="read design-patterns-test.jsonl and write target-family-candidates-test.jsonl when --apply is used")
    ap.add_argument("--apply", action="store_true", help="append candidates to target-family-candidates.jsonl or target-family-candidates-test.jsonl")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    pattern_path = TEST_PATTERNS if args.test_mode else PATTERNS
    target_path = TEST_CANDIDATES if args.test_mode else CANDIDATES
    patterns = load_jsonl(pattern_path)
    candidates = dedupe_candidates([candidate_from_pattern(p) for p in patterns])

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

    if not patterns:
        failures.append(f"missing_patterns:{pattern_path}")

    if patterns and not candidates:
        failures.append("no_target_family_candidates_built")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "builder_id": BUILDER_ID,
        "result": result,
        "apply": args.apply,
        "test_mode": args.test_mode,
        "pattern_path": str(pattern_path),
        "target_path": str(target_path),
        "input_pattern_count": len(patterns),
        "candidate_count": len(candidates),
        "candidates_preview": candidates[:8],
        "guardrails": {
            "do_not_write_state": True,
            "do_not_modify_website_source": True,
            "do_not_commit": True,
            "do_not_push": True,
            "do_not_deploy": True,
            "candidates_are_not_selector_routes": True,
            "candidate_must_get_probe_design_before_activation": True,
            "dispatch_dry_run_required_before_cycle_start": True,
        },
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
        "failures": failures,
    }

    report_json, report_md = write_report(payload, args.apply)

    print("research_target_family_candidate_builder =", result)
    print("builder_id =", BUILDER_ID)
    print("test_mode =", str(args.test_mode).lower())
    print("pattern_path =", pattern_path)
    print("target_path =", target_path)
    print("input_pattern_count =", len(patterns))
    print("candidate_count =", len(candidates))
    print("report_json =", report_json)
    print("report_md =", report_md)
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

    if not args.apply:
        print("candidates_written = false")
        return 0

    with target_path.open("a", encoding="utf-8") as f:
        for c in candidates:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print("candidates_written = true")
    print("candidates_path =", target_path)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
