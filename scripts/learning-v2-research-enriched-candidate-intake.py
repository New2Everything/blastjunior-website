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

ENRICHMENT_PACKETS = RESEARCH_DIR / "web-source-candidate-enrichment-packets.jsonl"
ENRICHMENTS = RESEARCH_DIR / "web-source-candidate-enrichments.jsonl"

INTAKE_ID = "learning-v2-research-enriched-candidate-intake-v0"

REQUIRED_FIELDS = [
    "candidate_id",
    "task_id",
    "query_id",
    "topic",
    "title",
    "url",
    "publisher_or_author",
    "source_type_guess",
    "candidate_confidence",
    "claim_summary",
    "key_claims",
    "design_principles",
    "applicability_to_blastjunior",
    "retrieved_or_created_at",
]

BLOCKED_MARKERS = [
    "placeholder_not_a_real_source",
    "placeholder only",
    "manual-test://",
    "test_fixture",
    "Schema validation fixture",
    "Do not treat as external evidence",
]

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

def load_input_file(path):
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(path))

    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        obj = json.loads(text)
        return obj if isinstance(obj, list) else [obj]

    rows = []
    for line in text.splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows

def packet_lookup():
    return {
        p.get("candidate_id"): p
        for p in load_jsonl(ENRICHMENT_PACKETS)
        if p.get("candidate_id")
    }

def existing_enrichment_keys():
    rows = load_jsonl(ENRICHMENTS)
    return {
        r.get("candidate_id")
        for r in rows
        if r.get("candidate_id")
    }

def has_blocked_marker(row):
    blob = json.dumps(row, ensure_ascii=False)
    return any(m in blob for m in BLOCKED_MARKERS)

def validate_row(row, packets):
    failures = []

    for f in REQUIRED_FIELDS:
        if not row.get(f):
            failures.append(f"missing_required_field:{f}")

    cid = row.get("candidate_id")
    packet = packets.get(cid)

    if not packet:
        failures.append(f"unknown_candidate_id:{cid}")
    else:
        for f in ["task_id", "query_id", "topic", "title", "url"]:
            if row.get(f) != packet.get(f):
                failures.append(f"packet_mismatch:{f}:row={row.get(f)} packet={packet.get(f)}")

    url = str(row.get("url") or "")
    if not (url.startswith("http://") or url.startswith("https://")):
        failures.append(f"invalid_url:{url}")

    key_claims = row.get("key_claims")
    if not isinstance(key_claims, list) or len(key_claims) < 2:
        failures.append("key_claims_must_be_list_with_at_least_2_items")

    design_principles = row.get("design_principles")
    if not isinstance(design_principles, list) or len(design_principles) < 2:
        failures.append("design_principles_must_be_list_with_at_least_2_items")

    if row.get("sources_jsonl_written") is True:
        failures.append("enriched_candidate_must_not_claim_sources_jsonl_written")

    if has_blocked_marker(row):
        failures.append("blocked_marker_detected")

    return failures

def normalize(row):
    return {
        "enrichment_id": row.get("enrichment_id") or f"candidate-enrichment-{row.get('candidate_id')}-{stamp()}",
        "candidate_id": row.get("candidate_id"),
        "task_id": row.get("task_id"),
        "query_id": row.get("query_id"),
        "topic": row.get("topic"),
        "title": row.get("title"),
        "url": row.get("url"),
        "publisher_or_author": row.get("publisher_or_author"),
        "source_type_guess": row.get("source_type_guess"),
        "candidate_confidence": row.get("candidate_confidence"),
        "claim_summary": row.get("claim_summary"),
        "key_claims": row.get("key_claims"),
        "design_principles": row.get("design_principles"),
        "applicability_to_blastjunior": row.get("applicability_to_blastjunior"),
        "retrieved_or_created_at": row.get("retrieved_or_created_at"),
        "notes": row.get("notes"),
        "status": "enriched_candidate_ready_for_revalidation",
        "requires_revalidation_before_real_source_intake": True,
        "sources_jsonl_written": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "ingested_at": now_iso(),
        "intake_id": INTAKE_ID,
    }

