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

VALIDATOR_ID = "learning-v2-research-web-source-candidate-validator-v0"

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

def existing_validation_keys():
    rows = load_jsonl(VALIDATIONS)
    return {
        r.get("candidate_id")
        for r in rows
        if r.get("candidate_id")
    }

def validate_candidate(c):
    failures = []
    warnings = []

    required = [
        "candidate_id",
        "task_id",
        "query_id",
        "topic",
        "title",
        "url",
        "publisher_or_author",
        "source_type_guess",
        "why_relevant",
        "candidate_confidence",
    ]

    for f in required:
        if not c.get(f):
            failures.append(f"missing_required_field:{f}")

    url = str(c.get("url") or "")
    if not (url.startswith("http://") or url.startswith("https://")):
        failures.append(f"invalid_url:{url}")

    if c.get("status") == "placeholder_not_a_real_source":
        failures.append("placeholder_candidate_not_allowed")

    if c.get("requires_validation_before_intake") is not True:
        warnings.append("requires_validation_before_intake_not_true")

    if c.get("sources_jsonl_written") is True:
        failures.append("candidate_claims_sources_jsonl_written")

    if has_blocked_marker(c):
        failures.append("blocked_marker_detected")

    if not c.get("key_claims"):
        warnings.append("missing_key_claims_for_real_source_intake")

    if not c.get("design_principles"):
        warnings.append("missing_design_principles_for_real_source_intake")

    if not c.get("claim_summary"):
        warnings.append("missing_claim_summary_for_real_source_intake")

    source_ready = (
        not failures
        and c.get("key_claims")
        and c.get("design_principles")
        and c.get("claim_summary")
    )

    if source_ready:
        decision = "ready_for_real_source_intake"
        next_step = "convert_to_real_source_record"
    elif not failures:
        decision = "needs_enrichment_before_real_source_intake"
        next_step = "collect_claim_summary_key_claims_and_design_principles"
    else:
        decision = "rejected"
        next_step = "do_not_promote"

    return {
        "candidate_id": c.get("candidate_id"),
        "task_id": c.get("task_id"),
        "query_id": c.get("query_id"),
        "topic": c.get("topic"),
        "title": c.get("title"),
        "url": c.get("url"),
        "publisher_or_author": c.get("publisher_or_author"),
        "source_type_guess": c.get("source_type_guess"),
        "candidate_confidence": c.get("candidate_confidence"),
        "decision": decision,
        "next_step": next_step,
        "ready_for_real_source_intake": bool(source_ready),
        "failures": failures,
        "warnings": warnings,
        "source_record_draft": build_source_record_draft(c) if source_ready else None,
        "validation_status": "validated" if not failures else "blocked",
        "sources_jsonl_written": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "validated_at": now_iso(),
        "validator_id": VALIDATOR_ID,
    }

def build_source_record_draft(c):
    return {
        "query_id": c.get("query_id"),
        "title": c.get("title"),
        "source_type": c.get("source_type_guess"),
        "publisher_or_author": c.get("publisher_or_author"),
        "url_or_reference": c.get("url"),
        "topic": c.get("topic"),
        "claim_summary": c.get("claim_summary"),
        "confidence": c.get("candidate_confidence"),
        "key_claims": c.get("key_claims"),
        "design_principles": c.get("design_principles"),
        "applicability_to_blastjunior": c.get("applicability_to_blastjunior"),
        "retrieved_or_created_at": c.get("retrieved_or_created_at"),
        "notes": "Generated from validated web source candidate. Must still pass real-source-intake."
    }

