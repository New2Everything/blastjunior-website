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

ENRICHMENTS = RESEARCH_DIR / "web-source-candidate-enrichments.jsonl"
REVALIDATIONS = RESEARCH_DIR / "web-source-candidate-revalidations.jsonl"

REVALIDATOR_ID = "learning-v2-research-enriched-candidate-revalidator-v0"

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

def has_blocked_marker(row):
    blob = json.dumps(row, ensure_ascii=False)
    return any(m in blob for m in BLOCKED_MARKERS)

def existing_revalidation_keys():
    rows = load_jsonl(REVALIDATIONS)
    return {
        r.get("enrichment_id")
        for r in rows
        if r.get("enrichment_id")
    }

def build_source_record_draft(e):
    return {
        "query_id": e.get("query_id"),
        "title": e.get("title"),
        "source_type": e.get("source_type_guess"),
        "publisher_or_author": e.get("publisher_or_author"),
        "url_or_reference": e.get("url"),
        "topic": e.get("topic"),
        "claim_summary": e.get("claim_summary"),
        "confidence": e.get("candidate_confidence"),
        "key_claims": e.get("key_claims"),
        "design_principles": e.get("design_principles"),
        "applicability_to_blastjunior": e.get("applicability_to_blastjunior"),
        "retrieved_or_created_at": e.get("retrieved_or_created_at"),
        "notes": "Generated from enriched web source candidate. Must pass learning-v2-research-real-source-intake.py before becoming a real source."
    }

