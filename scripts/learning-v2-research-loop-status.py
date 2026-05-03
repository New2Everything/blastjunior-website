#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
RESEARCH_DIR = BASE / "research"
SNAPSHOT_DIR = BASE / "snapshots"

STATUS_ID = "learning-v2-research-loop-status-v0"

ARTIFACTS = [
    ("queries", "queries.jsonl", False),
    ("source_plans", "source-plans.jsonl", False),
    ("sources_real", "sources.jsonl", True),
    ("sources_test", "sources-test.jsonl", False),
    ("digests_real", "digests.jsonl", True),
    ("digests_test", "digests-test.jsonl", False),
    ("patterns_real", "design-patterns.jsonl", True),
    ("patterns_test", "design-patterns-test.jsonl", False),
    ("candidates_real", "target-family-candidates.jsonl", True),
    ("candidates_test", "target-family-candidates-test.jsonl", False),
    ("collection_requests", "real-source-collection-requests.jsonl", False),
    ("manual_collection_packets", "manual-collection-packets.jsonl", False),
    ("web_discovery_queue", "web-source-discovery-queue.jsonl", False),
    ("web_source_candidates", "web-source-candidates.jsonl", False),
    ("web_source_candidate_validations", "web-source-candidate-validations.jsonl", False),
    ("web_source_candidate_enrichment_packets", "web-source-candidate-enrichment-packets.jsonl", False),
    ("web_source_candidate_enrichments", "web-source-candidate-enrichments.jsonl", False),
    ("web_source_candidate_revalidations", "web-source-candidate-revalidations.jsonl", False),
    ("evidence_reinforcements", "evidence-reinforcements.jsonl", False),
]

TEST_MARKERS = {
    "sources_real": [
        "manual-test://",
        "test_fixture",
        "Manual test source",
        "Schema validation fixture",
        "Do not treat as external evidence",
    ],
    "digests_real": [
        "manual-test://",
        "test_fixture",
        "Manual test source",
        "Schema validation fixture",
        "Do not treat as external evidence",
    ],
    "patterns_real": [
        "manual-test://",
        "test_fixture",
        "Manual test source",
        "Schema validation fixture",
        "Do not treat as external evidence",
    ],
    "candidates_real": [
        "manual-test://",
        "test_fixture",
        "Manual test source",
        "Schema validation fixture",
        "Do not treat as external evidence",
    ],
}

EXPECTED_DISABLED = [
    "simplicity.section_more_anchor",
    "simplicity.dead_or_duplicate_entry_scan",
    "accessibility.navigation_semantics",
    "accessibility.navigation_button_semantics",
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

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

def count_jsonl(path):
    return len(load_jsonl(path))

def latest_snapshot(pattern):
    matches = sorted(SNAPSHOT_DIR.glob(pattern))
    return str(matches[-1]) if matches else None

def has_test_marker(row, markers):
    blob = json.dumps(row, ensure_ascii=False)
    return any(m in blob for m in markers)

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    failures = []
    warnings = []

    mode = policy.get("mode")
    disabled = set(state.get("disabled_target_families") or [])
    track_status = state.get("track_status") or {}

    if mode != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{mode}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if state.get("current_topic") is not None:
        warnings.append(f"current_topic_active:{state.get('current_topic')}")

    if state.get("current_stage") is not None:
        warnings.append(f"current_stage_active:{state.get('current_stage')}")

    for family in EXPECTED_DISABLED:
        if family not in disabled:
            failures.append(f"expected_disabled_family_missing:{family}")
        if family not in track_status:
            warnings.append(f"track_status_missing:{family}")
        elif (track_status.get(family) or {}).get("status") != "complete":
            failures.append(f"track_not_complete:{family}")

    artifact_summary = []
    polluted = []

    for key, filename, should_be_real_clean in ARTIFACTS:
        path = RESEARCH_DIR / filename
        rows = load_jsonl(path)
        count = len(rows)

        markers = TEST_MARKERS.get(key, [])
        polluted_rows = []
        if markers:
            polluted_rows = [r for r in rows if has_test_marker(r, markers)]
            if polluted_rows:
                polluted.append((key, len(polluted_rows)))

        artifact_summary.append({
            "key": key,
            "path": str(path),
            "exists": path.exists(),
            "count": count,
            "polluted_test_marker_count": len(polluted_rows),
        })

    for key, count in polluted:
        failures.append(f"test_artifacts_found_in_real_store:{key}:{count}")

    first_research_snapshot = latest_snapshot("learning-v2-research-loop-first-target-family-closed-*.md")
    if not first_research_snapshot:
        warnings.append("missing_research_loop_first_target_family_closed_snapshot")

    result = "ok" if not failures else "blocked"

    print("research_loop_status =", result)
    print("status_id =", STATUS_ID)
    print("generated_at =", now_iso())
    print()
    print("=== Control Plane ===")
    print("mode =", mode)
    print("system_integrity =", integrity.get("result"))
    print("drift_count =", integrity.get("drift_count"))
    print("current_topic =", state.get("current_topic"))
    print("current_stage =", state.get("current_stage"))
    print("current_target_family =", state.get("current_target_family"))
    print("source_changes_allowed =", state.get("allow_source_changes"))
    print("git_commit_allowed =", state.get("allow_git_commit"))
    print("deploy_allowed =", state.get("allow_deploy"))

    print()
    print("=== Completed / Disabled Target Families ===")
    print("disabled_count =", len(disabled))
    for family in sorted(disabled):
        ts = track_status.get(family) or {}
        print(f"- {family}: status={ts.get('status')} completed_at={ts.get('completed_at')}")

    print()
    print("=== Research Artifacts ===")
    for item in artifact_summary:
        print(
            f"- {item['key']}: exists={item['exists']} "
            f"count={item['count']} polluted_test_marker_count={item['polluted_test_marker_count']}"
        )

    print()
    print("=== Snapshots ===")
    print("research_loop_first_target_family_closed =", first_research_snapshot)

    print()
    print("=== Safety Summary ===")
    print("real_store_pollution_count =", len(polluted))
    print("failure_count =", len(failures))
    print("warning_count =", len(warnings))

    if failures:
        print()
        print("failures:")
        for x in failures:
            print(" ", x)

    if warnings:
        print()
        print("warnings:")
        for x in warnings:
            print(" ", x)

    print()
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if failures:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
