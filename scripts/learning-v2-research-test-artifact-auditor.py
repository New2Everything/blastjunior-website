#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
RESEARCH_DIR = BASE / "research"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

AUDITOR_ID = "learning-v2-research-test-artifact-auditor-v0"

PAIRS = [
    {
        "kind": "sources",
        "real": RESEARCH_DIR / "sources.jsonl",
        "test": RESEARCH_DIR / "sources-test.jsonl",
        "test_markers": [
            "manual-test://",
            "test_fixture",
            "Manual test source",
            "Schema validation fixture",
        ],
    },
    {
        "kind": "digests",
        "real": RESEARCH_DIR / "digests.jsonl",
        "test": RESEARCH_DIR / "digests-test.jsonl",
        "test_markers": [
            "manual-test://",
            "test_fixture",
            "Manual test source",
            "digest-rq-accessibility-nav-001",
        ],
    },
    {
        "kind": "design_patterns",
        "real": RESEARCH_DIR / "design-patterns.jsonl",
        "test": RESEARCH_DIR / "design-patterns-test.jsonl",
        "test_markers": [
            "pattern-rq-accessibility-nav-001",
            "Manual source records must be digested",
            "Interactive navigation controls should have explicit semantic meaning",
        ],
    },
    {
        "kind": "target_family_candidates",
        "real": RESEARCH_DIR / "target-family-candidates.jsonl",
        "test": RESEARCH_DIR / "target-family-candidates-test.jsonl",
        "test_markers": [
            "candidate-accessibility.navigation_button_semantics",
            "accessibility.navigation_button_semantics",
            "accessibility_nav_button_probe",
        ],
    },
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        row["_line"] = i
        rows.append(row)
    return rows

def row_has_marker(row, markers):
    blob = json.dumps(row, ensure_ascii=False)
    return any(marker in blob for marker in markers)

def main():
    failures = []
    summaries = []

    for pair in PAIRS:
        real_rows = load_jsonl(pair["real"])
        test_rows = load_jsonl(pair["test"])
        polluted = [r for r in real_rows if row_has_marker(r, pair["test_markers"])]

        if polluted:
            failures.append(f"{pair['kind']}:test_records_found_in_real_store:{len(polluted)}")

        summaries.append({
            "kind": pair["kind"],
            "real_path": str(pair["real"]),
            "test_path": str(pair["test"]),
            "real_exists": pair["real"].exists(),
            "test_exists": pair["test"].exists(),
            "real_count": len(real_rows),
            "test_count": len(test_rows),
            "polluted_real_count": len(polluted),
            "polluted_real_preview": polluted[:5],
        })

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "auditor_id": AUDITOR_ID,
        "result": result,
        "failures": failures,
        "summaries": summaries,
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "audit_only": True,
        },
    }

    out_json = REPORT_DIR / f"research-test-artifact-audit-{stamp()}.json"
    out_md = REPORT_DIR / f"research-test-artifact-audit-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Research Test Artifact Audit")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- auditor_id: `{AUDITOR_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Store summaries")
    lines.append("")
    for s in summaries:
        lines.append(f"### `{s['kind']}`")
        lines.append("")
        lines.append(f"- real_exists: `{str(s['real_exists']).lower()}`")
        lines.append(f"- real_count: `{s['real_count']}`")
        lines.append(f"- test_exists: `{str(s['test_exists']).lower()}`")
        lines.append(f"- test_count: `{s['test_count']}`")
        lines.append(f"- polluted_real_count: `{s['polluted_real_count']}`")
        lines.append("")
    if failures:
        lines.append("## Failures")
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("research_test_artifact_audit =", result)
    print("auditor_id =", AUDITOR_ID)
    print("audit_json =", out_json)
    print("audit_md =", out_md)

    for s in summaries:
        print()
        print("kind =", s["kind"])
        print("real_exists =", s["real_exists"])
        print("real_count =", s["real_count"])
        print("test_exists =", s["test_exists"])
        print("test_count =", s["test_count"])
        print("polluted_real_count =", s["polluted_real_count"])

    print()
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

if __name__ == "__main__":
    main()
