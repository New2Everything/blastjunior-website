#!/usr/bin/env python3
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

SCAN_FILES = [
    WORKSPACE / "public/index.html",
    WORKSPACE / "components/nav.html",
    WORKSPACE / "public/styles.css",
]

TARGET_FAMILY = "simplicity.dead_or_duplicate_entry_scan"

KEYWORDS = [
    "首页",
    "赛程",
    "积分榜",
    "战队",
    "选手",
    "英雄",
    "画廊",
    "荣誉",
    "聊天室",
    "加入",
    "加入我们",
    "登录",
    "成员",
    "发送",
    "更多",
    "了解更多",
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

def compact(s, limit=220):
    s = re.sub(r"\s+", " ", s.strip())
    return s[:limit] + "..." if len(s) > limit else s

def classify_line(line):
    s = line.strip()

    if "learning-v2:auto-applied" in s:
        return "already_auto_applied_comment"

    if s.startswith("<!--") and s.endswith("-->"):
        return "html_comment"

    if "<a " in s and "href=" in s:
        return "nav_or_link"

    if "<button" in s:
        return "button"

    if "font-weight" in s or "<div" in s:
        return "visible_text_block"

    if ".section-more" in s:
        return "css_selector"

    return "other"

def extract_labels(line):
    labels = []
    s = re.sub(r"<[^>]+>", " ", line)
    s = s.replace("&gt;", ">")
    s = compact(s, 200)

    for k in KEYWORDS:
        if k in s:
            labels.append(k)

    return labels

def scan():
    records = []
    by_label = defaultdict(list)

    for p in SCAN_FILES:
        rel = str(p.relative_to(WORKSPACE))
        if not p.exists():
            records.append({
                "file": rel,
                "line": None,
                "kind": "missing_file",
                "text": "",
                "labels": [],
            })
            continue

        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()

        for idx, line in enumerate(lines, 1):
            labels = extract_labels(line)
            kind = classify_line(line)

            interesting = bool(labels) or kind in [
                "already_auto_applied_comment",
                "css_selector",
            ]

            if not interesting:
                continue

            rec = {
                "file": rel,
                "line": idx,
                "kind": kind,
                "text": compact(line),
                "labels": labels,
            }
            records.append(rec)

            for label in labels:
                by_label[label].append(rec)

    duplicate_labels = {
        label: rows
        for label, rows in by_label.items()
        if len(rows) >= 2
    }

    auto_applied_comments = [
        r for r in records
        if r["kind"] == "already_auto_applied_comment"
    ]

    weak_candidates = []
    for r in records:
        text = r["text"]
        labels = set(r["labels"])

        if r["kind"] == "css_selector":
            weak_candidates.append({
                **r,
                "reason": "dead_or_leftover_style_selector_possible_after_section_more_removal",
                "source_write_risk": False,
            })

        if "发送" in labels:
            weak_candidates.append({
                **r,
                "reason": "generic_chat_send_button_observed_but_not_safe_for_auto_change",
                "source_write_risk": False,
            })

        if "加入" in labels or "加入我们" in labels:
            weak_candidates.append({
                **r,
                "reason": "join_cta_repeated_across_navigation_and_cta_surface",
                "source_write_risk": False,
            })

        if "画廊" in labels and "auto-applied" in text:
            weak_candidates.append({
                **r,
                "reason": "gallery_entry_already_deprioritized_comment_observed",
                "source_write_risk": False,
            })

    return records, duplicate_labels, auto_applied_comments, weak_candidates

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if TARGET_FAMILY in set(state.get("disabled_target_families") or []):
        failures.append(f"target_family_already_disabled:{TARGET_FAMILY}")

    records, duplicate_labels, auto_applied_comments, weak_candidates = scan()

    result = "ok" if not failures else "blocked"

    report_json = REPORT_DIR / f"dead-duplicate-entry-probe-{stamp()}.json"
    report_md = REPORT_DIR / f"dead-duplicate-entry-probe-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "probe": "learning-v2-dead-duplicate-entry-probe",
        "target_family": TARGET_FAMILY,
        "result": result,
        "failures": failures,
        "records_count": len(records),
        "duplicate_labels": duplicate_labels,
        "auto_applied_comments": auto_applied_comments,
        "weak_candidates": weak_candidates,
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "probe_only": True,
        },
    }

    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Dead / Duplicate Entry Probe")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- records_count: `{len(records)}`")
    lines.append(f"- duplicate_label_count: `{len(duplicate_labels)}`")
    lines.append(f"- auto_applied_comment_count: `{len(auto_applied_comments)}`")
    lines.append(f"- weak_candidate_count: `{len(weak_candidates)}`")
    lines.append("- source_changed: `false`")
    lines.append("- state_written: `false`")
    lines.append("")

    lines.append("## Duplicate labels")
    lines.append("")
    if duplicate_labels:
        for label, rows in duplicate_labels.items():
            lines.append(f"### `{label}`")
            for r in rows:
                lines.append(f"- `{r['file']}:{r['line']}` `{r['kind']}` — {r['text']}")
            lines.append("")
    else:
        lines.append("No duplicate labels found.")
        lines.append("")

    lines.append("## Auto-applied comments")
    lines.append("")
    if auto_applied_comments:
        for r in auto_applied_comments:
            lines.append(f"- `{r['file']}:{r['line']}` — {r['text']}")
    else:
        lines.append("No auto-applied comments found.")
    lines.append("")

    lines.append("## Weak candidates")
    lines.append("")
    if weak_candidates:
        for r in weak_candidates:
            lines.append(f"- `{r['file']}:{r['line']}` `{r['kind']}` — {r['reason']}")
            lines.append(f"  - text: {r['text']}")
    else:
        lines.append("No weak candidates found.")
    lines.append("")

    lines.append("## Recommendation")
    lines.append("")
    lines.append("Use this probe only as read-only evidence. Do not create an apply executor yet.")
    lines.append("Next step should be a dry-run target-family design report.")
    lines.append("")

    report_md.write_text("\n".join(lines), encoding="utf-8")

    print("dead_duplicate_entry_probe =", result)
    print("target_family =", TARGET_FAMILY)
    print("report_json =", report_json)
    print("report_md =", report_md)
    print("records_count =", len(records))
    print("duplicate_label_count =", len(duplicate_labels))
    print("auto_applied_comment_count =", len(auto_applied_comments))
    print("weak_candidate_count =", len(weak_candidates))
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if duplicate_labels:
        print()
        print("duplicate_labels =")
        print(json.dumps({k: len(v) for k, v in duplicate_labels.items()}, ensure_ascii=False))

    if weak_candidates:
        print()
        print("weak_candidate_preview =")
        for r in weak_candidates[:8]:
            print(f"- {r['file']}:{r['line']} {r['reason']}")

    if failures:
        print()
        print("failures:")
        for x in failures:
            print(" ", x)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
