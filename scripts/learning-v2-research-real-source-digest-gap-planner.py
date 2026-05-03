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

SOURCES = RESEARCH_DIR / "sources.jsonl"
DIGESTS = RESEARCH_DIR / "digests.jsonl"

PLANNER_ID = "learning-v2-research-real-source-digest-gap-planner-v0"

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

def source_key(row):
    return (
        row.get("query_id"),
        row.get("title"),
        row.get("url_or_reference"),
    )

def digest_source_keys(digests):
    keys = set()
    for d in digests:
        keys.add((
            d.get("query_id"),
            d.get("title") or d.get("source_title"),
            d.get("url_or_reference") or d.get("source_url") or d.get("url"),
        ))
    return keys

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    sources = load_jsonl(SOURCES)
    digests = load_jsonl(DIGESTS)
    existing = digest_source_keys(digests)

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

    if not sources:
        failures.append("missing_real_sources")

    gaps = []
    covered = []

    for s in sources:
        key = source_key(s)
        if key in existing:
            covered.append(s)
        else:
            gaps.append(s)

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "planner_id": PLANNER_ID,
        "result": result,
        "source_count": len(sources),
        "digest_count": len(digests),
        "covered_source_count": len(covered),
        "digest_gap_count": len(gaps),
        "digest_gaps": gaps,
        "recommended_next_step": "build_incremental_real_source_digester" if gaps else "no_digest_gap",
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "planner_only": True,
        },
        "failures": failures,
    }

    out_json = REPORT_DIR / f"research-real-source-digest-gap-planner-{stamp()}.json"
    out_md = REPORT_DIR / f"research-real-source-digest-gap-planner-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Real Source Digest Gap Planner")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- planner_id: `{PLANNER_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- source_count: `{len(sources)}`")
    lines.append(f"- digest_count: `{len(digests)}`")
    lines.append(f"- covered_source_count: `{len(covered)}`")
    lines.append(f"- digest_gap_count: `{len(gaps)}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Digest gaps")
    lines.append("")
    if gaps:
        for s in gaps:
            lines.append(f"- `{s.get('query_id')}` topic=`{s.get('topic')}` title={s.get('title')}")
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

    print("research_real_source_digest_gap_planner =", result)
    print("planner_id =", PLANNER_ID)
    print("gap_json =", out_json)
    print("gap_md =", out_md)
    print("source_count =", len(sources))
    print("digest_count =", len(digests))
    print("covered_source_count =", len(covered))
    print("digest_gap_count =", len(gaps))
    print("recommended_next_step =", payload["recommended_next_step"])
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if gaps:
        print()
        print("digest_gap_preview =")
        for s in gaps:
            print(f"- {s.get('query_id')} topic={s.get('topic')} title={s.get('title')}")

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
