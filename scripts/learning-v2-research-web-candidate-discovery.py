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

QUEUE = RESEARCH_DIR / "web-source-discovery-queue.jsonl"
CANDIDATES = RESEARCH_DIR / "web-source-candidates.jsonl"

DISCOVERY_ID = "learning-v2-research-web-candidate-discovery-v0"

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

def existing_candidate_keys():
    rows = load_jsonl(CANDIDATES)
    return {
        (r.get("task_id"), r.get("url"))
        for r in rows
        if r.get("task_id") and r.get("url")
    }

def make_placeholder_candidate(task, rank):
    """
    v0 intentionally does NOT browse.
    It creates a candidate-discovery placeholder so the execution path,
    schema, duplicate policy, and safety gates can be tested before web access.
    """
    return {
        "candidate_id": f"web-source-candidate-placeholder-{task.get('query_id')}-{rank}-{stamp()}",
        "task_id": task.get("task_id"),
        "packet_id": task.get("packet_id"),
        "request_id": task.get("request_id"),
        "query_id": task.get("query_id"),
        "topic": task.get("topic"),
        "search_phrase": task.get("search_phrase"),
        "rank": rank,
        "title": None,
        "url": None,
        "publisher_or_author": None,
        "source_type_guess": None,
        "why_relevant": "placeholder only; no web browsing performed in v0",
        "candidate_confidence": "low",
        "requires_validation_before_intake": True,
        "web_browsed_by_openclaw": False,
        "sources_jsonl_written": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "status": "placeholder_not_a_real_source",
        "created_at": now_iso(),
        "discovery_id": DISCOVERY_ID,
    }

def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    out_json = REPORT_DIR / f"research-web-candidate-discovery-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-web-candidate-discovery-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Web Candidate Discovery")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- discovery_id: `{DISCOVERY_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- mode: `{payload['mode']}`")
    lines.append(f"- input_task_count: `{payload['input_task_count']}`")
    lines.append(f"- candidate_count: `{payload['candidate_count']}`")
    lines.append(f"- fresh_candidate_count: `{payload['fresh_candidate_count']}`")
    lines.append(f"- duplicate_candidate_count: `{payload['duplicate_candidate_count']}`")
    lines.append("- web_browsed_now: `false`")
    lines.append("- sources_jsonl_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Important")
    lines.append("")
    lines.append("This v0 executor does not browse the web and does not produce real sources.")
    lines.append("It only proves the candidate-discovery execution path and schema guardrails.")
    lines.append("")
    lines.append("## Candidate preview")
    lines.append("")

    for c in payload["candidates_preview"][:10]:
        lines.append(f"### `{c.get('candidate_id')}`")
        lines.append("")
        lines.append(f"- task_id: `{c.get('task_id')}`")
        lines.append(f"- query_id: `{c.get('query_id')}`")
        lines.append(f"- topic: `{c.get('topic')}`")
        lines.append(f"- search_phrase: {c.get('search_phrase')}")
        lines.append(f"- status: `{c.get('status')}`")
        lines.append(f"- web_browsed_by_openclaw: `{str(c.get('web_browsed_by_openclaw')).lower()}`")
        lines.append(f"- sources_jsonl_written: `{str(c.get('sources_jsonl_written')).lower()}`")
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
    ap.add_argument("--apply", action="store_true", help="append placeholder candidates to web-source-candidates.jsonl")
    ap.add_argument("--limit-tasks", type=int, default=5)
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    tasks = load_jsonl(QUEUE)

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

    if not tasks:
        failures.append("missing_web_source_discovery_queue")

    existing = existing_candidate_keys()
    fresh = []
    duplicates = 0

    for idx, task in enumerate(tasks[:args.limit_tasks], 1):
        c = make_placeholder_candidate(task, idx)
        key = (c.get("task_id"), c.get("url"))
        if key in existing:
            duplicates += 1
            continue
        fresh.append(c)

    if args.apply:
        failures.append("placeholder_apply_to_real_web_source_candidates_blocked")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "discovery_id": DISCOVERY_ID,
        "result": result,
        "apply": args.apply,
        "mode": "placeholder_no_web_v0",
        "input_task_count": len(tasks),
        "candidate_count": len(fresh) + duplicates,
        "fresh_candidate_count": len(fresh),
        "duplicate_candidate_count": duplicates,
        "candidates_preview": fresh[:20],
        "policy": {
            "web_browsed_now": False,
            "sources_jsonl_written": False,
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "placeholder_only": True,
        },
        "failures": failures,
    }

    report_json, report_md = write_report(payload, args.apply)

    print("research_web_candidate_discovery =", result)
    print("discovery_id =", DISCOVERY_ID)
    print("mode = placeholder_no_web_v0")
    print("discovery_json =", report_json)
    print("discovery_md =", report_md)
    print("input_task_count =", len(tasks))
    print("fresh_candidate_count =", len(fresh))
    print("duplicate_candidate_count =", duplicates)
    print("web_browsed_now = false")
    print("sources_jsonl_written = false")
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if fresh:
        print()
        print("candidate_preview =")
        for c in fresh[:10]:
            print(f"- {c.get('query_id')} topic={c.get('topic')} phrase={c.get('search_phrase')} status={c.get('status')}")

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

    if not args.apply:
        print("web_source_candidates_written = false")
        return 0

    if not fresh:
        print("web_source_candidates_written = false")
        print("reason = no_fresh_candidates")
        return 0

    with CANDIDATES.open("a", encoding="utf-8") as f:
        for c in fresh:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print("web_source_candidates_written = true")
    print("web_source_candidates_path =", CANDIDATES)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
