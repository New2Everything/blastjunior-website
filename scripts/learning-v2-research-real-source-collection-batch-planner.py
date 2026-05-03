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

REQUESTS = RESEARCH_DIR / "real-source-collection-requests.jsonl"
PLANNER_ID = "learning-v2-research-real-source-collection-batch-planner-v0"

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

def latest_coverage_report():
    reports = sorted(REPORT_DIR.glob("research-real-coverage-planner-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def existing_request_keys():
    rows = load_jsonl(REQUESTS)
    return {
        (r.get("query_id"), r.get("topic"))
        for r in rows
        if r.get("query_id")
    }

def source_type_targets(topic):
    mapping = {
        "community-experience": [
            "community product UX case study",
            "sports club/community website case",
            "membership onboarding case",
        ],
        "content-hierarchy": [
            "content hierarchy UX guideline",
            "information architecture case study",
            "homepage content structure example",
        ],
        "conversion-design": [
            "parent conversion landing page case",
            "youth sports signup funnel case",
            "trust-building UX guideline",
        ],
        "event-experience": [
            "event website UX case study",
            "sports event information design",
            "schedule/results UX pattern",
        ],
        "mobile-first": [
            "mobile navigation UX guideline",
            "responsive navigation design system",
            "mobile-first website case",
        ],
    }
    return mapping.get(topic, [
        "official guideline",
        "design system documentation",
        "high-quality UX case study",
    ])

def make_request(item, rank):
    query_id = item.get("query_id")
    topic = item.get("topic")
    return {
        "request_id": f"real-source-request-{query_id}-{stamp()}",
        "query_id": query_id,
        "topic": topic,
        "priority_rank": rank,
        "status": "planned",
        "coverage_status": item.get("status"),
        "question": item.get("question"),
        "collection_goal": item.get("recommendation"),
        "target_source_types": source_type_targets(topic),
        "minimum_source_count": 1,
        "preferred_source_count": 2,
        "quality_requirements": [
            "Prefer official guidelines, design systems, research papers, or mature public case studies.",
            "Do not use test fixtures or generated placeholder sources.",
            "Source record must include key_claims and design_principles.",
            "Source must be digested before pattern extraction.",
            "If source suggests an already completed target-family, archive as evidence reinforcement rather than restarting it.",
        ],
        "output_schema": {
            "query_id": query_id,
            "title": "Real source title",
            "source_type": "official guideline / design system / UX case study / paper / website case",
            "publisher_or_author": "Publisher or author",
            "url_or_reference": "https://example.com/real-source",
            "topic": topic,
            "claim_summary": "Concise paraphrased claim from the source.",
            "confidence": "medium / medium-high / high",
            "key_claims": [
                "Paraphrased key claim."
            ],
            "design_principles": [
                "Reusable design principle."
            ],
            "applicability_to_blastjunior": "Where this may apply in BLXST / HADO site experience.",
            "retrieved_or_created_at": "YYYY-MM-DD",
            "notes": "Real source record. Must be digested before pattern extraction."
        },
        "web_browse_allowed_later": True,
        "web_browsed_now": False,
        "source_changes_allowed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "created_at": now_iso(),
        "planner_id": PLANNER_ID,
    }

def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    out_json = REPORT_DIR / f"research-real-source-collection-batch-planner-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-real-source-collection-batch-planner-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Real Source Collection Batch Planner")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- planner_id: `{PLANNER_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- coverage_report: `{payload['coverage_report']}`")
    lines.append(f"- request_count: `{payload['request_count']}`")
    lines.append(f"- fresh_request_count: `{payload['fresh_request_count']}`")
    lines.append(f"- duplicate_request_count: `{payload['duplicate_request_count']}`")
    lines.append("- web_browsed_now: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Planned requests")
    lines.append("")
    for r in payload["requests_preview"]:
        lines.append(f"### `{r.get('query_id')}`")
        lines.append("")
        lines.append(f"- topic: `{r.get('topic')}`")
        lines.append(f"- priority_rank: `{r.get('priority_rank')}`")
        lines.append(f"- minimum_source_count: `{r.get('minimum_source_count')}`")
        lines.append(f"- preferred_source_count: `{r.get('preferred_source_count')}`")
        lines.append(f"- collection_goal: {r.get('collection_goal')}")
        lines.append("- target_source_types:")
        for t in r.get("target_source_types") or []:
            lines.append(f"  - {t}")
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
    ap.add_argument("--apply", action="store_true", help="append planned collection requests to research/real-source-collection-requests.jsonl")
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    coverage_path, coverage = latest_coverage_report()

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

    if not coverage_path:
        failures.append("missing_real_coverage_planner_report")

    if coverage.get("result") != "ok":
        failures.append(f"coverage_planner_not_ok:{coverage.get('result')}")

    next_collection = coverage.get("next_collection") or []
    if not next_collection:
        failures.append("no_next_collection_items")

    existing = existing_request_keys()
    requests = []
    duplicates = 0

    for idx, item in enumerate(next_collection[:args.limit], 1):
        key = (item.get("query_id"), item.get("topic"))
        req = make_request(item, idx)
        if key in existing:
            duplicates += 1
        else:
            requests.append(req)

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "planner_id": PLANNER_ID,
        "result": result,
        "apply": args.apply,
        "coverage_report": str(coverage_path) if coverage_path else None,
        "input_next_collection_count": len(next_collection),
        "request_count": len(requests) + duplicates,
        "fresh_request_count": len(requests),
        "duplicate_request_count": duplicates,
        "requests_preview": requests[:10],
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "web_browsed_now": False,
            "planner_only": True,
        },
        "failures": failures,
    }

    report_json, report_md = write_report(payload, args.apply)

    print("research_real_source_collection_batch_planner =", result)
    print("planner_id =", PLANNER_ID)
    print("coverage_report =", coverage_path)
    print("batch_json =", report_json)
    print("batch_md =", report_md)
    print("input_next_collection_count =", len(next_collection))
    print("fresh_request_count =", len(requests))
    print("duplicate_request_count =", duplicates)
    print("web_browsed_now = false")
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if requests:
        print()
        print("request_preview =")
        for r in requests:
            print(f"- {r.get('query_id')} topic={r.get('topic')} priority={r.get('priority_rank')}")

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

    if not args.apply:
        print("collection_requests_written = false")
        return 0

    if not requests:
        print("collection_requests_written = false")
        print("reason = no_fresh_requests")
        return 0

    with REQUESTS.open("a", encoding="utf-8") as f:
        for r in requests:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("collection_requests_written = true")
    print("collection_requests_path =", REQUESTS)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
