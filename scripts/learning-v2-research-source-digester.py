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

SOURCES = RESEARCH_DIR / "sources.jsonl"
TEST_SOURCES = RESEARCH_DIR / "sources-test.jsonl"
DIGESTS = RESEARCH_DIR / "digests.jsonl"
TEST_DIGESTS = RESEARCH_DIR / "digests-test.jsonl"

DIGESTER_ID = "learning-v2-research-source-digester-v0"

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

def make_digest(row):
    key_claims = row.get("key_claims") or []
    design_principles = row.get("design_principles") or []

    return {
        "digest_id": f"digest-{row.get('query_id')}-{stamp()}",
        "query_id": row.get("query_id"),
        "topic": row.get("topic"),
        "title": row.get("title"),
        "source_type": row.get("source_type"),
        "publisher_or_author": row.get("publisher_or_author"),
        "url_or_reference": row.get("url_or_reference"),
        "confidence": row.get("confidence"),
        "claim_summary": row.get("claim_summary"),
        "key_claims": key_claims,
        "design_principles": design_principles,
        "applicability_to_blastjunior": row.get("applicability_to_blastjunior"),
        "digest_summary": (
            f"{row.get('claim_summary')} "
            f"Principles: {'; '.join(design_principles[:3]) if design_principles else 'none'}"
        ),
        "pattern_candidate_ready": bool(design_principles),
        "requires_human_review_before_source_change": True,
        "source_changes_allowed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "digested_at": now_iso(),
        "digester_id": DIGESTER_ID,
    }

def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    mode = "test" if payload["test_mode"] else "real"
    out_json = REPORT_DIR / f"research-source-digester-{mode}-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-source-digester-{mode}-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Research Source Digester v0")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- digester_id: `{DIGESTER_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- test_mode: `{str(payload['test_mode']).lower()}`")
    lines.append(f"- input_count: `{payload['input_count']}`")
    lines.append(f"- digest_count: `{payload['digest_count']}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Digest preview")
    lines.append("")
    for d in payload["digests_preview"]:
        lines.append(f"### `{d.get('digest_id')}`")
        lines.append("")
        lines.append(f"- query_id: `{d.get('query_id')}`")
        lines.append(f"- topic: `{d.get('topic')}`")
        lines.append(f"- confidence: `{d.get('confidence')}`")
        lines.append(f"- pattern_candidate_ready: `{str(d.get('pattern_candidate_ready')).lower()}`")
        lines.append(f"- summary: {d.get('digest_summary')}")
        lines.append("")
    lines.append("## Guardrails")
    lines.append("")
    for k, v in payload["guardrails"].items():
        lines.append(f"- `{k}` = `{str(v).lower()}`")
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
    ap.add_argument("--test-mode", action="store_true", help="read sources-test.jsonl and write digests-test.jsonl when --apply is used")
    ap.add_argument("--apply", action="store_true", help="append digests to digests.jsonl or digests-test.jsonl")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    source_path = TEST_SOURCES if args.test_mode else SOURCES
    target_path = TEST_DIGESTS if args.test_mode else DIGESTS
    sources = load_jsonl(source_path)

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

    if not sources:
        failures.append(f"missing_sources:{source_path}")

    digests = [make_digest(row) for row in sources]
    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "digester_id": DIGESTER_ID,
        "result": result,
        "apply": args.apply,
        "test_mode": args.test_mode,
        "source_path": str(source_path),
        "target_path": str(target_path),
        "input_count": len(sources),
        "digest_count": len(digests),
        "digests_preview": digests[:5],
        "guardrails": {
            "do_not_write_state": True,
            "do_not_modify_website_source": True,
            "do_not_commit": True,
            "do_not_push": True,
            "do_not_deploy": True,
            "digests_are_not_direct_edit_permission": True,
            "pattern_extraction_required_before_target_family": True,
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

    print("research_source_digester =", result)
    print("digester_id =", DIGESTER_ID)
    print("test_mode =", str(args.test_mode).lower())
    print("source_path =", source_path)
    print("target_path =", target_path)
    print("input_count =", len(sources))
    print("digest_count =", len(digests))
    print("report_json =", report_json)
    print("report_md =", report_md)
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
        print("digests_written = false")
        return 0

    with target_path.open("a", encoding="utf-8") as f:
        for d in digests:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    print("digests_written = true")
    print("digests_path =", target_path)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
