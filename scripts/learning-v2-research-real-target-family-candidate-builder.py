#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
RESEARCH_DIR = BASE / "research"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PATTERNS = RESEARCH_DIR / "design-patterns.jsonl"
CANDIDATES = RESEARCH_DIR / "target-family-candidates.jsonl"

BUILDER_ID = "learning-v2-research-real-target-family-candidate-builder-v0"

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

def latest_guard_report():
    reports = sorted(REPORT_DIR.glob("research-candidate-novelty-guard-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def existing_candidate_families():
    rows = load_jsonl(CANDIDATES)
    return {
        r.get("target_family")
        for r in rows
        if r.get("target_family")
    }

def stage_for_family(target_family):
    mapping = {
        "community.onboarding_experience": {
            "recommended_stage": "community_onboarding_probe",
            "recommended_probe_script": "learning-v2-community-onboarding-experience-probe.py",
            "recommended_topic": "community-experience",
        },
        "community.engagement_path": {
            "recommended_stage": "community_engagement_path_probe",
            "recommended_probe_script": "learning-v2-community-engagement-path-probe.py",
            "recommended_topic": "community-experience",
        },
    }
    return mapping.get(target_family, {
        "recommended_stage": target_family.replace(".", "_") + "_probe",
        "recommended_probe_script": "learning-v2-" + target_family.replace(".", "-") + "-probe.py",
        "recommended_topic": "research-derived",
    })

def build_pattern_index():
    by_family = defaultdict(list)
    for p in load_jsonl(PATTERNS):
        family = p.get("suggested_target_family")
        if family:
            by_family[family].append(p)
    return by_family

def build_candidate(decision, patterns):
    target_family = decision.get("target_family")
    info = stage_for_family(target_family)

    source_query_ids = sorted({p.get("query_id") for p in patterns if p.get("query_id")})
    source_topics = sorted({p.get("topic") for p in patterns if p.get("topic")})
    principles = [p.get("principle") for p in patterns if p.get("principle")]

    return {
        "candidate_id": f"candidate-{target_family}-{stamp()}",
        "candidate_source_type": "real_research_novelty_guard",
        "target_family": target_family,
        "topic": info["recommended_topic"],
        "source_topics": source_topics,
        "source_query_ids": source_query_ids,
        "pattern_count": len(patterns),
        "principles": principles,
        "pattern_ids": [p.get("pattern_id") for p in patterns if p.get("pattern_id")],
        "source_titles": sorted({p.get("title") or p.get("source_title") for p in patterns if p.get("title") or p.get("source_title")}),
        "recommended_stage": info["recommended_stage"],
        "recommended_probe_script": info["recommended_probe_script"],
        "risk": "low",
        "observe_only_first": True,
        "activation_allowed_now": True,
        "activation_status": "candidate_ready_for_observe_only_probe_design",
        "novelty_guard_decision": decision.get("decision"),
        "novelty_guard_reason": decision.get("reason"),
        "next_step": "design_observe_only_probe",
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "created_at": now_iso(),
        "builder_id": BUILDER_ID,
    }

def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    out_json = REPORT_DIR / f"research-real-target-family-candidate-builder-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-real-target-family-candidate-builder-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Real Target-Family Candidate Builder")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- builder_id: `{BUILDER_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- guard_report: `{payload['guard_report']}`")
    lines.append(f"- eligible_decision_count: `{payload['eligible_decision_count']}`")
    lines.append(f"- fresh_candidate_count: `{payload['fresh_candidate_count']}`")
    lines.append(f"- duplicate_candidate_count: `{payload['duplicate_candidate_count']}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Candidate preview")
    lines.append("")
    for c in payload["candidates_preview"]:
        lines.append(f"### `{c.get('target_family')}`")
        lines.append("")
        lines.append(f"- candidate_id: `{c.get('candidate_id')}`")
        lines.append(f"- pattern_count: `{c.get('pattern_count')}`")
        lines.append(f"- recommended_stage: `{c.get('recommended_stage')}`")
        lines.append(f"- recommended_probe_script: `{c.get('recommended_probe_script')}`")
        lines.append(f"- observe_only_first: `{str(c.get('observe_only_first')).lower()}`")
        lines.append("")
        lines.append("Principles:")
        for p in c.get("principles") or []:
            lines.append(f"- {p}")
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
    ap.add_argument("--apply", action="store_true", help="append real target-family candidates")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    guard_path, guard = latest_guard_report()
    pattern_index = build_pattern_index()
    existing = existing_candidate_families()

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

    if not guard_path:
        failures.append("missing_novelty_guard_report")

    if guard.get("result") != "ok":
        failures.append(f"novelty_guard_not_ok:{guard.get('result')}")

    decisions = [
        d for d in guard.get("decisions", [])
        if d.get("decision") == "eligible_new_candidate"
        and d.get("activation_allowed") is True
    ]

    fresh = []
    duplicates = 0

    for d in decisions:
        family = d.get("target_family")
        if not family:
            failures.append("decision_missing_target_family")
            continue

        if family in existing:
            duplicates += 1
            continue

        patterns = pattern_index.get(family, [])
        if not patterns:
            failures.append(f"no_patterns_for_target_family:{family}")
            continue

        fresh.append(build_candidate(d, patterns))

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "builder_id": BUILDER_ID,
        "result": result,
        "apply": args.apply,
        "guard_report": str(guard_path) if guard_path else None,
        "eligible_decision_count": len(decisions),
        "fresh_candidate_count": len(fresh),
        "duplicate_candidate_count": duplicates,
        "candidates_preview": fresh[:10],
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "candidate_only": True,
        },
        "failures": failures,
    }

    report_json, report_md = write_report(payload, args.apply)

    print("research_real_target_family_candidate_builder =", result)
    print("builder_id =", BUILDER_ID)
    print("candidate_json =", report_json)
    print("candidate_md =", report_md)
    print("guard_report =", guard_path)
    print("eligible_decision_count =", len(decisions))
    print("fresh_candidate_count =", len(fresh))
    print("duplicate_candidate_count =", duplicates)
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if fresh:
        print()
        print("candidate_preview =")
        for c in fresh:
            print(f"- {c.get('target_family')} stage={c.get('recommended_stage')} probe={c.get('recommended_probe_script')} patterns={c.get('pattern_count')}")

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

    if not args.apply:
        print("real_target_family_candidates_written = false")
        return 0

    if not fresh:
        print("real_target_family_candidates_written = false")
        print("reason = no_fresh_candidates")
        return 0

    with CANDIDATES.open("a", encoding="utf-8") as f:
        for c in fresh:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print("real_target_family_candidates_written = true")
    print("target_family_candidates_path =", CANDIDATES)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