def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    out_json = REPORT_DIR / f"research-web-source-candidate-validator-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-web-source-candidate-validator-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Web Source Candidate Validator")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- validator_id: `{VALIDATOR_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- input_candidate_count: `{payload['input_candidate_count']}`")
    lines.append(f"- validation_count: `{payload['validation_count']}`")
    lines.append(f"- ready_for_real_source_intake_count: `{payload['ready_for_real_source_intake_count']}`")
    lines.append(f"- needs_enrichment_count: `{payload['needs_enrichment_count']}`")
    lines.append(f"- rejected_count: `{payload['rejected_count']}`")
    lines.append("- sources_jsonl_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Validation preview")
    lines.append("")

    for v in payload["validations_preview"]:
        lines.append(f"### `{v.get('candidate_id')}`")
        lines.append("")
        lines.append(f"- query_id: `{v.get('query_id')}`")
        lines.append(f"- topic: `{v.get('topic')}`")
        lines.append(f"- title: {v.get('title')}")
        lines.append(f"- decision: `{v.get('decision')}`")
        lines.append(f"- next_step: `{v.get('next_step')}`")
        lines.append(f"- ready_for_real_source_intake: `{str(v.get('ready_for_real_source_intake')).lower()}`")
        if v.get("warnings"):
            lines.append("- warnings:")
            for w in v.get("warnings"):
                lines.append(f"  - {w}")
        if v.get("failures"):
            lines.append("- failures:")
            for f in v.get("failures"):
                lines.append(f"  - {f}")
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
    ap.add_argument("--apply", action="store_true", help="append validation records to web-source-candidate-validations.jsonl")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    candidates = load_jsonl(CANDIDATES)

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

    if not candidates:
        failures.append("missing_web_source_candidates")

    existing = existing_validation_keys()
    fresh = []
    duplicates = 0

    for c in candidates:
        cid = c.get("candidate_id")
        if cid in existing:
            duplicates += 1
            continue
        fresh.append(validate_candidate(c))

    ready_count = sum(1 for v in fresh if v.get("decision") == "ready_for_real_source_intake")
    enrichment_count = sum(1 for v in fresh if v.get("decision") == "needs_enrichment_before_real_source_intake")
    rejected_count = sum(1 for v in fresh if v.get("decision") == "rejected")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "validator_id": VALIDATOR_ID,
        "result": result,
        "apply": args.apply,
        "input_candidate_count": len(candidates),
        "validation_count": len(fresh),
        "duplicate_validation_count": duplicates,
        "ready_for_real_source_intake_count": ready_count,
        "needs_enrichment_count": enrichment_count,
        "rejected_count": rejected_count,
        "validations_preview": fresh[:20],
        "policy": {
            "sources_jsonl_written": False,
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "validation_only": True,
        },
        "failures": failures,
    }

    report_json, report_md = write_report(payload, args.apply)

    print("research_web_source_candidate_validator =", result)
    print("validator_id =", VALIDATOR_ID)
    print("validation_json =", report_json)
    print("validation_md =", report_md)
    print("input_candidate_count =", len(candidates))
    print("validation_count =", len(fresh))
    print("duplicate_validation_count =", duplicates)
    print("ready_for_real_source_intake_count =", ready_count)
    print("needs_enrichment_count =", enrichment_count)
    print("rejected_count =", rejected_count)
    print("sources_jsonl_written = false")
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    for v in fresh[:10]:
        print()
        print("candidate_id =", v.get("candidate_id"))
        print("query_id =", v.get("query_id"))
        print("topic =", v.get("topic"))
        print("decision =", v.get("decision"))
        print("next_step =", v.get("next_step"))
        print("ready_for_real_source_intake =", v.get("ready_for_real_source_intake"))
        print("warnings =", v.get("warnings"))
        print("failures =", v.get("failures"))

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

    if not args.apply:
        print("candidate_validations_written = false")
        return 0

    if not fresh:
        print("candidate_validations_written = false")
        print("reason = no_fresh_validations")
        return 0

    with VALIDATIONS.open("a", encoding="utf-8") as f:
        for v in fresh:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")

    print("candidate_validations_written = true")
    print("candidate_validations_path =", VALIDATIONS)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
