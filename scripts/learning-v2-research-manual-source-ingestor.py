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

QUERIES = RESEARCH_DIR / "queries.jsonl"
SOURCE_PLANS = RESEARCH_DIR / "source-plans.jsonl"
SOURCES = RESEARCH_DIR / "sources.jsonl"
TEST_SOURCES = RESEARCH_DIR / "sources-test.jsonl"

INGESTOR_ID = "learning-v2-research-manual-source-ingestor-v0"

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

def load_source_file(path):
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(path))

    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        obj = json.loads(text)
        if isinstance(obj, list):
            return obj
        return [obj]

    rows = []
    for line in text.splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows

def template_record():
    return {
        "query_id": "rq-accessibility-nav-001",
        "title": "Example title of source",
        "source_type": "official guideline / design system / UX case study / paper / website case",
        "publisher_or_author": "Source publisher or author",
        "url_or_reference": "https://example.com/source-or-manual-reference",
        "topic": "accessibility-basics",
        "claim_summary": "One concise summary of what this source claims.",
        "confidence": "medium",
        "key_claims": [
            "Claim 1, paraphrased.",
            "Claim 2, paraphrased."
        ],
        "design_principles": [
            "Reusable design principle extracted from the source."
        ],
        "applicability_to_blastjunior": "Where this may apply on the BLXST / HADO website.",
        "notes": "Manual ingestion note. Do not treat this as direct permission to edit source."
    }

def validate_record(row, known_query_ids):
    failures = []

    for f in REQUIRED_FIELDS:
        if not row.get(f):
            failures.append(f"missing_required_field:{f}")

    qid = row.get("query_id")
    if qid and qid not in known_query_ids:
        failures.append(f"unknown_query_id:{qid}")

    confidence = row.get("confidence")
    if confidence and confidence not in ["low", "medium", "medium-high", "high"]:
        failures.append(f"invalid_confidence:{confidence}")

    return failures

def normalize_record(row):
    out = {}
    for f in REQUIRED_FIELDS + OPTIONAL_FIELDS:
        if f in row:
            out[f] = row.get(f)

    out["ingested_at"] = now_iso()
    out["ingestor_id"] = INGESTOR_ID
    out["ingest_mode"] = "manual"
    out["web_browsed_by_openclaw"] = False
    out["verified_external_source"] = False
    out["source_changes_allowed"] = False
    out["business_source_written"] = False
    out["git_commit"] = False
    out["git_push"] = False
    out["deploy"] = False
    out["status"] = "manual_source_ingested"
    return out

def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    out_json = REPORT_DIR / f"research-manual-source-ingestor-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-manual-source-ingestor-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Manual Source Ingestor v0")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- ingestor_id: `{INGESTOR_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- input_count: `{payload['input_count']}`")
    lines.append(f"- valid_count: `{payload['valid_count']}`")
    lines.append(f"- failure_count: `{len(payload['failures'])}`")
    lines.append("- web_browsed: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Template")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(template_record(), ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Guardrails")
    lines.append("")
    for k, v in payload["guardrails"].items():
        lines.append(f"- `{k}` = `{str(v).lower()}`")
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
    ap.add_argument("--source-file", help="JSON or JSONL file containing manual source records")
    ap.add_argument("--test-mode", action="store_true", help="write to research/sources-test.jsonl instead of sources.jsonl when --apply is used")
    ap.add_argument("--apply", action="store_true", help="append validated records to research/sources.jsonl, or sources-test.jsonl with --test-mode")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    queries = load_jsonl(QUERIES)
    source_plans = load_jsonl(SOURCE_PLANS)
    known_query_ids = {q.get("query_id") for q in queries if q.get("query_id")}

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

    records = load_source_file(args.source_file) if args.source_file else []
    normalized = []

    record_failures = []
    for idx, row in enumerate(records, 1):
        fs = validate_record(row, known_query_ids)
        if fs:
            for f in fs:
                record_failures.append(f"record_{idx}:{f}")
        else:
            normalized.append(normalize_record(row))

    failures.extend(record_failures)

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "ingestor_id": INGESTOR_ID,
        "result": result,
        "apply": args.apply,
        "test_mode": args.test_mode,
        "source_file": args.source_file,
        "input_count": len(records),
        "valid_count": len(normalized),
        "queries_count": len(queries),
        "source_plans_count": len(source_plans),
        "records_preview": normalized[:5],
        "template": template_record(),
        "guardrails": {
            "web_browsed": False,
            "do_not_write_state": True,
            "do_not_modify_website_source": True,
            "do_not_commit": True,
            "do_not_push": True,
            "do_not_deploy": True,
            "manual_sources_are_not_direct_edit_permission": True,
            "manual_sources_must_later_be_digested_before_pattern_extraction": True,
            "test_mode_writes_only_sources_test_jsonl": True,
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

    print("research_manual_source_ingestor =", result)
    print("ingestor_id =", INGESTOR_ID)
    print("source_file =", args.source_file)
    print("test_mode =", str(args.test_mode).lower())
    print("input_count =", len(records))
    print("valid_count =", len(normalized))
    print("report_json =", report_json)
    print("report_md =", report_md)
    print("web_browsed = false")
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
        print("manual_sources_written = false")
        print("template_ready = true")
        return 0

    if not normalized:
        print("manual_sources_written = false")
        print("reason = no_valid_input_records")
        return 0

    target_path = TEST_SOURCES if args.test_mode else SOURCES

    with target_path.open("a", encoding="utf-8") as f:
        for row in normalized:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("manual_sources_written = true")
    print("manual_sources_path =", target_path)
    print("manual_sources_test_mode =", str(args.test_mode).lower())
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
