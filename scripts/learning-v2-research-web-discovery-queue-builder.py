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

PACKETS = RESEARCH_DIR / "manual-collection-packets.jsonl"
QUEUE = RESEARCH_DIR / "web-source-discovery-queue.jsonl"

BUILDER_ID = "learning-v2-research-web-discovery-queue-builder-v0"

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

def existing_queue_keys():
    rows = load_jsonl(QUEUE)
    return {
        (r.get("packet_id"), r.get("search_phrase"))
        for r in rows
        if r.get("packet_id") and r.get("search_phrase")
    }

def make_task(packet, search_phrase, phrase_rank):
    query_id = packet.get("query_id")
    topic = packet.get("topic")
    packet_id = packet.get("packet_id")

    return {
        "task_id": f"web-discovery-task-{query_id}-{phrase_rank}-{stamp()}",
        "packet_id": packet_id,
        "request_id": packet.get("request_id"),
        "query_id": query_id,
        "topic": topic,
        "priority_rank": packet.get("priority_rank"),
        "phrase_rank": phrase_rank,
        "search_phrase": search_phrase,
        "target_source_types": packet.get("target_source_types") or [],
        "minimum_source_count": packet.get("minimum_source_count"),
        "preferred_source_count": packet.get("preferred_source_count"),
        "status": "planned",
        "candidate_output_store": "learning-v2/research/web-source-candidates.jsonl",
        "max_candidates_to_collect": 3,
        "quality_filter": [
            "Prefer official guidelines, design systems, reputable UX case studies, or research papers.",
            "Avoid SEO spam, AI-generated placeholder pages, unclear publishers, or pure ads.",
            "Search result snippets are not enough; candidates must later be opened and validated.",
            "Candidate discovery must not write sources.jsonl directly.",
            "Real source intake must happen only through learning-v2-research-real-source-intake.py."
        ],
        "candidate_schema": {
            "candidate_id": "web-source-candidate-<query_id>-<timestamp>-<rank>",
            "task_id": "this task id",
            "packet_id": packet_id,
            "request_id": packet.get("request_id"),
            "query_id": query_id,
            "topic": topic,
            "search_phrase": search_phrase,
            "title": "candidate source title",
            "url": "candidate source url",
            "publisher_or_author": "publisher or author if available",
            "source_type_guess": "official guideline / design system / UX case study / paper / website case",
            "why_relevant": "short relevance explanation",
            "candidate_confidence": "low / medium / medium-high / high",
            "requires_validation_before_intake": True,
            "web_browsed_by_openclaw": True,
            "sources_jsonl_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False
        },
        "web_browsed_now": False,
        "sources_jsonl_written": False,
        "state_written": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "created_at": now_iso(),
        "builder_id": BUILDER_ID,
    }

def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    out_json = REPORT_DIR / f"research-web-discovery-queue-builder-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-web-discovery-queue-builder-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Web Discovery Queue Builder")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- builder_id: `{BUILDER_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- input_packet_count: `{payload['input_packet_count']}`")
    lines.append(f"- task_count: `{payload['task_count']}`")
    lines.append(f"- fresh_task_count: `{payload['fresh_task_count']}`")
    lines.append(f"- duplicate_task_count: `{payload['duplicate_task_count']}`")
    lines.append("- web_browsed_now: `false`")
    lines.append("- sources_jsonl_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Task preview")
    lines.append("")

    for t in payload["tasks_preview"]:
        lines.append(f"### `{t.get('task_id')}`")
        lines.append("")
        lines.append(f"- query_id: `{t.get('query_id')}`")
        lines.append(f"- topic: `{t.get('topic')}`")
        lines.append(f"- priority_rank: `{t.get('priority_rank')}`")
        lines.append(f"- phrase_rank: `{t.get('phrase_rank')}`")
        lines.append(f"- search_phrase: {t.get('search_phrase')}")
        lines.append(f"- max_candidates_to_collect: `{t.get('max_candidates_to_collect')}`")
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
    ap.add_argument("--apply", action="store_true", help="append web discovery tasks to research/web-source-discovery-queue.jsonl")
    ap.add_argument("--limit-packets", type=int, default=5)
    ap.add_argument("--limit-phrases-per-packet", type=int, default=4)
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    packets = load_jsonl(PACKETS)

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

    if not packets:
        failures.append("missing_manual_collection_packets")

    existing = existing_queue_keys()
    fresh = []
    duplicates = 0

    for packet in packets[:args.limit_packets]:
        phrases = packet.get("search_phrases") or []
        for idx, phrase in enumerate(phrases[:args.limit_phrases_per_packet], 1):
            key = (packet.get("packet_id"), phrase)
            if key in existing:
                duplicates += 1
                continue
            fresh.append(make_task(packet, phrase, idx))

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "builder_id": BUILDER_ID,
        "result": result,
        "apply": args.apply,
        "input_packet_count": len(packets),
        "task_count": len(fresh) + duplicates,
        "fresh_task_count": len(fresh),
        "duplicate_task_count": duplicates,
        "tasks_preview": fresh[:20],
        "policy": {
            "web_browsed_now": False,
            "sources_jsonl_written": False,
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "queue_only": True,
        },
        "failures": failures,
    }

    report_json, report_md = write_report(payload, args.apply)

    print("research_web_discovery_queue_builder =", result)
    print("builder_id =", BUILDER_ID)
    print("queue_json =", report_json)
    print("queue_md =", report_md)
    print("input_packet_count =", len(packets))
    print("fresh_task_count =", len(fresh))
    print("duplicate_task_count =", duplicates)
    print("web_browsed_now = false")
    print("sources_jsonl_written = false")
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if fresh:
        print()
        print("task_preview =")
        for t in fresh[:10]:
            print(f"- {t.get('query_id')} topic={t.get('topic')} phrase={t.get('search_phrase')}")

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

    if not args.apply:
        print("web_discovery_queue_written = false")
        return 0

    if not fresh:
        print("web_discovery_queue_written = false")
        print("reason = no_fresh_tasks")
        return 0

    with QUEUE.open("a", encoding="utf-8") as f:
        for task in fresh:
            f.write(json.dumps(task, ensure_ascii=False) + "\n")

    print("web_discovery_queue_written = true")
    print("web_discovery_queue_path =", QUEUE)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
