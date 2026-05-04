#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

GUARD_ID = "learning-v2-business-staging-guard-v0"

EXPECTED_BUSINESS_FILES = {
    "public/index.html",
    "public/gallery.html",
    "public/news.html",
    "public/about.html",
}

FORBIDDEN_STAGED_PREFIXES = (
    "components/",
    "learning-v2/reports/",
    "learning-v2/snapshots/",
    "learning-v2/backups/",
    "learning-v2/freezes/",
    "learning-v2/research/",
    "learning-v2/inbox/",
    "worker/",
    "artifacts/",
    "harness/",
    "blxst/",
)

FORBIDDEN_STAGED_EXACT = {
    "public/styles.css",
    "learning-v2/state.json",
    "learning-v2/experiments.jsonl",
    "learning-v2/outcomes.jsonl",
    "scripts/hourly-optimization.sh",
    "scripts/auto-optimization.sh",
}

FORBIDDEN_PUBLIC_BACKUP_TOKENS = (
    ".bak",
    ".backup",
    "before-color-fix",
)

REQUIRED_MARKERS = {
    "public/index.html": "home-onboarding",
    "public/gallery.html": "gallery-next-action",
    "public/news.html": "news-engagement-return-path",
    "public/about.html": 'data-controlled-create-file="public-about-page"',
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def run(cmd):
    p = subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def staged_name_status():
    rc, out, err = run(["git", "diff", "--cached", "--name-status"])
    if rc != 0:
        raise RuntimeError(err)
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        rows.append({
            "raw": line,
            "status": parts[0] if parts else "",
            "path": parts[-1] if parts else line.strip(),
        })
    return rows

def is_forbidden(path):
    if path in FORBIDDEN_STAGED_EXACT:
        return True
    if any(path.startswith(prefix) for prefix in FORBIDDEN_STAGED_PREFIXES):
        return True
    if path.startswith("public/") and any(token in path for token in FORBIDDEN_PUBLIC_BACKUP_TOKENS):
        return True
    return False

def main():
    failures = []
    warnings = []

    readiness_rc, readiness_out, readiness_err = run(["python3", "scripts/learning-v2-business-release-readiness-guard.py"])

    latest_readiness_reports = sorted(REPORT_DIR.glob("learning-v2-business-release-readiness-guard-*.json"))
    readiness_report_path = latest_readiness_reports[-1] if latest_readiness_reports else None
    readiness_report = {}
    readiness_failures = []
    if readiness_report_path:
        readiness_report = json.loads(readiness_report_path.read_text(encoding="utf-8"))
        readiness_failures = readiness_report.get("failures") or []

    staged = staged_name_status()
    staged_paths = {x["path"] for x in staged}

    readiness_only_blocked_by_index = (
        readiness_rc != 0
        and readiness_failures == ["git_index_not_empty"]
    )

    if readiness_rc != 0 and not readiness_only_blocked_by_index:
        failures.append("business_release_readiness_guard_not_ok")

    staged_forbidden = sorted([p for p in staged_paths if is_forbidden(p)])
    staged_unexpected = sorted(staged_paths - EXPECTED_BUSINESS_FILES)

    if staged_forbidden:
        failures.append("forbidden_paths_staged")

    if staged_unexpected:
        failures.append("unexpected_paths_staged")

    if staged_paths:
        missing_expected_staged = sorted(EXPECTED_BUSINESS_FILES - staged_paths)
        if missing_expected_staged:
            failures.append("partial_business_staging_detected")
    else:
        missing_expected_staged = sorted(EXPECTED_BUSINESS_FILES)
        warnings.append("git_index_empty; ready for guarded business staging")

    marker_results = {}
    for rel, marker in REQUIRED_MARKERS.items():
        path = WORKSPACE / rel
        exists = path.exists()
        text = path.read_text(encoding="utf-8", errors="ignore") if exists else ""
        found = marker in text
        marker_results[rel] = {
            "marker": marker,
            "exists": exists,
            "found": found,
        }
        if not exists:
            failures.append(f"required_file_missing:{rel}")
        elif not found:
            failures.append(f"required_marker_missing:{rel}:{marker}")

    release_rc, release_out, release_err = run(["python3", "scripts/learning-v2-release-gate.py"])
    latest_release_reports = sorted(REPORT_DIR.glob("release-gate-*.json"))
    release_report_path = latest_release_reports[-1] if latest_release_reports else None
    release_summary = {}
    if release_report_path:
        release_summary = json.loads(release_report_path.read_text(encoding="utf-8")).get("summary", {})

    if release_summary.get("ok_for_deploy") is not False:
        failures.append(f"release_gate_deploy_not_false:{release_summary.get('ok_for_deploy')}")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "guard_id": GUARD_ID,
        "result": result,
        "mode": "business_staging_guard",
        "expected_business_files": sorted(EXPECTED_BUSINESS_FILES),
        "staged_count": len(staged_paths),
        "staged_paths": staged,
        "staged_unexpected": staged_unexpected,
        "staged_forbidden": staged_forbidden,
        "missing_expected_staged": missing_expected_staged,
        "marker_results": marker_results,
        "business_release_readiness_rc": readiness_rc,
        "business_release_readiness_failures": readiness_failures,
        "business_release_readiness_only_blocked_by_index": readiness_only_blocked_by_index,
        "release_gate_summary": release_summary,
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "guard_only": True,
            "git_add": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
        "recommended_next_step": (
            "business staged set is clean; commit remains manual-only and push/deploy remain forbidden"
            if result == "ok" and staged_paths
            else "index is clean; guarded business staging may be prepared"
            if result == "ok"
            else "fix staged set before any business commit"
        ),
    }

    out_json = REPORT_DIR / f"learning-v2-business-staging-guard-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-business-staging-guard-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Business Staging Guard")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- mode: `{payload['mode']}`")
    lines.append(f"- staged_count: `{len(staged_paths)}`")
    lines.append("- git_add: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Staged paths")
    if staged:
        for item in staged:
            lines.append(f"- `{item['raw']}`")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Failures")
    if failures:
        for f in failures:
            lines.append(f"- {f}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Warnings")
    if warnings:
        for w in warnings:
            lines.append(f"- {w}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Recommended next step")
    lines.append(payload["recommended_next_step"])
    lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("business_staging_guard =", result)
    print("mode = business_staging_guard")
    print("staged_count =", len(staged_paths))
    print("git_add = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("recommended_next_step =", payload["recommended_next_step"])
    print("report_json =", out_json)
    print("report_md =", out_md)

    if warnings:
        print("warnings =", json.dumps(warnings, ensure_ascii=False))
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
