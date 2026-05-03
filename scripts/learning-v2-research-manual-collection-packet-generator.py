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
PACKETS = RESEARCH_DIR / "manual-collection-packets.jsonl"

GENERATOR_ID = "learning-v2-research-manual-collection-packet-generator-v0"

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

def existing_packet_keys():
    rows = load_jsonl(PACKETS)
    return {
        r.get("request_id")
        for r in rows
        if r.get("request_id")
    }

def search_phrases(topic):
    mapping = {
        "community-experience": [
            "community product onboarding UX case study",
            "sports club membership website UX case study",
            "online community engagement design case study",
            "youth sports club website onboarding example"
        ],
        "content-hierarchy": [
            "content hierarchy UX guidelines homepage",
            "information architecture homepage case study",
            "website content hierarchy best practices",
            "sports website homepage information architecture"
        ],
        "conversion-design": [
            "parent conversion landing page case study",
            "youth sports signup funnel UX case study",
            "trust-building landing page UX guidelines",
            "children activity signup page conversion case"
        ],
        "event-experience": [
            "event website UX case study schedule results",
            "sports event information design UX",
            "tournament website schedule results UX pattern",
            "event landing page attendee experience design"
        ],
        "mobile-first": [
            "mobile navigation UX guidelines",
            "responsive navigation design system",
            "mobile first website navigation case study",
            "hamburger menu accessibility responsive navigation"
        ],
    }
    return mapping.get(topic, [
        f"{topic} UX guideline",
        f"{topic} design case study",
        f"{topic} website best practices"
    ])

def build_packet(req):
    query_id = req.get("query_id")
    topic = req.get("topic")
    request_id = req.get("request_id")

    return {
        "packet_id": f"manual-collection-packet-{query_id}-{stamp()}",
        "request_id": request_id,
        "query_id": query_id,
        "topic": topic,
        "priority_rank": req.get("priority_rank"),
        "status": "packet_ready",
        "collection_goal": req.get("collection_goal"),
        "minimum_source_count": req.get("minimum_source_count"),
        "preferred_source_count": req.get("preferred_source_count"),
        "target_source_types": req.get("target_source_types") or [],
        "search_phrases": search_phrases(topic),
        "acceptance_criteria": [
            "Source should be a real external source, not a generated placeholder.",
            "Prefer official guidelines, mature design systems, research papers, or high-quality public case studies.",
            "Source should contain reusable UX/design principles, not only marketing copy.",
            "Source must be relevant to the query_id and topic.",
            "Collector must paraphrase key claims instead of copying long text.",
            "Collector must produce key_claims and design_principles.",
            "Do not ingest until the record passes real-source-intake validation."
        ],
        "reject_criteria": [
            "AI-generated source without external reference.",
            "Unclear author or publisher when a better source is available.",
            "Pure advertisement with no reusable design principle.",
            "Duplicate of an already ingested source.",
            "Test fixture or manual-test source."
        ],
        "required_output_schema": {
            "query_id": query_id,
            "title": "Real source title",
            "source_type": "official guideline / design system / UX case study / paper / website case",
            "publisher_or_author": "Publisher or author",
            "url_or_reference": "https://example.com/real-source",
            "topic": topic,
            "claim_summary": "Concise paraphrased claim from the source.",
            "confidence": "medium / medium-high / high",
            "key_claims": [
                "Paraphrased key claim 1.",
                "Paraphrased key claim 2."
            ],
            "design_principles": [
                "Reusable design principle 1.",
                "Reusable design principle 2."
            ],
            "applicability_to_blastjunior": "Where this may apply in BLXST / HADO site experience.",
            "retrieved_or_created_at": "YYYY-MM-DD",
            "notes": "Real source record. Must be digested before pattern extraction."
        },
        "copy_ready_instruction": (
            "Find 1-2 high-quality real sources for this learning-v2 research request. "
            "Use the required output schema exactly. Do not invent sources. "
            "Paraphrase key claims and design principles. Do not write to sources.jsonl directly."
        ),
        "web_browsed_now": False,
        "state_written": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "created_at": now_iso(),
        "generator_id": GENERATOR_ID,
    }

