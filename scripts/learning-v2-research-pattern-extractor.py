#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
RESEARCH_DIR = BASE / "research"
REPORT_DIR = BASE / "reports"
RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

DIGESTS = RESEARCH_DIR / "digests.jsonl"
TEST_DIGESTS = RESEARCH_DIR / "digests-test.jsonl"
PATTERNS = RESEARCH_DIR / "design-patterns.jsonl"
TEST_PATTERNS = RESEARCH_DIR / "design-patterns-test.jsonl"

EXTRACTOR_ID = "learning-v2-research-pattern-extractor-v0"

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

def slugify(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:80] or "pattern"

def suggested_target_family(topic, query_id, principle):
    if query_id == "rq-accessibility-nav-001":
        return "accessibility.navigation_button_semantics"
    if topic == "mobile-first":
        return "mobile_first.nav_density"
    if topic == "content-hierarchy":
        return "content_hierarchy.homepage_primary_cta"
    if topic == "simplicity":
        return "simplicity.secondary_entry_grouping"
    if topic == "performance-basics":
        return "performance.homepage_interaction_budget"
    return f"{slugify(topic)}.{slugify(principle)[:40]}"

def risk_for(topic, principle):
    p = (principle or "").lower()
    if "semantic" in p or "aria" in p or "navigation" in p:
        return "low"
    if topic in ["accessibility-basics", "performance-basics"]:
        return "low"
    if topic in ["conversion-design", "visual-design", "community-experience"]:
        return "medium"
    return "low-medium"

def pattern_from_digest(digest, index, principle):
    topic = digest.get("topic")
    query_id = digest.get("query_id")
    family = suggested_target_family(topic, query_id, principle)

    return {
        "pattern_id": f"pattern-{slugify(query_id)}-{index}-{slugify(principle)}",
        "source_digest_id": digest.get("digest_id"),
        "query_id": query_id,
        "topic": topic,
        "principle": principle,
        "evidence": digest.get("claim_summary"),
        "source_title": digest.get("title"),
        "source_type": digest.get("source_type"),
        "source_confidence": digest.get("confidence"),
        "applicability": digest.get("applicability_to_blastjunior"),
        "risk": risk_for(topic, principle),
        "suggested_target_family": family,
        "requires_source_change": False,
        "observe_only_first": True,
        "pattern_candidate_ready": True,
        "requires_human_review_before_source_change": True,
        "source_changes_allowed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "extracted_at": now_iso(),
        "extractor_id": EXTRACTOR_ID,
    }

def extract_patterns(digests):
    patterns = []
    for digest in digests:
        if not digest.get("pattern_candidate_ready"):
            continue
        principles = digest.get("design_principles") or []
        for idx, principle in enumerate(principles, 1):
            if str(principle).strip():
                patterns.append(pattern_from_digest(digest, idx, principle))
    return patterns

def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    mode = "test" if payload["test_mode"] else "real"
    out_json = REPORT_DIR / f"research-pattern-extractor-{mode}-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-pattern-extractor-{mode}-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Research Pattern Extractor v0")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- extractor_id: `{EXTRACTOR_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- test_mode: `{str(payload['test_mode']).lower()}`")
    lines.append(f"- input_digest_count: `{payload['input_digest_count']}`")
    lines.append(f"- pattern_count: `{payload['pattern_count']}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Pattern preview")
    lines.append("")
    for p in payload["patterns_preview"]:
        lines.append(f"### `{p.get('pattern_id')}`")
        lines.append("")
        lines.append(f"- topic: `{p.get('topic')}`")
        lines.append(f"- suggested_target_family: `{p.get('suggested_target_family')}`")
        lines.append(f"- risk: `{p.get('risk')}`")
        lines.append(f"- observe_only_first: `{str(p.get('observe_only_first')).lower()}`")
        lines.append(f"- principle: {p.get('principle')}")
        lines.append(f"- evidence: {p.get('evidence')}")
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
    ap.add_argument("--test-mode", action="store_true", help="read digests-test.jsonl and write design-patterns-test.jsonl when --apply is used")
    ap.add_argument("--apply", action="store_true", help="append patterns to design-patterns.jsonl or design-patterns-test.jsonl")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    digest_path = TEST_DIGESTS if args.test_mode else DIGESTS
    target_path = TEST_PATTERNS if args.test_mode else PATTERNS
    digests = load_jsonl(digest_path)
    patterns = extract_patterns(digests)

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

    if not digests:
        failures.append(f"missing_digests:{digest_path}")

    if digests and not patterns:
        failures.append("no_patterns_extracted_from_available_digests")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "extractor_id": EXTRACTOR_ID,
        "result": result,
        "apply": args.apply,
        "test_mode": args.test_mode,
        "digest_path": str(digest_path),
        "target_path": str(target_path),
        "input_digest_count": len(digests),
        "pattern_count": len(patterns),
        "patterns_preview": patterns[:8],
        "guardrails": {
            "do_not_write_state": True,
            "do_not_modify_website_source": True,
            "do_not_commit": True,
            "do_not_push": True,
            "do_not_deploy": True,
            "patterns_are_not_direct_edit_permission": True,
            "patterns_must_become_observe_only_target_family_first": True,
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

    print("research_pattern_extractor =", result)
    print("extractor_id =", EXTRACTOR_ID)
    print("test_mode =", str(args.test_mode).lower())
    print("digest_path =", digest_path)
    print("target_path =", target_path)
    print("input_digest_count =", len(digests))
    print("pattern_count =", len(patterns))
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
        print("patterns_written = false")
        return 0

    with target_path.open("a", encoding="utf-8") as f:
        for p in patterns:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print("patterns_written = true")
    print("patterns_path =", target_path)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
