#!/usr/bin/env python3
import difflib
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

VALIDATOR_ID = "learning-v2-homepage-onboarding-isolated-post-apply-validator-v0"
TARGET_FILE = WORKSPACE / "public/index.html"
TARGET_REL = "public/index.html"

REQUIRED_MARKERS = [
    "home-onboarding",
    "home-onboarding-title",
    "New to HADO?",
    "Start with one simple path",
    "1. Understand",
    "2. Try",
    "3. Belong",
]

ALLOWED_NEW_MARKERS = [
    "home-onboarding",
    "home-onboarding-title",
    "section-kicker",
    "onboarding-steps",
    "onboarding-step",
    "onboarding-action",
    "New to HADO?",
    "Start with one simple path",
    "See how HADO combines sport, teamwork, and AR technology.",
    "Join a beginner-friendly experience with parents, players, or friends.",
    "Meet the club community, follow events, and find your next match.",
    "Start here",
    "See HADO moments",
    "/join.html",
    "/gallery.html",
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

def latest_apply_report():
    reports = sorted(REPORT_DIR.glob("homepage-onboarding-source-change-apply-apply-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def main():
    apply_path, apply_report = latest_apply_report()

    failures = []
    warnings = []

    if not apply_path:
        failures.append("missing_apply_report")

    if apply_report.get("result") != "ok":
        failures.append(f"apply_report_not_ok:{apply_report.get('result')}")

    if apply_report.get("source_written") is not True:
        failures.append("apply_report_source_written_not_true")

    if apply_report.get("target_file") != TARGET_REL:
        failures.append(f"unexpected_target_file:{apply_report.get('target_file')}")

    backup_path = apply_report.get("backup_path")
    if not backup_path:
        failures.append("missing_backup_path")
        backup = ""
    else:
        bp = Path(backup_path)
        if not bp.exists():
            failures.append(f"backup_not_found:{backup_path}")
            backup = ""
        else:
            backup = bp.read_text(encoding="utf-8", errors="ignore")

    if not TARGET_FILE.exists():
        failures.append("target_file_missing")
        current = ""
    else:
        current = TARGET_FILE.read_text(encoding="utf-8", errors="ignore")

    for marker in REQUIRED_MARKERS:
        if marker not in current:
            failures.append(f"required_marker_missing:{marker}")

    if "home-onboarding" in backup or "home-onboarding-title" in backup:
        failures.append("backup_already_contained_home_onboarding")

    before_lines = backup.splitlines()
    after_lines = current.splitlines()

    diff_lines = list(difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile="backup-before-apply/public/index.html",
        tofile="current/public/index.html",
        lineterm=""
    ))

    added_lines = [line[1:] for line in diff_lines if line.startswith("+") and not line.startswith("+++")]
    removed_lines = [line[1:] for line in diff_lines if line.startswith("-") and not line.startswith("---")]

    # This validator is intentionally strict, but inserting before </main>
    # can appear in unified diff as removing the old closing tag and re-adding it.
    # Allow only structural closing tags if they still exist in the current file.
    allowed_removed = []
    unexpected_removed = []

    for line in removed_lines:
        stripped = line.strip().lower()
        if stripped in ("</main>", "</body>") and stripped in current.lower():
            allowed_removed.append(line)
        else:
            unexpected_removed.append(line)

    if unexpected_removed:
        failures.append(f"isolated_diff_has_unexpected_removed_lines:{len(unexpected_removed)}")

    if not any("home-onboarding" in line for line in added_lines):
        failures.append("isolated_diff_missing_home_onboarding_addition")

    suspicious_added = []
    for line in added_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if any(marker in stripped for marker in ALLOWED_NEW_MARKERS):
            continue
        if stripped in [
            '<section class="home-onboarding" aria-labelledby="home-onboarding-title">',
            '<div class="section-inner">',
            '</div>',
            '</section>',
            '</p>',
            '</main>',
            '<p class="section-kicker">New to HADO?</p>',
            '<h2 id="home-onboarding-title">Start with one simple path</h2>',
            '<div class="onboarding-steps" aria-label="HADO starter steps">',
            '<div class="onboarding-step">',
            '<strong>1. Understand</strong>',
            '<strong>2. Try</strong>',
            '<strong>3. Belong</strong>',
            '<p class="onboarding-action">',
            '<a href="/join.html" class="btn primary">Start here</a>',
            '<a href="/gallery.html" class="btn secondary">See HADO moments</a>',
        ]:
            continue
        suspicious_added.append(stripped)

    if suspicious_added:
        warnings.append(f"suspicious_added_lines:{suspicious_added[:10]}")

    isolated_ok = not failures

    payload = {
        "generated_at": now_iso(),
        "validator_id": VALIDATOR_ID,
        "result": "ok" if isolated_ok else "blocked",
        "apply_report": str(apply_path) if apply_path else None,
        "target_file": TARGET_REL,
        "backup_path": backup_path,
        "required_markers_present": all(m in current for m in REQUIRED_MARKERS),
        "backup_had_onboarding": "home-onboarding" in backup or "home-onboarding-title" in backup,
        "isolated_diff_line_count": len(diff_lines),
        "added_line_count": len(added_lines),
        "removed_line_count": len(removed_lines),
        "allowed_removed_line_count": len(allowed_removed),
        "unexpected_removed_line_count": len(unexpected_removed),
        "isolated_delta_interpretation": "backup_to_current_delta_is_homepage_onboarding_only" if isolated_ok else "backup_to_current_delta_needs_review",
        "global_worktree_dirty_files_are_ignored_here": True,
        "diff_preview": diff_lines[:220],
        "policy": {
            "source_written_by_this_validator": False,
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "isolated_validation_only": True,
        },
        "warnings": warnings,
        "failures": failures,
    }

    out_json = REPORT_DIR / f"homepage-onboarding-isolated-post-apply-validator-{stamp()}.json"
    out_md = REPORT_DIR / f"homepage-onboarding-isolated-post-apply-validator-{stamp()}.md"
    out_diff = REPORT_DIR / f"homepage-onboarding-isolated-post-apply-validator-{stamp()}.diff"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_diff.write_text("\n".join(diff_lines) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Homepage Onboarding Isolated Post-Apply Validator")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- validator_id: `{VALIDATOR_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- target_file: `{TARGET_REL}`")
    lines.append(f"- backup_path: `{backup_path}`")
    lines.append(f"- required_markers_present: `{str(payload['required_markers_present']).lower()}`")
    lines.append(f"- backup_had_onboarding: `{str(payload['backup_had_onboarding']).lower()}`")
    lines.append(f"- isolated_diff_line_count: `{payload['isolated_diff_line_count']}`")
    lines.append(f"- added_line_count: `{payload['added_line_count']}`")
    lines.append(f"- removed_line_count: `{payload['removed_line_count']}`")
    lines.append(f"- allowed_removed_line_count: `{payload['allowed_removed_line_count']}`")
    lines.append(f"- unexpected_removed_line_count: `{payload['unexpected_removed_line_count']}`")
    lines.append(f"- isolated_delta_interpretation: `{payload['isolated_delta_interpretation']}`")
    lines.append("- source_written_by_this_validator: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Diff preview")
    lines.append("")
    lines.append("```diff")
    lines.extend(diff_lines[:220])
    lines.append("```")
    if warnings:
        lines.append("")
        lines.append("## Warnings")
        for w in warnings:
            lines.append(f"- {w}")
    if failures:
        lines.append("")
        lines.append("## Failures")
        for f in failures:
            lines.append(f"- {f}")
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("homepage_onboarding_isolated_post_apply_validator =", payload["result"])
    print("validator_id =", VALIDATOR_ID)
    print("target_file =", TARGET_REL)
    print("apply_report =", apply_path)
    print("backup_path =", backup_path)
    print("validator_json =", out_json)
    print("validator_md =", out_md)
    print("validator_diff =", out_diff)
    print("required_markers_present =", str(payload["required_markers_present"]).lower())
    print("backup_had_onboarding =", str(payload["backup_had_onboarding"]).lower())
    print("isolated_diff_line_count =", len(diff_lines))
    print("added_line_count =", len(added_lines))
    print("removed_line_count =", len(removed_lines))
    print("allowed_removed_line_count =", len(allowed_removed))
    print("unexpected_removed_line_count =", len(unexpected_removed))
    print("isolated_delta_interpretation =", payload["isolated_delta_interpretation"])
    print("global_worktree_dirty_files_are_ignored_here = true")
    print("source_written_by_this_validator = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if warnings:
        print()
        print("warnings:")
        for w in warnings:
            print(" ", w)

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