def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    out_json = REPORT_DIR / f"research-manual-collection-packet-generator-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-manual-collection-packet-generator-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Manual Collection Packet Generator")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- generator_id: `{GENERATOR_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- input_request_count: `{payload['input_request_count']}`")
    lines.append(f"- packet_count: `{payload['packet_count']}`")
    lines.append(f"- fresh_packet_count: `{payload['fresh_packet_count']}`")
    lines.append(f"- duplicate_packet_count: `{payload['duplicate_packet_count']}`")
    lines.append("- web_browsed_now: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Packets")
    lines.append("")

    for pkt in payload["packets_preview"]:
        lines.append(f"### `{pkt.get('query_id')}` — `{pkt.get('topic')}`")
        lines.append("")
        lines.append(f"- packet_id: `{pkt.get('packet_id')}`")
        lines.append(f"- request_id: `{pkt.get('request_id')}`")
        lines.append(f"- priority_rank: `{pkt.get('priority_rank')}`")
        lines.append(f"- minimum_source_count: `{pkt.get('minimum_source_count')}`")
        lines.append(f"- preferred_source_count: `{pkt.get('preferred_source_count')}`")
        lines.append(f"- collection_goal: {pkt.get('collection_goal')}")
        lines.append("")
        lines.append("#### Search phrases")
        lines.append("")
        for phrase in pkt.get("search_phrases") or []:
            lines.append(f"- {phrase}")
        lines.append("")
        lines.append("#### Copy-ready instruction")
        lines.append("")
        lines.append(pkt.get("copy_ready_instruction") or "")
        lines.append("")
        lines.append("#### Required output schema")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(pkt.get("required_output_schema"), ensure_ascii=False, indent=2))
        lines.append("```")
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
    ap.add_argument("--apply", action="store_true", help="append manual packets to research/manual-collection-packets.jsonl")
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    requests = load_jsonl(REQUESTS)

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

    if not requests:
        failures.append("missing_real_source_collection_requests")

    existing = existing_packet_keys()
    fresh = []
    duplicates = 0

    for req in requests[:args.limit]:
        if req.get("request_id") in existing:
            duplicates += 1
            continue
        fresh.append(build_packet(req))

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "generator_id": GENERATOR_ID,
        "result": result,
        "apply": args.apply,
        "input_request_count": len(requests),
        "packet_count": len(fresh) + duplicates,
        "fresh_packet_count": len(fresh),
        "duplicate_packet_count": duplicates,
        "packets_preview": fresh[:10],
        "policy": {
            "web_browsed_now": False,
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "packet_only": True,
        },
        "failures": failures,
    }

    report_json, report_md = write_report(payload, args.apply)

    print("research_manual_collection_packet_generator =", result)
    print("generator_id =", GENERATOR_ID)
    print("packet_json =", report_json)
    print("packet_md =", report_md)
    print("input_request_count =", len(requests))
    print("fresh_packet_count =", len(fresh))
    print("duplicate_packet_count =", duplicates)
    print("web_browsed_now = false")
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if fresh:
        print()
        print("packet_preview =")
        for pkt in fresh:
            print(f"- {pkt.get('query_id')} topic={pkt.get('topic')} priority={pkt.get('priority_rank')}")

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

    if not args.apply:
        print("manual_collection_packets_written = false")
        return 0

    if not fresh:
        print("manual_collection_packets_written = false")
        print("reason = no_fresh_packets")
        return 0

    with PACKETS.open("a", encoding="utf-8") as f:
        for pkt in fresh:
            f.write(json.dumps(pkt, ensure_ascii=False) + "\n")

    print("manual_collection_packets_written = true")
    print("manual_collection_packets_path =", PACKETS)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
