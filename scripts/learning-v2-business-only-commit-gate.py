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

GATE_ID = "learning-v2-business-only-commit-gate-v0"

EXPECTED_STAGED = {
    "public/about.html",
    "public/gallery.html",
    "public/index.html",
    "public/news.html",
}

REQUIRED_MARKERS = {
    "public/index.html": "home-onboarding",
    "public/gallery.html": "gallery-next-action",
    "public/news.html": "news-engagement-return-path",
    "public/about.html": 'data-controlled-create-file="public-about-page"',
}

FORBIDDEN_PREFIXES = (
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
    "scripts/",
)

FORBIDDEN_EXACT = {
    "public/styles.css",
    "learning-v2/state.json",
    "learning-v2/experiments.jsonl",
    "learning-v2/outcomes.jsonl",
}

FORBIDDEN_PUBLIC_BACKUP_TOKENS = (
    ".bak",
    ".backup",
    "before-color-fix",
)

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

def staged_rows():
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
    if path in FORBIDDEN_EXACT:
        return True
    if any(path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
        return True
    if path.startswith("public/") and any(token in path for token in FORBIDDEN_PUBLIC_BACKUP_TOKENS):
        return True
    return False

def load_latest(pattern):
    files = sorted(REPORT_DIR.glob(pattern))
    if not files:
        return None, {}
    p = files[-1]
    return p, json.loads(p.read_text(encoding="utf-8"))

def main():
    failures = []
    warnings = []

    staging_rc, staging_out, staging_err = run(["python3", "scripts/learning-v2-business-staging-guard.py"])
    staging_report_path, staging_report = load_latest("learning-v2-business-staging-guard-*.json")

    rows = staged_rows()
    staged_paths = {x["path"] for x in rows}

    if staging_rc != 0:
        failures.append("business_staging_guard_not_ok")

    if not staged_paths:
        failures.append("no_staged_files")

    unexpected = sorted(staged_paths - EXPECTED_STAGED)
    missing = sorted(EXPECTED_STAGED - staged_paths)
    forbidden = sorted([p for p in staged_paths if is_forbidden(p)])

    if unexpected:
        failures.append("unexpected_staged_paths")
    if missing:
        failures.append("missing_expected_staged_paths")
    if forbidden:
        failures.append("forbidden_paths_staged")

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
    release_report_path, release_report = load_latest("release-gate-*.json")
    release_summary = release_report.get("summary") or {}
    freeze_compare = release_report.get("freeze_compare") or {}
    freeze_changed = freeze_compare.get("changed") or []

    freeze_changed_only_by_staging_status = (
        bool(freeze_changed)
        and not freeze_compare.get("missing_or_cleaned")
        and not freeze_compare.get("new_business_dirty")
        and all(
            item.get("path") in EXPECTED_STAGED
            and item.get("old_sha256") == item.get("new_sha256")
            for item in freeze_changed
        )
    )

    if release_summary.get("ok_for_system_build") is not True:
        if freeze_changed_only_by_staging_status and staged_paths == EXPECTED_STAGED:
            warnings.append("release gate system build false only because business files are staged; content sha256 is unchanged")
        else:
            failures.append(f"release_gate_system_build_not_ok:{release_summary.get('ok_for_system_build')}")

    if release_summary.get("ok_for_deploy") is not False:
        failures.append(f"release_gate_deploy_not_false:{release_summary.get('ok_for_deploy')}")

    # Normal release gate may still say ok_for_commit=false.
    # This dedicated gate is only a local business-only commit review gate.
    if release_summary.get("ok_for_commit") is not False:
        warnings.append(f"release_gate_commit_unexpectedly_true:{release_summary.get('ok_for_commit')}")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "gate_id": GATE_ID,
        "result": result,
        "mode": "business_only_commit_gate",
        "staged_count": len(staged_paths),
        "staged_rows": rows,
        "expected_staged": sorted(EXPECTED_STAGED),
        "unexpected_staged": unexpected,
        "missing_expected_staged": missing,
        "forbidden_staged": forbidden,
        "marker_results": marker_results,
        "business_staging_guard_rc": staging_rc,
        "business_staging_guard_report": str(staging_report_path) if staging_report_path else None,
        "release_gate_report": str(release_report_path) if release_report_path else None,
        "release_gate_summary": release_summary,
        "freeze_changed_only_by_staging_status": freeze_changed_only_by_staging_status,
        "freeze_compare_changed": freeze_changed,
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "gate_only": True,
            "git_add": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "business_only_commit_review_ready": result == "ok",
        },
        "recommended_next_step": (
            "business-only staged set is ready for manual local commit review; push/deploy remain forbidden"
            if result == "ok"
            else "fix staged set before any business commit"
        ),
    }

    out_json = REPORT_DIR / f"learning-v2-business-only-commit-gate-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-business-only-commit-gate-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Business Only Commit Gate")
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
    if rows:
        for item in rows:
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

    print("business_only_commit_gate =", result)
    print("mode = business_only_commit_gate")
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
