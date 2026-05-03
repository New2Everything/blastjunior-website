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

DIGESTS = RESEARCH_DIR / "digests.jsonl"
PATTERNS = RESEARCH_DIR / "design-patterns.jsonl"

PLANNER_ID = "learning-v2-research-real-digest-pattern-gap-planner-v0"

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

def digest_identity(d):
    return {
        "digest_id": d.get("digest_id"),
        "query_id": d.get("query_id"),
        "topic": d.get("topic"),
        "title": d.get("title") or d.get("source_title"),
        "url": d.get("url_or_reference") or d.get("source_url") or d.get("url"),
    }

def pattern_covers_digest(patterns, digest):
    did = digest.get("digest_id")
    qid = digest.get("query_id")
    topic = digest.get("topic")
    title = digest.get("title") or digest.get("source_title")
    url = digest.get("url_or_reference") or digest.get("source_url") or digest.get("url")

    for p in patterns:
        if did and p.get("digest_id") == did:
            return True, "digest_id"
        if qid and topic and p.get("query_id") == qid and p.get("topic") == topic:
            return True, "query_topic"
        if qid and title and p.get("query_id") == qid and (p.get("title") == title or p.get("source_title") == title):
            return True, "query_title"
        if qid and url and p.get("query_id") == qid and (p.get("url_or_reference") == url or p.get("source_url") == url or p.get("url") == url):
            return True, "query_url"

    return False, None

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    digests = load_jsonl(DIGESTS)
    patterns = load_jsonl(PATTERNS)

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

    if not digests:
        failures.append("missing_real_digests")

    covered = []
    gaps = []

    for d in digests:
        if not d.get("pattern_candidate_ready"):
            continue

        is_covered, match_mode = pattern_covers_digest(patterns, d)
        row = digest_identity(d)
        row["pattern_candidate_ready"] = d.get("pattern_candidate_ready")
        row["match_mode"] = match_mode

        if is_covered:
            covered.append(row)
        else:
            gaps.append(d)

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "planner_id": PLANNER_ID,
        "result": result,
        "digest_count": len(digests),
        "pattern_count": len(patterns),
        "covered_digest_count": len(covered),
        "pattern_gap_count": len(gaps),
        "covered_digests": covered,
        "pattern_gaps": gaps,
        "recommended_next_step": "build_incremental_real_pattern_extractor" if gaps else "no_pattern_gap",
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "planner_only": True
        },
        "failures": failures
    }

    out_json = REPORT_DIR / f"research-real-digest-pattern-gap-planner-{stamp()}.json"
    out_md = REPORT_DIR / f"research-real-digest-pattern-gap-planner-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Real Digest Pattern Gap Planner")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- planner_id: `{PLANNER_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- digest_count: `{len(digests)}`")
    lines.append(f"- pattern_count: `{len(patterns)}`")
    lines.append(f"- covered_digest_count: `{len(covered)}`")
    lines.append(f"- pattern_gap_count: `{len(gaps)}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Pattern gaps")
    lines.append("")
    if gaps:
        for d in gaps:
            lines.append(f"- `{d.get('query_id')}` topic=`{d.get('topic')}` title={d.get('title') or d.get('source_title')}")
    else:
        lines.append("- none")
    lines.append("")
    if failures:
        lines.append("## Failures")
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("research_real_digest_pattern_gap_planner =", result)
    print("planner_id =", PLANNER_ID)
    print("gap_json =", out_json)
    print("gap_md =", out_md)
    print("digest_count =", len(digests))
    print("pattern_count =", len(patterns))
    print("covered_digest_count =", len(covered))
    print("pattern_gap_count =", len(gaps))
    print("recommended_next_step =", payload["recommended_next_step"])
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if gaps:
        print()
        print("pattern_gap_preview =")
        for d in gaps:
            print(f"- {d.get('query_id')} topic={d.get('topic')} title={d.get('title') or d.get('source_title')}")

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
