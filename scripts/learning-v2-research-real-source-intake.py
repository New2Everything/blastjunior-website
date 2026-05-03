#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
RESEARCH_DIR = BASE / "research"
REPORT_DIR = BASE / "reports"
RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

QUERIES = RESEARCH_DIR / "queries.jsonl"
SOURCE_PLANS = RESEARCH_DIR / "source-plans.jsonl"
SOURCES = RESEARCH_DIR / "sources.jsonl"

INTAKE_ID = "learning-v2-research-real-source-intake-v0"

REQUIRED_FIELDS = [
    "query_id",
    "title",
    "source_type",
    "publisher_or_author",
    "url_or_reference",
    "topic",
    "claim_summary",
    "confidence",
]

OPTIONAL_FIELDS = [
    "key_claims",
    "design_principles",
    "applicability_to_blastjunior",
    "notes",
    "retrieved_or_created_at",
]

ALLOWED_CONFIDENCE = ["low", "medium", "medium-high", "high"]

TEST_MARKERS = [
    "manual-test://",
    "test_fixture",
    "Manual test source",
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
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
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

def has_test_marker(row):
    blob = json.dumps(row, ensure_ascii=False)
    return any(m in blob for m in TEST_MARKERS)

def template_record():
    return {
        "query_id": "rq-accessibility-nav-001",
        "title": "Real source title",
        "source_type": "official guideline / design system / UX case study / paper / website case",
        "publisher_or_author": "Publisher or author",
        "url_or_reference": "https://example.com/real-source",
        "topic": "accessibility-basics",
        "claim_summary": "A concise paraphrased claim from the source.",
        "confidence": "medium",
        "key_claims": [
            "Paraphrased key claim 1.",
            "Paraphrased key claim 2."
        ],
        "design_principles": [
            "Reusable design principle extracted from this source."
        ],
        "applicability_to_blastjunior": "Where this might apply in BLXST / HADO site experience.",
        "retrieved_or_created_at": "2026-04-28",
        "notes": "Real source record. Must be digested before pattern extraction."
    }

def validate_record(row, known_query_ids, known_topics):
    failures = []

    for field in REQUIRED_FIELDS:
        if not row.get(field):
            failures.append(f"missing_required_field:{field}")

    qid = row.get("query_id")
    if qid and qid not in known_query_ids:
        failures.append(f"unknown_query_id:{qid}")

    topic = row.get("topic")
    if topic and topic not in known_topics:
        failures.append(f"unknown_topic:{topic}")

    confidence = row.get("confidence")
    if confidence and confidence not in ALLOWED_CONFIDENCE:
        failures.append(f"invalid_confidence:{confidence}")

    if has_test_marker(row):
        failures.append("test_marker_detected_in_real_source_record")

    source_type = str(row.get("source_type") or "").lower()
    if source_type == "test_fixture":
        failures.append("source_type_test_fixture_not_allowed_in_real_store")

    url = str(row.get("url_or_reference") or "")
    if url.startswith("manual-test://"):
        failures.append("manual_test_url_not_allowed_in_real_store")

    if not row.get("key_claims"):
        failures.append("missing_optional_but_required_for_real_quality:key_claims")

    if not row.get("design_principles"):
        failures.append("missing_optional_but_required_for_real_quality:design_principles")

    return failures

def normalize_record(row):
    out = {}
    for field in REQUIRED_FIELDS + OPTIONAL_FIELDS:
        if field in row:
            out[field] = row.get(field)

    out["ingested_at"] = now_iso()
    out["intake_id"] = INTAKE_ID
    out["ingest_mode"] = "real_manual_vetted"
    out["web_browsed_by_openclaw"] = False
    out["verified_external_source"] = True
    out["source_changes_allowed"] = False
    out["business_source_written"] = False
    out["git_commit"] = False
    out["git_push"] = False
    out["deploy"] = False
    out["status"] = "real_source_ingested"
    return out

def existing_keys():
    rows = load_jsonl(SOURCES)
    keys = set()
    for r in rows:
        keys.add((r.get("query_id"), r.get("url_or_reference"), r.get("title")))
    return keys

def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    out_json = REPORT_DIR / f"research-real-source-intake-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-real-source-intake-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Real Source Intake")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- intake_id: `{INTAKE_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- input_count: `{payload['input_count']}`")
    lines.append(f"- valid_count: `{payload['valid_count']}`")
    lines.append(f"- duplicate_count: `{payload['duplicate_count']}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- web_browsed_by_openclaw: `false`")
    lines.append("")
    lines.append("## Template")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(template_record(), ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")

    if payload["records_preview"]:
        lines.append("## Records preview")
        lines.append("")
        for r in payload["records_preview"]:
            lines.append(f"### `{r.get('query_id')}` — {r.get('title')}")
            lines.append("")
            lines.append(f"- topic: `{r.get('topic')}`")
            lines.append(f"- source_type: `{r.get('source_type')}`")
            lines.append(f"- confidence: `{r.get('confidence')}`")
            lines.append(f"- claim_summary: {r.get('claim_summary')}")
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
    ap.add_argument("--source-file", help="JSON or JSONL file containing vetted real source records")
    ap.add_argument("--apply", action="store_true", help="append validated real records to research/sources.jsonl")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    queries = load_jsonl(QUERIES)
    source_plans = load_jsonl(SOURCE_PLANS)

    known_query_ids = {q.get("query_id") for q in queries if q.get("query_id")}
    known_topics = {q.get("topic") for q in queries if q.get("topic")}

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
        failures.append("missing_research_queries")

    if not source_plans:
        failures.append("missing_research_source_plans")

    input_rows = load_input_file(args.source_file) if args.source_file else []
    existing = existing_keys()

    valid = []
    duplicates = 0

    for idx, row in enumerate(input_rows, 1):
        row_failures = validate_record(row, known_query_ids, known_topics)

        key = (row.get("query_id"), row.get("url_or_reference"), row.get("title"))
        if key in existing:
            duplicates += 1
            row_failures.append("duplicate_real_source_record")

        if row_failures:
            for f in row_failures:
                failures.append(f"record_{idx}:{f}")
        else:
            valid.append(normalize_record(row))

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "intake_id": INTAKE_ID,
        "result": result,
        "apply": args.apply,
        "source_file": args.source_file,
        "input_count": len(input_rows),
        "valid_count": len(valid),
        "duplicate_count": duplicates,
        "known_query_count": len(known_query_ids),
        "known_topic_count": len(known_topics),
        "records_preview": valid[:5],
        "template": template_record(),
        "guardrails": {
            "do_not_write_state": True,
            "do_not_modify_website_source": True,
            "do_not_commit": True,
            "do_not_push": True,
            "do_not_deploy": True,
            "reject_test_markers_in_real_store": True,
            "real_sources_must_be_digested_before_pattern_extraction": True,
        },
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
        "failures": failures,
    }

    report_json, report_md = write_report(payload, args.apply)

    print("research_real_source_intake =", result)
    print("intake_id =", INTAKE_ID)
    print("source_file =", args.source_file)
    print("input_count =", len(input_rows))
    print("valid_count =", len(valid))
    print("duplicate_count =", duplicates)
    print("report_json =", report_json)
    print("report_md =", report_md)
    print("web_browsed_by_openclaw = false")
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
        print("real_sources_written = false")
        print("template_ready = true")
        return 0

    if not valid:
        print("real_sources_written = false")
        print("reason = no_valid_input_records")
        return 0

    with SOURCES.open("a", encoding="utf-8") as f:
        for row in valid:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("real_sources_written = true")
    print("real_sources_path =", SOURCES)
    return 0

if __name__ == "__main__":
    main()
