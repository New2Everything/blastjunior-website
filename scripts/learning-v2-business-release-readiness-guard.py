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

GUARD_ID = "learning-v2-business-release-readiness-guard-v0"

EXPECTED_BUSINESS_DIRTY = {
    "public/gallery.html",
    "public/index.html",
    "public/news.html",
    "public/about.html",
}

REQUIRED_MARKERS = {
    "public/index.html": "home-onboarding",
    "public/gallery.html": "gallery-next-action",
    "public/news.html": "news-engagement-return-path",
    "public/about.html": 'data-controlled-create-file="public-about-page"',
}

FORBIDDEN_PUBLIC_BACKUP_PATTERNS = [
    ".bak",
    ".backup",
    "before-color-fix",
]

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

def git_status_paths(*paths):
    rc, out, err = run(["git", "status", "--short", "--", *paths])
    if rc != 0:
        raise RuntimeError(err)
    return [line for line in out.splitlines() if line.strip()]

def parse_status_line(line):
    # Examples:
    # " M public/index.html"
    # "M  public/gallery.html"
    # "M public/gallery.html"
    # "?? public/about.html"
    code = line[:2]
    path = line[2:].strip()
    return code, path

def main():
    failures = []
    warnings = []

    status_public_components = git_status_paths("public", "components")
    parsed = [parse_status_line(x) for x in status_public_components]

    dirty_paths = {path for code, path in parsed}

    business_dirty = {
        path for path in dirty_paths
        if path.startswith("public/") or path.startswith("components/")
    }

    unexpected_business_dirty = sorted(business_dirty - EXPECTED_BUSINESS_DIRTY)
    missing_expected_dirty = sorted(EXPECTED_BUSINESS_DIRTY - business_dirty)

    if unexpected_business_dirty:
        failures.append("unexpected_business_dirty_paths")

    if missing_expected_dirty:
        failures.append("missing_expected_business_dirty_paths")

    component_dirty = sorted([p for p in dirty_paths if p.startswith("components/")])
    if component_dirty:
        failures.append("components_not_clean")

    if "public/styles.css" in dirty_paths:
        failures.append("public_styles_css_not_clean")

    public_backup_dirty = sorted([
        p for p in dirty_paths
        if p.startswith("public/") and any(token in p for token in FORBIDDEN_PUBLIC_BACKUP_PATTERNS)
    ])
    if public_backup_dirty:
        failures.append("public_backup_files_present")

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

    rc_cached, cached_out, cached_err = run(["git", "diff", "--cached", "--name-status"])
    if rc_cached != 0:
        failures.append("failed_to_read_cached_diff")
    elif cached_out.strip():
        failures.append("git_index_not_empty")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "guard_id": GUARD_ID,
        "result": result,
        "mode": "business_release_readiness_guard",
        "expected_business_dirty": sorted(EXPECTED_BUSINESS_DIRTY),
        "actual_public_components_status": status_public_components,
        "business_dirty": sorted(business_dirty),
        "unexpected_business_dirty": unexpected_business_dirty,
        "missing_expected_dirty": missing_expected_dirty,
        "component_dirty": component_dirty,
        "public_backup_dirty": public_backup_dirty,
        "marker_results": marker_results,
        "git_index_empty": not bool(cached_out.strip()),
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
            "business candidate scope is ready for human review; do not commit/push/deploy"
            if result == "ok"
            else "fix business dirty scope before staging"
        ),
    }

    out_json = REPORT_DIR / f"learning-v2-business-release-readiness-guard-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-business-release-readiness-guard-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Business Release Readiness Guard")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- mode: `{payload['mode']}`")
    lines.append(f"- business_dirty_count: `{len(business_dirty)}`")
    lines.append(f"- git_index_empty: `{str(payload['git_index_empty']).lower()}`")
    lines.append("- git_add: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Business dirty")
    for p in sorted(business_dirty):
        lines.append(f"- `{p}`")
    lines.append("")
    lines.append("## Marker results")
    for rel, info in marker_results.items():
        lines.append(f"- `{rel}` marker=`{info['marker']}` found=`{str(info['found']).lower()}`")
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

    print("business_release_readiness_guard =", result)
    print("mode = business_release_readiness_guard")
    print("business_dirty_count =", len(business_dirty))
    print("git_index_empty =", str(payload["git_index_empty"]).lower())
    print("git_add = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("recommended_next_step =", payload["recommended_next_step"])
    print("report_json =", out_json)
    print("report_md =", out_md)

    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
