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
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PATTERNS = RESEARCH_DIR / "design-patterns.jsonl"

EXTRACTOR_ID = "learning-v2-research-incremental-real-pattern-extractor-v0"

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

def latest_gap_report():
    reports = sorted(REPORT_DIR.glob("research-real-digest-pattern-gap-planner-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def slug(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:80] or "pattern"

def suggested_target_family(topic, principle):
    text = f"{topic} {principle}".lower()

    if "onboarding" in text or "first successful action" in text or "new user" in text:
        return "community.onboarding_experience"

    if "community" in text or "engagement" in text:
        return "community.engagement_path"

    if "content" in text or "hierarchy" in text:
        return "content.information_hierarchy"

    if "conversion" in text or "signup" in text or "parent" in text:
        return "conversion.parent_signup_path"

    if "event" in text or "schedule" in text or "results" in text:
        return "event.information_experience"

    if "mobile" in text or "navigation" in text:
        return "mobile.navigation_experience"

    return f"research.{slug(topic)}"

def existing_pattern_keys():
    rows = load_jsonl(PATTERNS)
    keys = set()
    for r in rows:
        keys.add((
            r.get("digest_id"),
            r.get("principle"),
        ))
        keys.add((
            r.get("query_id"),
            r.get("principle"),
        ))
    return keys

def make_pattern(digest, principle, idx):
    query_id = digest.get("query_id")
    topic = digest.get("topic")
    title = digest.get("title") or digest.get("source_title")
    url = digest.get("url_or_reference") or digest.get("source_url") or digest.get("url")
    digest_id = digest.get("digest_id")
    target_family = suggested_target_family(topic, principle)

    return {
        "pattern_id": f"pattern-{query_id}-{idx}-{slug(principle)}",
        "pattern_source_type": "incremental_real_digest_pattern",
        "digest_id": digest_id,
        "query_id": query_id,
        "topic": topic,
        "title": title,
        "source_title": title,
        "source_type": digest.get("source_type"),
        "publisher_or_author": digest.get("publisher_or_author"),
        "url_or_reference": url,
        "source_url": url,
        "confidence": digest.get("confidence"),
        "principle": principle,
        "claim_summary": digest.get("claim_summary"),
        "supporting_key_claims": digest.get("key_claims") or [],
        "applicability_to_blastjunior": digest.get("applicability_to_blastjunior"),
        "suggested_target_family": target_family,
        "risk": "low",
        "observe_only_first": True,
        "activation_allowed_now": False,
        "recommended_next_step": "run_novelty_guard_before_candidate_activation",
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "created_at": now_iso(),
        "extractor_id": EXTRACTOR_ID,
    }

def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    out_json = REPORT_DIR / f"research-incremental-real-pattern-extractor-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-incremental-real-pattern-extractor-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Incremental Real Pattern Extractor")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- extractor_id: `{EXTRACTOR_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- gap_report: `{payload['gap_report']}`")
    lines.append(f"- input_gap_count: `{payload['input_gap_count']}`")
    lines.append(f"- pattern_count: `{payload['pattern_count']}`")
    lines.append(f"- fresh_pattern_count: `{payload['fresh_pattern_count']}`")
    lines.append(f"- duplicate_pattern_count: `{payload['duplicate_pattern_count']}`")
    lines.append("- business_source_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("")
    lines.append("## Pattern preview")
    lines.append("")
    for p in payload["patterns_preview"]:
        lines.append(f"- `{p.get('query_id')}` target_family=`{p.get('suggested_target_family')}` principle={p.get('principle')}")
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
    ap.add_argument("--apply", action="store_true", help="append incremental patterns to learning-v2/research/design-patterns.jsonl")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    gap_path, gap = latest_gap_report()

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

    if not gap_path:
        failures.append("missing_pattern_gap_report")

    if gap.get("result") != "ok":
        failures.append(f"pattern_gap_report_not_ok:{gap.get('result')}")

    gap_digests = gap.get("pattern_gaps") or []
    if not gap_digests:
        failures.append("no_pattern_gaps_to_process")

    existing = existing_pattern_keys()
    fresh = []
    duplicates = 0

    for digest in gap_digests:
        principles = digest.get("design_principles") or []
        if not principles:
            continue

        for idx, principle in enumerate(principles, 1):
            key1 = (digest.get("digest_id"), principle)
            key2 = (digest.get("query_id"), principle)

            if key1 in existing or key2 in existing:
                duplicates += 1
                continue

            fresh.append(make_pattern(digest, principle, idx))

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "extractor_id": EXTRACTOR_ID,
        "result": result,
        "apply": args.apply,
        "gap_report": str(gap_path) if gap_path else None,
        "input_gap_count": len(gap_digests),
        "pattern_count": len(fresh) + duplicates,
        "fresh_pattern_count": len(fresh),
        "duplicate_pattern_count": duplicates,
        "patterns_preview": fresh[:20],
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "incremental_only": True,
        },
        "failures": failures,
    }

    report_json, report_md = write_report(payload, args.apply)

    print("research_incremental_real_pattern_extractor =", result)
    print("extractor_id =", EXTRACTOR_ID)
    print("pattern_json =", report_json)
    print("pattern_md =", report_md)
    print("gap_report =", gap_path)
    print("input_gap_count =", len(gap_digests))
    print("fresh_pattern_count =", len(fresh))
    print("duplicate_pattern_count =", duplicates)
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if fresh:
        print()
        print("pattern_preview =")
        for p in fresh:
            print(f"- {p.get('query_id')} target_family={p.get('suggested_target_family')} principle={p.get('principle')}")

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

    if not args.apply:
        print("incremental_patterns_written = false")
        return 0

    if not fresh:
        print("incremental_patterns_written = false")
        print("reason = no_fresh_patterns")
        return 0

    with PATTERNS.open("a", encoding="utf-8") as f:
        for p in fresh:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print("incremental_patterns_written = true")
    print("patterns_path =", PATTERNS)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
