#!/usr/bin/env python3
import difflib
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

VALIDATOR_ID = "learning-v2-engagement-news-return-path-isolated-post-apply-validator-v0"
TARGET_FILE = "public/news.html"

REQUIRED_MARKERS = [
    "news-engagement-return-path",
    "news-engagement-return-path-title",
    "看完俱乐部动态",
    "下一步可以很简单",
    "看看 HADO 精彩瞬间",
    "回到首页了解如何开始",
    'href="/gallery.html"',
    'href="/index.html"',
]

EXPECTED_SECTION_MARKER = 'class="card news-engagement-return-path"'
EXPECTED_TITLE_MARKER = 'id="news-engagement-return-path-title"'

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def latest_report(pattern):
    reports = sorted(REPORT_DIR.glob(pattern))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    apply_path, apply_report = latest_report("engagement-news-return-path-source-change-apply-apply-*.json")

    failures = []
    warnings = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_closed:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    for key in [
        "source_changes_allowed",
        "git_commit_allowed",
        "git_push_allowed",
        "deploy_allowed",
    ]:
        if policy.get(key) is not False:
            failures.append(f"policy_{key}_not_false:{policy.get(key)}")

    if not apply_path:
        failures.append("missing_apply_report")

    if apply_report.get("result") != "ok":
        failures.append(f"apply_report_not_ok:{apply_report.get('result')}")

    if apply_report.get("apply") is not True:
        failures.append(f"apply_report_apply_not_true:{apply_report.get('apply')}")

    if apply_report.get("target_file") != TARGET_FILE:
        failures.append(f"apply_target_not_news:{apply_report.get('target_file')}")

    if apply_report.get("source_written") is not True:
        failures.append("apply_report_source_written_not_true")

    if apply_report.get("gate_opened_during_apply") is not True:
        failures.append(f"gate_opened_during_apply_not_true:{apply_report.get('gate_opened_during_apply')}")

    if apply_report.get("gate_closed_after_apply") is not True:
        failures.append(f"gate_closed_after_apply_not_true:{apply_report.get('gate_closed_after_apply')}")

    if apply_report.get("git_commit") is not False:
        failures.append(f"git_commit_not_false:{apply_report.get('git_commit')}")

    if apply_report.get("git_push") is not False:
        failures.append(f"git_push_not_false:{apply_report.get('git_push')}")

    if apply_report.get("deploy") is not False:
        failures.append(f"deploy_not_false:{apply_report.get('deploy')}")

    backup_path = apply_report.get("backup_path")
    if not backup_path or not Path(backup_path).exists():
        failures.append(f"backup_missing:{backup_path}")

    target_path = WORKSPACE / TARGET_FILE
    if not target_path.exists():
        failures.append(f"target_missing:{TARGET_FILE}")

    backup_text = Path(backup_path).read_text(encoding="utf-8", errors="ignore") if backup_path and Path(backup_path).exists() else ""
    current_text = target_path.read_text(encoding="utf-8", errors="ignore") if target_path.exists() else ""

    if EXPECTED_SECTION_MARKER in backup_text:
        failures.append("backup_had_news_engagement_return_path")

    if EXPECTED_SECTION_MARKER not in current_text:
        failures.append("current_missing_news_engagement_return_path")

    if EXPECTED_TITLE_MARKER not in current_text:
        failures.append("current_missing_news_engagement_return_path_title")

    for marker in REQUIRED_MARKERS:
        if marker not in current_text:
            failures.append(f"current_missing_required_marker:{marker}")

    section_marker_count = current_text.count(EXPECTED_SECTION_MARKER)
    title_marker_count = current_text.count(EXPECTED_TITLE_MARKER)

    if section_marker_count != 1:
        failures.append(f"unexpected_section_marker_count:{section_marker_count}")

    if title_marker_count != 1:
        failures.append(f"unexpected_title_marker_count:{title_marker_count}")

    diff_lines = list(difflib.unified_diff(
        backup_text.splitlines(),
        current_text.splitlines(),
        fromfile="backup",
        tofile="current",
        lineterm="",
    ))

    added_lines = [
        x for x in diff_lines
        if x.startswith("+") and not x.startswith("+++")
    ]
    removed_lines = [
        x for x in diff_lines
        if x.startswith("-") and not x.startswith("---")
    ]

    added_text = "\n".join(added_lines)
    removed_text = "\n".join(removed_lines)

    if len(added_lines) <= 0:
        failures.append("no_added_lines_detected")

    if len(added_lines) > 20:
        failures.append(f"too_many_added_lines:{len(added_lines)}")

    if removed_lines:
        failures.append(f"unexpected_removed_line_count:{len(removed_lines)}")

    for marker in REQUIRED_MARKERS:
        if marker not in added_text:
            failures.append(f"added_diff_missing_required_marker:{marker}")

    blocked_added_markers = [
        "<script",
        "</script",
        "fetch(",
        "addEventListener",
        "localStorage",
        "blxst_token",
        "D1",
        "KV",
        "R2",
        "wrangler",
        "Worker",
        "login",
        "logout",
        "register",
        "verify",
        "heartbeat",
        "online",
        "onclick=",
        "onsubmit=",
    ]

    for marker in blocked_added_markers:
        if marker.lower() in added_text.lower():
            failures.append(f"blocked_added_marker_found:{marker}")

    if "function renderNews" in added_text or "function renderNews" in removed_text:
        failures.append("diff_touches_renderNews_function")

    if "function handlePublish" in added_text or "function handlePublish" in removed_text:
        failures.append("diff_touches_handlePublish_function")

    if "const API =" in added_text or "const API =" in removed_text:
        failures.append("diff_touches_api_constant")

    isolated_delta_interpretation = (
        "backup_to_current_delta_is_engagement_news_return_path_only"
        if not failures
        else "blocked_or_unclassified_delta"
    )

    result = "ok" if not failures else "blocked"

    out_json = REPORT_DIR / f"engagement-news-return-path-isolated-post-apply-validator-{stamp()}.json"
    out_md = REPORT_DIR / f"engagement-news-return-path-isolated-post-apply-validator-{stamp()}.md"
    out_diff = REPORT_DIR / f"engagement-news-return-path-isolated-post-apply-validator-{stamp()}.diff"

    payload = {
        "generated_at": now_iso(),
        "validator_id": VALIDATOR_ID,
        "result": result,
        "target_file": TARGET_FILE,
        "apply_report": str(apply_path) if apply_path else None,
        "backup_path": backup_path,
        "required_markers_present": all(marker in current_text for marker in REQUIRED_MARKERS),
        "backup_had_news_engagement_return_path": EXPECTED_SECTION_MARKER in backup_text,
        "current_has_news_engagement_return_path": EXPECTED_SECTION_MARKER in current_text,
        "current_has_news_engagement_return_path_title": EXPECTED_TITLE_MARKER in current_text,
        "section_marker_count": section_marker_count,
        "title_marker_count": title_marker_count,
        "added_line_count": len(added_lines),
        "removed_line_count": len(removed_lines),
        "isolated_delta_interpretation": isolated_delta_interpretation,
        "diff_path": str(out_diff),
        "policy": {
            "validator_only": True,
            "state_written": False,
            "source_written": False,
            "business_source_written": False,
            "source_change_gate_opened": False,
            "human_review_required": False,
            "machine_policy_gate": True,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
        "warnings": warnings,
        "failures": failures,
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_diff.write_text("\n".join(diff_lines) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Engagement News Return Path Isolated Post Apply Validator")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- validator_id: `{VALIDATOR_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- target_file: `{TARGET_FILE}`")
    lines.append(f"- added_line_count: `{len(added_lines)}`")
    lines.append(f"- removed_line_count: `{len(removed_lines)}`")
    lines.append(f"- isolated_delta_interpretation: `{isolated_delta_interpretation}`")
    lines.append("- validator_only: `true`")
    lines.append("- state_written: `false`")
    lines.append("- source_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- human_review_required: `false`")
    lines.append("- machine_policy_gate: `true`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    if failures:
        lines.append("")
        lines.append("## Failures")
        for f in failures:
            lines.append(f"- {f}")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("engagement_news_return_path_isolated_post_apply_validator =", result)
    print("target_file =", TARGET_FILE)
    print("apply_report =", str(apply_path) if apply_path else None)
    print("backup_path =", backup_path)
    print("required_markers_present =", payload["required_markers_present"])
    print("backup_had_news_engagement_return_path =", payload["backup_had_news_engagement_return_path"])
    print("current_has_news_engagement_return_path =", payload["current_has_news_engagement_return_path"])
    print("current_has_news_engagement_return_path_title =", payload["current_has_news_engagement_return_path_title"])
    print("section_marker_count =", section_marker_count)
    print("title_marker_count =", title_marker_count)
    print("added_line_count =", len(added_lines))
    print("removed_line_count =", len(removed_lines))
    print("isolated_delta_interpretation =", isolated_delta_interpretation)
    print("state_written = False")
    print("source_written = False")
    print("business_source_written = False")
    print("source_change_gate_opened = False")
    print("human_review_required = False")
    print("machine_policy_gate = True")
    print("git_commit = False")
    print("git_push = False")
    print("deploy = False")
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("diff_path =", out_diff)

    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
