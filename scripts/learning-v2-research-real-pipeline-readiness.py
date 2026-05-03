#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
RESEARCH_DIR = BASE / "research"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

READINESS_ID = "learning-v2-research-real-pipeline-readiness-v0"

REQUIRED_DISABLED = [
    "simplicity.section_more_anchor",
    "simplicity.dead_or_duplicate_entry_scan",
    "accessibility.navigation_semantics",
    "accessibility.navigation_button_semantics",
]

REQUIRED_BASE = [
    ("queries", "queries.jsonl"),
    ("source_plans", "source-plans.jsonl"),
]

TEST_STORES = [
    ("sources_test", "sources-test.jsonl"),
    ("digests_test", "digests-test.jsonl"),
    ("patterns_test", "design-patterns-test.jsonl"),
    ("candidates_test", "target-family-candidates-test.jsonl"),
]

REAL_STORES = [
    ("sources_real", "sources.jsonl"),
    ("digests_real", "digests.jsonl"),
    ("patterns_real", "design-patterns.jsonl"),
    ("candidates_real", "target-family-candidates.jsonl"),
]

TEST_MARKERS = [
    "manual-test://",
    "test_fixture",
    "Manual test source",
    "Schema validation fixture",
    "accessibility.navigation_button_semantics",
    "accessibility_nav_button_probe",
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

def has_marker(row):
    blob = json.dumps(row, ensure_ascii=False)
    return any(m in blob for m in TEST_MARKERS)

def latest_snapshot(pattern):
    xs = sorted(SNAPSHOT_DIR.glob(pattern))
    return str(xs[-1]) if xs else None

def summarize_store(name, filename):
    p = RESEARCH_DIR / filename
    rows = load_jsonl(p)
    return {
        "name": name,
        "path": str(p),
        "exists": p.exists(),
        "count": len(rows),
        "test_marker_count": sum(1 for r in rows if has_marker(r)),
    }

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    disabled = set(state.get("disabled_target_families") or [])
    track_status = state.get("track_status") or {}

    failures = []
    warnings = []

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

    for fam in REQUIRED_DISABLED:
        if fam not in disabled:
            failures.append(f"required_disabled_family_missing:{fam}")
        ts = track_status.get(fam) or {}
        if ts.get("status") != "complete":
            failures.append(f"required_track_not_complete:{fam}:{ts.get('status')}")

    base_summaries = [summarize_store(k, f) for k, f in REQUIRED_BASE]
    test_summaries = [summarize_store(k, f) for k, f in TEST_STORES]
    real_summaries = [summarize_store(k, f) for k, f in REAL_STORES]

    for s in base_summaries:
        if not s["exists"] or s["count"] <= 0:
            failures.append(f"missing_or_empty_base_research_store:{s['name']}")

    for s in real_summaries:
        if s["count"] > 0:
            warnings.append(f"real_store_not_empty:{s['name']}:{s['count']}")
        if s["test_marker_count"] > 0:
            failures.append(f"test_marker_found_in_real_store:{s['name']}:{s['test_marker_count']}")

    research_snapshot = latest_snapshot("learning-v2-research-loop-first-target-family-closed-*.md")
    if not research_snapshot:
        warnings.append("missing_research_loop_first_target_family_closed_snapshot")

    result = "ok" if not failures else "blocked"
    real_mode_ready = result == "ok"

    payload = {
        "generated_at": now_iso(),
        "readiness_id": READINESS_ID,
        "result": result,
        "real_mode_ready": real_mode_ready,
        "failures": failures,
        "warnings": warnings,
        "control_plane": {
            "mode": policy.get("mode"),
            "system_integrity": integrity.get("result"),
            "drift_count": integrity.get("drift_count"),
            "current_topic": state.get("current_topic"),
            "current_stage": state.get("current_stage"),
            "current_target_family": state.get("current_target_family"),
            "allow_source_changes": state.get("allow_source_changes"),
            "allow_git_commit": state.get("allow_git_commit"),
            "allow_deploy": state.get("allow_deploy"),
        },
        "disabled_target_families": sorted(disabled),
        "base_research_stores": base_summaries,
        "test_research_stores": test_summaries,
        "real_research_stores": real_summaries,
        "research_snapshot": research_snapshot,
        "recommended_next_step": {
            "script": "learning-v2-research-real-source-intake.py",
            "purpose": "Ingest vetted real source records into sources.jsonl after schema validation.",
            "must_default_dry_run": True,
            "must_not_browse_yet": True,
            "must_not_modify_website_source": True,
            "must_not_write_state": True,
        },
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "read_only": True,
        },
    }

    out_json = REPORT_DIR / f"research-real-pipeline-readiness-{stamp()}.json"
    out_md = REPORT_DIR / f"research-real-pipeline-readiness-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Research Real Pipeline Readiness")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- readiness_id: `{READINESS_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- real_mode_ready: `{str(real_mode_ready).lower()}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Control Plane")
    lines.append("")
    for k, v in payload["control_plane"].items():
        lines.append(f"- `{k}` = `{v}`")
    lines.append("")
    lines.append("## Base stores")
    lines.append("")
    for s in base_summaries:
        lines.append(f"- `{s['name']}` exists=`{str(s['exists']).lower()}` count=`{s['count']}`")
    lines.append("")
    lines.append("## Test stores")
    lines.append("")
    for s in test_summaries:
        lines.append(f"- `{s['name']}` exists=`{str(s['exists']).lower()}` count=`{s['count']}`")
    lines.append("")
    lines.append("## Real stores")
    lines.append("")
    for s in real_summaries:
        lines.append(f"- `{s['name']}` exists=`{str(s['exists']).lower()}` count=`{s['count']}` test_marker_count=`{s['test_marker_count']}`")
    lines.append("")
    lines.append("## Recommended next step")
    lines.append("")
    lines.append(f"- script: `{payload['recommended_next_step']['script']}`")
    lines.append(f"- purpose: {payload['recommended_next_step']['purpose']}")
    lines.append("- dry-run first: `true`")
    lines.append("- browse now: `false`")
    lines.append("")

    if failures:
        lines.append("## Failures")
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")

    if warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("research_real_pipeline_readiness =", result)
    print("readiness_id =", READINESS_ID)
    print("real_mode_ready =", str(real_mode_ready).lower())
    print("readiness_json =", out_json)
    print("readiness_md =", out_md)

    print()
    print("=== Control Plane ===")
    for k, v in payload["control_plane"].items():
        print(k, "=", v)

    print()
    print("=== Base Stores ===")
    for s in base_summaries:
        print(f"{s['name']}: exists={s['exists']} count={s['count']}")

    print()
    print("=== Test Stores ===")
    for s in test_summaries:
        print(f"{s['name']}: exists={s['exists']} count={s['count']}")

    print()
    print("=== Real Stores ===")
    for s in real_summaries:
        print(f"{s['name']}: exists={s['exists']} count={s['count']} test_marker_count={s['test_marker_count']}")

    print()
    print("recommended_next_step = learning-v2-research-real-source-intake.py")
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

    if warnings:
        print()
        print("warnings:")
        for w in warnings:
            print(" ", w)

if __name__ == "__main__":
    main()