def validate_enrichment(e):
    failures = []
    warnings = []

    required = [
        "enrichment_id",
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

    for f in required:
        if not e.get(f):
            failures.append(f"missing_required_field:{f}")

    url = str(e.get("url") or "")
    if not (url.startswith("http://") or url.startswith("https://")):
        failures.append(f"invalid_url:{url}")

    key_claims = e.get("key_claims")
    if not isinstance(key_claims, list) or len(key_claims) < 2:
        failures.append("key_claims_must_be_list_with_at_least_2_items")

    design_principles = e.get("design_principles")
    if not isinstance(design_principles, list) or len(design_principles) < 2:
        failures.append("design_principles_must_be_list_with_at_least_2_items")

    claim_summary = str(e.get("claim_summary") or "").strip()
    if len(claim_summary) < 40:
        warnings.append("claim_summary_may_be_too_short")

    if e.get("sources_jsonl_written") is True:
        failures.append("enrichment_must_not_claim_sources_jsonl_written")

    if has_blocked_marker(e):
        failures.append("blocked_marker_detected")

    if e.get("requires_revalidation_before_real_source_intake") is not True:
        warnings.append("requires_revalidation_before_real_source_intake_not_true")

    ready = not failures

    return {
        "revalidation_id": f"candidate-revalidation-{e.get('candidate_id')}-{stamp()}",
        "enrichment_id": e.get("enrichment_id"),
        "candidate_id": e.get("candidate_id"),
        "task_id": e.get("task_id"),
        "query_id": e.get("query_id"),
        "topic": e.get("topic"),
        "title": e.get("title"),
        "url": e.get("url"),
        "publisher_or_author": e.get("publisher_or_author"),
        "source_type_guess": e.get("source_type_guess"),
        "candidate_confidence": e.get("candidate_confidence"),
        "decision": "ready_for_real_source_intake" if ready else "rejected",
        "next_step": "run_real_source_intake_dry_run_with_source_record_draft" if ready else "fix_enrichment_record",
        "ready_for_real_source_intake": ready,
        "source_record_draft": build_source_record_draft(e) if ready else None,
        "failures": failures,
        "warnings": warnings,
        "sources_jsonl_written": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "revalidated_at": now_iso(),
        "revalidator_id": REVALIDATOR_ID,
    }

def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    out_json = REPORT_DIR / f"research-enriched-candidate-revalidator-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-enriched-candidate-revalidator-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Enriched Candidate Revalidator")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- revalidator_id: `{REVALIDATOR_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- input_enrichment_count: `{payload['input_enrichment_count']}`")
    lines.append(f"- revalidation_count: `{payload['revalidation_count']}`")
    lines.append(f"- ready_for_real_source_intake_count: `{payload['ready_for_real_source_intake_count']}`")
    lines.append(f"- rejected_count: `{payload['rejected_count']}`")
    lines.append("- sources_jsonl_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Revalidation preview")
    lines.append("")

    for r in payload["revalidations_preview"]:
        lines.append(f"### `{r.get('candidate_id')}`")
        lines.append("")
        lines.append(f"- title: {r.get('title')}")
        lines.append(f"- url: {r.get('url')}")
        lines.append(f"- decision: `{r.get('decision')}`")
        lines.append(f"- next_step: `{r.get('next_step')}`")
        lines.append(f"- ready_for_real_source_intake: `{str(r.get('ready_for_real_source_intake')).lower()}`")
        if r.get("warnings"):
            lines.append("- warnings:")
            for w in r.get("warnings"):
                lines.append(f"  - {w}")
        if r.get("failures"):
            lines.append("- failures:")
            for f in r.get("failures"):
                lines.append(f"  - {f}")
        if r.get("source_record_draft"):
            lines.append("")
            lines.append("#### Source record draft")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(r.get("source_record_draft"), ensure_ascii=False, indent=2))
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
    ap.add_argument("--apply", action="store_true", help="append revalidation records to web-source-candidate-revalidations.jsonl")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    enrichments = load_jsonl(ENRICHMENTS)

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

    if not enrichments:
        failures.append("missing_web_source_candidate_enrichments")

    existing = existing_revalidation_keys()
    fresh = []
    duplicates = 0

    for e in enrichments:
        eid = e.get("enrichment_id")
        if eid in existing:
            duplicates += 1
            continue
        fresh.append(validate_enrichment(e))

    ready_count = sum(1 for r in fresh if r.get("ready_for_real_source_intake"))
    rejected_count = sum(1 for r in fresh if r.get("decision") == "rejected")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "revalidator_id": REVALIDATOR_ID,
        "result": result,
        "apply": args.apply,
        "input_enrichment_count": len(enrichments),
        "revalidation_count": len(fresh),
        "duplicate_revalidation_count": duplicates,
        "ready_for_real_source_intake_count": ready_count,
        "rejected_count": rejected_count,
        "revalidations_preview": fresh[:20],
        "policy": {
            "sources_jsonl_written": False,
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "revalidation_only": True,
        },
        "failures": failures,
    }

    report_json, report_md = write_report(payload, args.apply)

    print("research_enriched_candidate_revalidator =", result)
    print("revalidator_id =", REVALIDATOR_ID)
    print("revalidation_json =", report_json)
    print("revalidation_md =", report_md)
    print("input_enrichment_count =", len(enrichments))
    print("revalidation_count =", len(fresh))
    print("duplicate_revalidation_count =", duplicates)
    print("ready_for_real_source_intake_count =", ready_count)
    print("rejected_count =", rejected_count)
    print("sources_jsonl_written = false")
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    for r in fresh[:10]:
        print()
        print("candidate_id =", r.get("candidate_id"))
        print("query_id =", r.get("query_id"))
        print("topic =", r.get("topic"))
        print("decision =", r.get("decision"))
        print("next_step =", r.get("next_step"))
        print("ready_for_real_source_intake =", r.get("ready_for_real_source_intake"))
        print("warnings =", r.get("warnings"))
        print("failures =", r.get("failures"))

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

    if not args.apply:
        print("candidate_revalidations_written = false")
        return 0

    if not fresh:
        print("candidate_revalidations_written = false")
        print("reason = no_fresh_revalidations")
        return 0

    with REVALIDATIONS.open("a", encoding="utf-8") as f:
        for r in fresh:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("candidate_revalidations_written = true")
    print("candidate_revalidations_path =", REVALIDATIONS)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
