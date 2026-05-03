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
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PATTERNS = RESEARCH_DIR / "design-patterns.jsonl"
ARCHIVE = RESEARCH_DIR / "evidence-reinforcements.jsonl"

ARCHIVER_ID = "learning-v2-research-evidence-reinforcement-archive-v0"

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

def latest_guard_report():
    reports = sorted(REPORT_DIR.glob("research-candidate-novelty-guard-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def existing_archive_keys():
    rows = load_jsonl(ARCHIVE)
    keys = set()
    for r in rows:
        keys.add((r.get("target_family"), tuple(r.get("pattern_ids") or [])))
    return keys

def build_records(guard, patterns):
    pattern_by_id = {p.get("pattern_id"): p for p in patterns}
    records = []

    for d in guard.get("decisions") or []:
        if d.get("decision") != "archive_as_evidence_reinforcement":
            continue

        pattern_ids = d.get("pattern_ids") or []
        matched = [pattern_by_id[x] for x in pattern_ids if x in pattern_by_id]

        records.append({
            "archive_id": f"evidence-reinforcement-{d.get('target_family')}-{stamp()}",
            "target_family": d.get("target_family"),
            "topic": d.get("topic"),
            "pattern_count": d.get("pattern_count"),
            "pattern_ids": pattern_ids,
            "principles": d.get("principles") or [],
            "matched_patterns": matched,
            "reason": d.get("reason"),
            "decision": d.get("decision"),
            "activation_allowed": False,
            "archive_status": "evidence_reinforcement_only",
            "source_changes_allowed": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "archived_at": now_iso(),
            "archiver_id": ARCHIVER_ID,
        })

    return records

def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    out_json = REPORT_DIR / f"research-evidence-reinforcement-archive-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-evidence-reinforcement-archive-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Evidence Reinforcement Archive")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- archiver_id: `{ARCHIVER_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- archive_record_count: `{payload['archive_record_count']}`")
    lines.append(f"- duplicate_count: `{payload['duplicate_count']}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Archive preview")
    lines.append("")
    for r in payload["records_preview"]:
        lines.append(f"### `{r.get('target_family')}`")
        lines.append("")
        lines.append(f"- topic: `{r.get('topic')}`")
        lines.append(f"- pattern_count: `{r.get('pattern_count')}`")
        lines.append(f"- activation_allowed: `{str(r.get('activation_allowed')).lower()}`")
        lines.append(f"- archive_status: `{r.get('archive_status')}`")
        lines.append(f"- reason: `{r.get('reason')}`")
        lines.append("")
        for p in r.get("principles") or []:
            lines.append(f"- principle: {p}")
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
    ap.add_argument("--apply", action="store_true", help="append evidence reinforcement records to research/evidence-reinforcements.jsonl")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    guard_path, guard = latest_guard_report()
    patterns = load_jsonl(PATTERNS)

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

    if not guard_path:
        failures.append("missing_candidate_novelty_guard_report")

    if guard.get("result") != "ok":
        failures.append(f"novelty_guard_not_ok:{guard.get('result')}")

    if not patterns:
        failures.append("missing_real_design_patterns")

    records = build_records(guard, patterns)

    guard_decisions = guard.get("decisions") or []
    already_archived_decisions = [
        d for d in guard_decisions
        if d.get("decision") == "already_archived_evidence_reinforcement"
    ]

    if not records and already_archived_decisions:
        no_action_reason = "evidence_already_archived"
    elif not records:
        no_action_reason = None
        failures.append("no_evidence_reinforcement_records_to_archive")
    else:
        no_action_reason = None

    existing = existing_archive_keys()
    fresh = []
    duplicates = 0

    for r in records:
        key = (r.get("target_family"), tuple(r.get("pattern_ids") or []))
        if key in existing:
            duplicates += 1
        else:
            fresh.append(r)

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "archiver_id": ARCHIVER_ID,
        "result": result,
        "apply": args.apply,
        "guard_report": str(guard_path) if guard_path else None,
        "input_pattern_count": len(patterns),
        "archive_record_count": len(records),
        "fresh_record_count": len(fresh),
        "duplicate_count": duplicates,
        "already_archived_decision_count": len(already_archived_decisions),
        "no_action_reason": no_action_reason,
        "records_preview": records[:5],
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "archive_only": True,
        },
        "failures": failures,
    }

    report_json, report_md = write_report(payload, args.apply)

    print("research_evidence_reinforcement_archive =", result)
    print("archiver_id =", ARCHIVER_ID)
    print("guard_report =", guard_path)
    print("archive_json =", report_json)
    print("archive_md =", report_md)
    print("input_pattern_count =", len(patterns))
    print("archive_record_count =", len(records))
    print("fresh_record_count =", len(fresh))
    print("duplicate_count =", duplicates)
    print("already_archived_decision_count =", len(already_archived_decisions))
    print("no_action_reason =", no_action_reason)
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    for r in records:
        print()
        print("target_family =", r.get("target_family"))
        print("topic =", r.get("topic"))
        print("pattern_count =", r.get("pattern_count"))
        print("activation_allowed =", r.get("activation_allowed"))
        print("archive_status =", r.get("archive_status"))

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

    if not args.apply:
        print("evidence_reinforcements_written = false")
        if no_action_reason:
            print("reason =", no_action_reason)
        return 0

    if not fresh:
        print("evidence_reinforcements_written = false")
        print("reason =", no_action_reason or "no_fresh_records")
        return 0

    with ARCHIVE.open("a", encoding="utf-8") as f:
        for r in fresh:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("evidence_reinforcements_written = true")
    print("evidence_reinforcements_path =", ARCHIVE)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