def template(packets):
    first = next(iter(packets.values()), {})
    return {
        "candidate_id": first.get("candidate_id") or "web-source-candidate-...",
        "task_id": first.get("task_id") or "web-discovery-task-...",
        "query_id": first.get("query_id") or "rq-community-ux-001",
        "topic": first.get("topic") or "community-experience",
        "title": first.get("title") or "Candidate source title",
        "url": first.get("url") or "https://example.com/source",
        "publisher_or_author": first.get("publisher_or_author") or "Publisher or author",
        "source_type_guess": first.get("source_type_guess") or "UX case study",
        "candidate_confidence": first.get("candidate_confidence") or "medium-high",
        "claim_summary": "Concise paraphrased summary of the relevant claim.",
        "key_claims": [
            "Paraphrased key claim 1.",
            "Paraphrased key claim 2."
        ],
        "design_principles": [
            "Reusable design principle 1.",
            "Reusable design principle 2."
        ],
        "applicability_to_blastjunior": "How this source may apply to BLXST / HADO website or community experience.",
        "retrieved_or_created_at": "YYYY-MM-DD",
        "sources_jsonl_written": False,
        "notes": "Enriched candidate only. Must be revalidated before real-source-intake."
    }

def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    out_json = REPORT_DIR / f"research-enriched-candidate-intake-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-enriched-candidate-intake-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Enriched Candidate Intake")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- intake_id: `{INTAKE_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- input_count: `{payload['input_count']}`")
    lines.append(f"- valid_count: `{payload['valid_count']}`")
    lines.append(f"- duplicate_count: `{payload['duplicate_count']}`")
    lines.append("- sources_jsonl_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Template")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(payload["template"], ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")

    if payload["enrichments_preview"]:
        lines.append("## Enrichment preview")
        lines.append("")
        for r in payload["enrichments_preview"]:
            lines.append(f"- `{r.get('candidate_id')}` `{r.get('topic')}` — {r.get('title')}")
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
    ap.add_argument("--enrichment-file", help="JSON or JSONL enriched candidate records")
    ap.add_argument("--apply", action="store_true", help="append validated enriched candidates to web-source-candidate-enrichments.jsonl")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    packets = packet_lookup()

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
        failures.append("missing_candidate_enrichment_packets")

    input_rows = load_input_file(args.enrichment_file) if args.enrichment_file else []
    existing = existing_enrichment_keys()

    valid = []
    duplicates = 0

    for idx, row in enumerate(input_rows, 1):
        row_failures = validate_row(row, packets)
        cid = row.get("candidate_id")

        if cid in existing:
            duplicates += 1
            row_failures.append("duplicate_enriched_candidate")

        if row_failures:
            for f in row_failures:
                failures.append(f"record_{idx}:{f}")
        else:
            valid.append(normalize(row))

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "intake_id": INTAKE_ID,
        "result": result,
        "apply": args.apply,
        "enrichment_file": args.enrichment_file,
        "input_count": len(input_rows),
        "valid_count": len(valid),
        "duplicate_count": duplicates,
        "known_packet_count": len(packets),
        "template": template(packets),
        "enrichments_preview": valid[:10],
        "policy": {
            "sources_jsonl_written": False,
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "enrichment_only": True,
            "requires_revalidation_before_real_source_intake": True,
        },
        "failures": failures,
    }

    report_json, report_md = write_report(payload, args.apply)

    print("research_enriched_candidate_intake =", result)
    print("intake_id =", INTAKE_ID)
    print("enrichment_file =", args.enrichment_file)
    print("input_count =", len(input_rows))
    print("valid_count =", len(valid))
    print("duplicate_count =", duplicates)
    print("known_packet_count =", len(packets))
    print("report_json =", report_json)
    print("report_md =", report_md)
    print("sources_jsonl_written = false")
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

    if not args.apply:
        print("enriched_candidates_written = false")
        print("template_ready = true")
        return 0

    if not valid:
        print("enriched_candidates_written = false")
        print("reason = no_valid_enrichments")
        return 0

    with ENRICHMENTS.open("a", encoding="utf-8") as f:
        for row in valid:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("enriched_candidates_written = true")
    print("enriched_candidates_path =", ENRICHMENTS)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
