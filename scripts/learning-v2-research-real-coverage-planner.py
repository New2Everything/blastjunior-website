#!/usr/bin/env python3
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

QUERIES = RESEARCH_DIR / "queries.jsonl"
SOURCE_PLANS = RESEARCH_DIR / "source-plans.jsonl"
SOURCES = RESEARCH_DIR / "sources.jsonl"
DIGESTS = RESEARCH_DIR / "digests.jsonl"
PATTERNS = RESEARCH_DIR / "design-patterns.jsonl"
CANDIDATES = RESEARCH_DIR / "target-family-candidates.jsonl"
EVIDENCE = RESEARCH_DIR / "evidence-reinforcements.jsonl"

PLANNER_ID = "learning-v2-research-real-coverage-planner-v0"

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

def by_key(rows, key):
    d = defaultdict(list)
    for r in rows:
        d[r.get(key)].append(r)
    return d

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    queries = load_jsonl(QUERIES)
    source_plans = load_jsonl(SOURCE_PLANS)
    sources = load_jsonl(SOURCES)
    digests = load_jsonl(DIGESTS)
    patterns = load_jsonl(PATTERNS)
    candidates = load_jsonl(CANDIDATES)
    evidence = load_jsonl(EVIDENCE)

    source_by_query = by_key(sources, "query_id")
    digest_by_query = by_key(digests, "query_id")
    pattern_by_query = by_key(patterns, "query_id")

    disabled = set(state.get("disabled_target_families") or [])
    track_status = state.get("track_status") or {}

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

    if not queries:
        failures.append("missing_queries")

    if not source_plans:
        failures.append("missing_source_plans")

    coverage = []

    for q in queries:
        qid = q.get("query_id")
        topic = q.get("topic")
        real_source_count = len(source_by_query.get(qid, []))
        digest_count = len(digest_by_query.get(qid, []))
        pattern_count = len(pattern_by_query.get(qid, []))

        families = sorted({
            p.get("suggested_target_family")
            for p in pattern_by_query.get(qid, [])
            if p.get("suggested_target_family")
        })

        disabled_family_hits = [f for f in families if f in disabled]
        active_candidate_families = sorted({
            c.get("target_family")
            for c in candidates
            if c.get("target_family")
        })

        if real_source_count == 0:
            status = "needs_real_source"
            priority = 1
            recommendation = "Collect at least one vetted real source for this query."
        elif digest_count == 0:
            status = "needs_digest"
            priority = 2
            recommendation = "Run real source digester."
        elif pattern_count == 0:
            status = "needs_pattern_extraction"
            priority = 3
            recommendation = "Run real pattern extractor."
        elif families and len(disabled_family_hits) == len(families):
            status = "covered_as_evidence_reinforcement"
            priority = 5
            recommendation = "Already reinforces completed/disabled target-family. Do not reactivate."
        elif families:
            status = "has_potential_candidate_family"
            priority = 4
            recommendation = "Run novelty guard and candidate builder carefully."
        else:
            status = "needs_pattern_review"
            priority = 4
            recommendation = "Patterns exist but no target-family was suggested."

        coverage.append({
            "query_id": qid,
            "topic": topic,
            "question": q.get("question") or q.get("query") or q.get("prompt"),
            "real_source_count": real_source_count,
            "digest_count": digest_count,
            "pattern_count": pattern_count,
            "suggested_target_families": families,
            "disabled_family_hits": disabled_family_hits,
            "active_candidate_families": active_candidate_families,
            "status": status,
            "priority": priority,
            "recommendation": recommendation,
        })

    coverage_sorted = sorted(coverage, key=lambda x: (x["priority"], x.get("query_id") or ""))

    next_collection = [
        c for c in coverage_sorted
        if c["status"] == "needs_real_source"
    ][:5]

    status_counts = defaultdict(int)
    for c in coverage:
        status_counts[c["status"]] += 1

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "planner_id": PLANNER_ID,
        "result": result,
        "failures": failures,
        "query_count": len(queries),
        "source_plan_count": len(source_plans),
        "sources_real_count": len(sources),
        "digests_real_count": len(digests),
        "patterns_real_count": len(patterns),
        "candidates_real_count": len(candidates),
        "evidence_reinforcements_count": len(evidence),
        "status_counts": dict(status_counts),
        "coverage": coverage_sorted,
        "next_collection": next_collection,
        "recommended_next_step": (
            "collect_real_sources_for_uncovered_queries"
            if next_collection else
            "run_candidate_builder_or_archive_reinforcement"
        ),
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "planner_only": True,
        },
    }

    out_json = REPORT_DIR / f"research-real-coverage-planner-{stamp()}.json"
    out_md = REPORT_DIR / f"research-real-coverage-planner-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Real Research Coverage Planner")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- planner_id: `{PLANNER_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- query_count: `{len(queries)}`")
    lines.append(f"- sources_real_count: `{len(sources)}`")
    lines.append(f"- digests_real_count: `{len(digests)}`")
    lines.append(f"- patterns_real_count: `{len(patterns)}`")
    lines.append(f"- candidates_real_count: `{len(candidates)}`")
    lines.append(f"- evidence_reinforcements_count: `{len(evidence)}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Status counts")
    lines.append("")
    for k, v in sorted(status_counts.items()):
        lines.append(f"- `{k}` = `{v}`")
    lines.append("")
    lines.append("## Next real source collection")
    lines.append("")
    if next_collection:
        for c in next_collection:
            lines.append(f"### `{c.get('query_id')}`")
            lines.append("")
            lines.append(f"- topic: `{c.get('topic')}`")
            lines.append(f"- status: `{c.get('status')}`")
            lines.append(f"- recommendation: {c.get('recommendation')}")
            if c.get("question"):
                lines.append(f"- question: {c.get('question')}")
            lines.append("")
    else:
        lines.append("- none")
        lines.append("")
    lines.append("## Full coverage")
    lines.append("")
    for c in coverage_sorted:
        lines.append(f"- `{c.get('query_id')}` topic=`{c.get('topic')}` status=`{c.get('status')}` sources=`{c.get('real_source_count')}` digests=`{c.get('digest_count')}` patterns=`{c.get('pattern_count')}` families=`{', '.join(c.get('suggested_target_families') or [])}`")
    lines.append("")

    if failures:
        lines.append("## Failures")
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("research_real_coverage_planner =", result)
    print("planner_id =", PLANNER_ID)
    print("coverage_json =", out_json)
    print("coverage_md =", out_md)
    print("query_count =", len(queries))
    print("sources_real_count =", len(sources))
    print("digests_real_count =", len(digests))
    print("patterns_real_count =", len(patterns))
    print("candidates_real_count =", len(candidates))
    print("evidence_reinforcements_count =", len(evidence))
    print("status_counts =", json.dumps(dict(status_counts), ensure_ascii=False))
    print("next_collection_count =", len(next_collection))
    print("recommended_next_step =", payload["recommended_next_step"])

    if next_collection:
        print()
        print("next_collection_preview =")
        for c in next_collection:
            print(f"- {c.get('query_id')} topic={c.get('topic')} status={c.get('status')}")

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
