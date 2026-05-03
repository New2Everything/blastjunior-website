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

CANDIDATES = RESEARCH_DIR / "web-source-candidates.jsonl"
VALIDATIONS = RESEARCH_DIR / "web-source-candidate-validations.jsonl"
ENRICHMENT_PACKETS = RESEARCH_DIR / "web-source-candidate-enrichment-packets.jsonl"

GENERATOR_ID = "learning-v2-research-candidate-enrichment-packet-generator-v0"

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
    rows = load_jsonl(ENRICHMENT_PACKETS)
    return {
        r.get("candidate_id")
        for r in rows
        if r.get("candidate_id")
    }

def build_candidate_lookup():
    return {
        c.get("candidate_id"): c
        for c in load_jsonl(CANDIDATES)
        if c.get("candidate_id")
    }

def missing_fields_from_validation(v):
    warnings = v.get("warnings") or []
    missing = []

    if "missing_claim_summary_for_real_source_intake" in warnings:
        missing.append("claim_summary")
    if "missing_key_claims_for_real_source_intake" in warnings:
        missing.append("key_claims")
    if "missing_design_principles_for_real_source_intake" in warnings:
        missing.append("design_principles")

    return missing

def build_packet(validation, candidate):
    candidate_id = validation.get("candidate_id")
    missing_fields = missing_fields_from_validation(validation)

    return {
        "packet_id": f"candidate-enrichment-packet-{candidate_id}-{stamp()}",
        "candidate_id": candidate_id,
        "task_id": validation.get("task_id") or candidate.get("task_id"),
        "query_id": validation.get("query_id") or candidate.get("query_id"),
        "topic": validation.get("topic") or candidate.get("topic"),
        "title": validation.get("title") or candidate.get("title"),
        "url": validation.get("url") or candidate.get("url"),
        "publisher_or_author": validation.get("publisher_or_author") or candidate.get("publisher_or_author"),
        "source_type_guess": validation.get("source_type_guess") or candidate.get("source_type_guess"),
        "candidate_confidence": validation.get("candidate_confidence") or candidate.get("candidate_confidence"),
        "validation_decision": validation.get("decision"),
        "validation_next_step": validation.get("next_step"),
        "missing_fields": missing_fields,
        "status": "enrichment_packet_ready",
        "enrichment_goal": "Collect claim_summary, key_claims, and design_principles so this candidate can be revalidated for real-source-intake.",
        "copy_ready_instruction": (
            "Open and review the candidate source. Extract a concise claim_summary, 2-4 paraphrased key_claims, "
            "and 2-4 reusable design_principles. Do not copy long passages. Do not write to sources.jsonl directly. "
            "Return the enriched candidate record using the required_output_schema."
        ),
        "required_output_schema": {
            "candidate_id": candidate_id,
            "task_id": validation.get("task_id") or candidate.get("task_id"),
            "query_id": validation.get("query_id") or candidate.get("query_id"),
            "topic": validation.get("topic") or candidate.get("topic"),
            "title": validation.get("title") or candidate.get("title"),
            "url": validation.get("url") or candidate.get("url"),
            "publisher_or_author": validation.get("publisher_or_author") or candidate.get("publisher_or_author"),
            "source_type_guess": validation.get("source_type_guess") or candidate.get("source_type_guess"),
            "candidate_confidence": validation.get("candidate_confidence") or candidate.get("candidate_confidence"),
            "claim_summary": "Concise paraphrased summary of the candidate source's relevant claim.",
            "key_claims": [
                "Paraphrased key claim 1.",
                "Paraphrased key claim 2."
            ],
            "design_principles": [
                "Reusable design principle 1.",
                "Reusable design principle 2."
            ],
            "applicability_to_blastjunior": "Where this source may apply to BLXST / HADO website or community experience.",
            "retrieved_or_created_at": "YYYY-MM-DD",
            "web_browsed_by_openclaw": True,
            "sources_jsonl_written": False,
            "notes": "Enriched candidate only. Must be revalidated before real-source-intake."
        },
        "acceptance_criteria": [
            "claim_summary is present and paraphrased.",
            "key_claims contains at least two useful paraphrased claims.",
            "design_principles contains at least two reusable design principles.",
            "applicability_to_blastjunior explains how the source can inform BLXST / HADO site or community experience.",
            "The enriched candidate still must pass candidate validator before any real-source-intake."
        ],
        "reject_criteria": [
            "Long copied text from the source.",
            "No clear design or UX principle.",
            "Only marketing claims with no reusable lesson.",
            "Unclear relation to query_id/topic.",
            "Any attempt to write directly to sources.jsonl."
        ],
        "web_browsed_now": False,
        "sources_jsonl_written": False,
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
    out_json = REPORT_DIR / f"research-candidate-enrichment-packet-generator-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-candidate-enrichment-packet-generator-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Candidate Enrichment Packet Generator")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- generator_id: `{GENERATOR_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- input_validation_count: `{payload['input_validation_count']}`")
    lines.append(f"- packet_count: `{payload['packet_count']}`")
    lines.append(f"- fresh_packet_count: `{payload['fresh_packet_count']}`")
    lines.append(f"- duplicate_packet_count: `{payload['duplicate_packet_count']}`")
    lines.append("- web_browsed_now: `false`")
    lines.append("- sources_jsonl_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Packet preview")
    lines.append("")

    for pkt in payload["packets_preview"]:
        lines.append(f"### `{pkt.get('candidate_id')}`")
        lines.append("")
        lines.append(f"- title: {pkt.get('title')}")
        lines.append(f"- url: {pkt.get('url')}")
        lines.append(f"- query_id: `{pkt.get('query_id')}`")
        lines.append(f"- topic: `{pkt.get('topic')}`")
        lines.append(f"- missing_fields: `{', '.join(pkt.get('missing_fields') or [])}`")
        lines.append(f"- status: `{pkt.get('status')}`")
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
    ap.add_argument("--apply", action="store_true", help="append enrichment packets to web-source-candidate-enrichment-packets.jsonl")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    validations = load_jsonl(VALIDATIONS)
    candidate_lookup = build_candidate_lookup()

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

    if not validations:
        failures.append("missing_web_source_candidate_validations")

    existing = existing_packet_keys()
    fresh = []
    duplicates = 0

    for v in validations:
        if v.get("decision") != "needs_enrichment_before_real_source_intake":
            continue

        cid = v.get("candidate_id")
        if not cid:
            failures.append("validation_missing_candidate_id")
            continue

        if cid in existing:
            duplicates += 1
            continue

        candidate = candidate_lookup.get(cid)
        if not candidate:
            failures.append(f"candidate_not_found_for_validation:{cid}")
            continue

        fresh.append(build_packet(v, candidate))

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "generator_id": GENERATOR_ID,
        "result": result,
        "apply": args.apply,
        "input_validation_count": len(validations),
        "packet_count": len(fresh) + duplicates,
        "fresh_packet_count": len(fresh),
        "duplicate_packet_count": duplicates,
        "packets_preview": fresh[:10],
        "policy": {
            "web_browsed_now": False,
            "sources_jsonl_written": False,
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

    print("research_candidate_enrichment_packet_generator =", result)
    print("generator_id =", GENERATOR_ID)
    print("packet_json =", report_json)
    print("packet_md =", report_md)
    print("input_validation_count =", len(validations))
    print("fresh_packet_count =", len(fresh))
    print("duplicate_packet_count =", duplicates)
    print("web_browsed_now = false")
    print("sources_jsonl_written = false")
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if fresh:
        print()
        print("packet_preview =")
        for pkt in fresh:
            print(f"- {pkt.get('candidate_id')} topic={pkt.get('topic')} missing={pkt.get('missing_fields')}")

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

    if not args.apply:
        print("candidate_enrichment_packets_written = false")
        return 0

    if not fresh:
        print("candidate_enrichment_packets_written = false")
        print("reason = no_fresh_packets")
        return 0

    with ENRICHMENT_PACKETS.open("a", encoding="utf-8") as f:
        for pkt in fresh:
            f.write(json.dumps(pkt, ensure_ascii=False) + "\n")

    print("candidate_enrichment_packets_written = true")
    print("candidate_enrichment_packets_path =", ENRICHMENT_PACKETS)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
