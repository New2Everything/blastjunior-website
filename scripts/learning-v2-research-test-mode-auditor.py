#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
RESEARCH_DIR = BASE / "research"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

SOURCES = RESEARCH_DIR / "sources.jsonl"
TEST_SOURCES = RESEARCH_DIR / "sources-test.jsonl"

AUDITOR_ID = "learning-v2-research-test-mode-auditor-v0"

TEST_MARKERS = [
    "manual-test://",
    "test_fixture",
    "Manual test source",
    "Schema validation fixture",
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

def row_has_test_marker(row):
    blob = json.dumps(row, ensure_ascii=False)
    return any(marker in blob for marker in TEST_MARKERS)

def main():
    real_rows = load_jsonl(SOURCES)
    test_rows = load_jsonl(TEST_SOURCES)

    failures = []
    real_test_rows = [r for r in real_rows if row_has_test_marker(r)]

    if real_test_rows:
        failures.append(f"test_records_found_in_real_sources:{len(real_test_rows)}")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "auditor_id": AUDITOR_ID,
        "result": result,
        "failures": failures,
        "real_sources_path": str(SOURCES),
        "test_sources_path": str(TEST_SOURCES),
        "real_sources_exists": SOURCES.exists(),
        "test_sources_exists": TEST_SOURCES.exists(),
        "real_sources_count": len(real_rows),
        "test_sources_count": len(test_rows),
        "real_test_rows": real_test_rows[:10],
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "audit_only": True,
        },
    }

    out = REPORT_DIR / f"research-test-mode-audit-{stamp()}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("research_test_mode_audit =", result)
    print("auditor_id =", AUDITOR_ID)
    print("audit_report =", out)
    print("real_sources_exists =", SOURCES.exists())
    print("real_sources_count =", len(real_rows))
    print("test_sources_exists =", TEST_SOURCES.exists())
    print("test_sources_count =", len(test_rows))
    print("real_test_record_count =", len(real_test_rows))
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if failures:
        print()
        print("failures:")
        for x in failures:
            print(" ", x)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
