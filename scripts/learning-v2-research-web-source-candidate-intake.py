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

QUEUE = RESEARCH_DIR / "web-source-discovery-queue.jsonl"
CANDIDATES = RESEARCH_DIR / "web-source-candidates.jsonl"

INTAKE_ID = "learning-v2-research-web-source-candidate-intake-v0"

REQUIRED_FIELDS = [
    "task_id",
    "packet_id",
    "request_id",
    "query_id",
    "topic",
    "search_phrase",
    "title",
    "url",
    "publisher_or_author",
    "source_type_guess",
    "why_relevant",
    "candidate_confidence",
]

ALLOWED_CONFIDENCE = ["low", "medium", "medium-high", "high"]

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

def has_blocked_marker(row):
    blob = json.dumps(row, ensure_ascii=False)
    return any(m in blob for m in BLOCKED_MARKERS)

def existing_candidate_keys():
    rows = load_jsonl(CANDIDATES)
    return {
        (r.get("task_id"), r.get("url"))
        for r in rows
        if r.get("task_id") and r.get("url")
    }

def task_lookup():
    rows = load_jsonl(QUEUE)
    return {r.get("task_id"): r for r in rows if r.get("task_id")}

def validate_candidate(row, tasks):
    failures = []

    for f in REQUIRED_FIELDS:
        if not row.get(f):
            failures.append(f"missing_required_field:{f}")

    task_id = row.get("task_id")
    task = tasks.get(task_id)
    if not task:
        failures.append(f"unknown_task_id:{task_id}")
    else:
        for f in ["packet_id", "request_id", "query_id", "topic", "search_phrase"]:
            if row.get(f) != task.get(f):
                failures.append(f"task_mismatch:{f}:candidate={row.get(f)} task={task.get(f)}")

    url = str(row.get("url") or "")
    if not (url.startswith("http://") or url.startswith("https://")):
        failures.append(f"invalid_url:{url}")

    confidence = row.get("candidate_confidence")
    if confidence and confidence not in ALLOWED_CONFIDENCE:
        failures.append(f"invalid_candidate_confidence:{confidence}")

    if row.get("status") == "placeholder_not_a_real_source":
        failures.append("placeholder_candidate_not_allowed")

    if row.get("web_browsed_by_openclaw") is False:
        failures.append("web_browsed_by_openclaw_false_not_allowed_for_real_candidate")

    if row.get("sources_jsonl_written") is True:
        failures.append("candidate_must_not_claim_sources_jsonl_written")

    if has_blocked_marker(row):
        failures.append("blocked_marker_detected")

    return failures

def normalize_candidate(row):
    out = {}
    for f in REQUIRED_FIELDS:
        out[f] = row.get(f)

    out.update({
        "candidate_id": row.get("candidate_id") or f"web-source-candidate-{row.get('query_id')}-{stamp()}",
        "rank": row.get("rank"),
        "requires_validation_before_intake": True,
        "web_browsed_by_openclaw": True,
        "sources_jsonl_written": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "status": "candidate_needs_validation",
        "ingested_at": now_iso(),
        "intake_id": INTAKE_ID,
        "notes": row.get("notes"),
    })

    return out

def template(tasks):
    first_task = next(iter(tasks.values()), {})
    return {
        "task_id": first_task.get("task_id") or "web-discovery-task-...",
        "packet_id": first_task.get("packet_id") or "manual-collection-packet-...",
        "request_id": first_task.get("request_id") or "real-source-request-...",
        "query_id": first_task.get("query_id") or "rq-community-ux-001",
        "topic": first_task.get("topic") or "community-experience",
        "search_phrase": first_task.get("search_phrase") or "community product onboarding UX case study",
        "title": "Real candidate source title",
        "url": "https://example.com/real-source",
        "publisher_or_author": "Publisher or author",
        "source_type_guess": "official guideline / design system / UX case study / paper / website case",
        "why_relevant": "Why this source appears relevant to the packet/query.",
        "candidate_confidence": "medium",
        "web_browsed_by_openclaw": True,
        "sources_jsonl_written": False,
        "notes": "Candidate only. Must be validated before real-source-intake."
    }

def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    out_json = REPORT_DIR / f"research-web-source-candidate-intake-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-web-source-candidate-intake-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Web Source Candidate Intake")
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
    if payload["candidates_preview"]:
        lines.append("## Candidate preview")
        lines.append("")
        for c in payload["candidates_preview"]:
            lines.append(f"- `{c.get('query_id')}` `{c.get('topic')}` — {c.get('title')} / {c.get('url')}")
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
    ap.add_argument("--candidate-file", help="JSON or JSONL candidate records")
    ap.add_argument("--apply", action="store_true", help="append validated candidates to web-source-candidates.jsonl")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    tasks = task_lookup()

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

    if not tasks:
        failures.append("missing_web_discovery_queue_tasks")

    input_rows = load_input_file(args.candidate_file) if args.candidate_file else []
    existing = existing_candidate_keys()

    valid = []
    duplicates = 0

    for idx, row in enumerate(input_rows, 1):
        row_failures = validate_candidate(row, tasks)
        key = (row.get("task_id"), row.get("url"))

        if key in existing:
            duplicates += 1
            row_failures.append("duplicate_web_source_candidate")

        if row_failures:
            for f in row_failures:
                failures.append(f"record_{idx}:{f}")
        else:
            valid.append(normalize_candidate(row))

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "intake_id": INTAKE_ID,
        "result": result,
        "apply": args.apply,
        "candidate_file": args.candidate_file,
        "input_count": len(input_rows),
        "valid_count": len(valid),
        "duplicate_count": duplicates,
        "known_task_count": len(tasks),
        "template": template(tasks),
        "candidates_preview": valid[:10],
        "policy": {
            "sources_jsonl_written": False,
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "candidate_only": True,
            "requires_validation_before_intake": True,
        },
        "failures": failures,
    }

    report_json, report_md = write_report(payload, args.apply)

    print("research_web_source_candidate_intake =", result)
    print("intake_id =", INTAKE_ID)
    print("candidate_file =", args.candidate_file)
    print("input_count =", len(input_rows))
    print("valid_count =", len(valid))
    print("duplicate_count =", duplicates)
    print("known_task_count =", len(tasks))
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
        print("web_source_candidates_written = false")
        print("template_ready = true")
        return 0

    if not valid:
        print("web_source_candidates_written = false")
        print("reason = no_valid_candidates")
        return 0

    with CANDIDATES.open("a", encoding="utf-8") as f:
        for c in valid:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print("web_source_candidates_written = true")
    print("web_source_candidates_path =", CANDIDATES)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
