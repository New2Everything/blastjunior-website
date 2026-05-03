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
REPORT_DIR.mkdir(parents=True, exist_ok=True)

DIGESTS = RESEARCH_DIR / "digests.jsonl"

DIGESTER_ID = "learning-v2-research-incremental-real-source-digester-v0"

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

def latest_gap_report():
    reports = sorted(REPORT_DIR.glob("research-real-source-digest-gap-planner-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def digest_key(row):
    return (
        row.get("query_id"),
        row.get("title") or row.get("source_title"),
        row.get("url_or_reference") or row.get("source_url") or row.get("url"),
    )

def existing_digest_keys():
    rows = load_jsonl(DIGESTS)
    return {digest_key(r) for r in rows}

def make_digest(source):
    query_id = source.get("query_id")
    title = source.get("title")
    topic = source.get("topic")
    url = source.get("url_or_reference")

    key_claims = source.get("key_claims") or []
    design_principles = source.get("design_principles") or []

    return {
        "digest_id": f"digest-{query_id}-{stamp()}",
        "source_digest_type": "real_source_incremental_digest",
        "query_id": query_id,
        "topic": topic,
        "title": title,
        "source_title": title,
        "source_type": source.get("source_type"),
        "publisher_or_author": source.get("publisher_or_author"),
        "url_or_reference": url,
        "source_url": url,
        "confidence": source.get("confidence"),
        "claim_summary": source.get("claim_summary"),
        "key_claims": key_claims,
        "design_principles": design_principles,
        "applicability_to_blastjunior": source.get("applicability_to_blastjunior"),
        "retrieved_or_created_at": source.get("retrieved_or_created_at"),
        "notes": source.get("notes"),
        "pattern_candidate_ready": bool(design_principles),
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "created_at": now_iso(),
        "digester_id": DIGESTER_ID,
    }

def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    out_json = REPORT_DIR / f"research-incremental-real-source-digester-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-incremental-real-source-digester-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Incremental Real Source Digester")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- digester_id: `{DIGESTER_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- gap_report: `{payload['gap_report']}`")
    lines.append(f"- input_gap_count: `{payload['input_gap_count']}`")
    lines.append(f"- digest_count: `{payload['digest_count']}`")
    lines.append(f"- fresh_digest_count: `{payload['fresh_digest_count']}`")
    lines.append(f"- duplicate_digest_count: `{payload['duplicate_digest_count']}`")
    lines.append("- business_source_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("")
    lines.append("## Digest preview")
    lines.append("")
    for d in payload["digests_preview"]:
        lines.append(f"- `{d.get('query_id')}` topic=`{d.get('topic')}` title={d.get('title')} pattern_candidate_ready=`{str(d.get('pattern_candidate_ready')).lower()}`")
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
    ap.add_argument("--apply", action="store_true", help="append incremental digests to learning-v2/research/digests.jsonl")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    gap_path, gap = latest_gap_report()

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

    if not gap_path:
        failures.append("missing_digest_gap_report")

    if gap.get("result") != "ok":
        failures.append(f"digest_gap_report_not_ok:{gap.get('result')}")

    gap_sources = gap.get("digest_gaps") or []
    if not gap_sources:
        failures.append("no_digest_gaps_to_process")

    existing = existing_digest_keys()
    fresh = []
    duplicates = 0

    for source in gap_sources:
        key = (
            source.get("query_id"),
            source.get("title"),
            source.get("url_or_reference"),
        )
        if key in existing:
            duplicates += 1
            continue
        fresh.append(make_digest(source))

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "digester_id": DIGESTER_ID,
        "result": result,
        "apply": args.apply,
        "gap_report": str(gap_path) if gap_path else None,
        "input_gap_count": len(gap_sources),
        "digest_count": len(fresh) + duplicates,
        "fresh_digest_count": len(fresh),
        "duplicate_digest_count": duplicates,
        "digests_preview": fresh[:10],
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "incremental_only": True,
        },
        "failures": failures,
    }

    report_json, report_md = write_report(payload, args.apply)

    print("research_incremental_real_source_digester =", result)
    print("digester_id =", DIGESTER_ID)
    print("digest_json =", report_json)
    print("digest_md =", report_md)
    print("gap_report =", gap_path)
    print("input_gap_count =", len(gap_sources))
    print("fresh_digest_count =", len(fresh))
    print("duplicate_digest_count =", duplicates)
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if fresh:
        print()
        print("digest_preview =")
        for d in fresh:
            print(f"- {d.get('query_id')} topic={d.get('topic')} title={d.get('title')} pattern_candidate_ready={d.get('pattern_candidate_ready')}")

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

    if not args.apply:
        print("incremental_digests_written = false")
        return 0

    if not fresh:
        print("incremental_digests_written = false")
        print("reason = no_fresh_digests")
        return 0

    with DIGESTS.open("a", encoding="utf-8") as f:
        for d in fresh:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    print("incremental_digests_written = true")
    print("digests_path =", DIGESTS)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
