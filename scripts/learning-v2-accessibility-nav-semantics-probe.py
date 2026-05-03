#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FAMILY = "accessibility.navigation_semantics"

SCAN_FILES = [
    WORKSPACE / "components/nav.html",
    WORKSPACE / "public/index.html",
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

def scan_file(path):
    rel = str(path.relative_to(WORKSPACE))
    if not path.exists():
        return [{
            "file": rel,
            "line": None,
            "kind": "missing_file",
            "severity": "warning",
            "text": "",
            "recommendation": "File missing; cannot inspect accessibility semantics.",
        }]

    rows = []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()

    for idx, line in enumerate(lines, 1):
        s = line.strip()
        low = s.lower()

        if "<nav" in low:
            has_label = "aria-label" in low or "aria-labelledby" in low
            rows.append({
                "file": rel,
                "line": idx,
                "kind": "nav_landmark",
                "severity": "ok" if has_label else "review",
                "text": compact(s),
                "recommendation": "Nav landmark has accessible label." if has_label else "Consider aria-label for the main navigation landmark.",
            })

        if "nav-mobile-toggle" in s or "<button" in low and "☰" in s:
            has_aria = "aria-label" in low or "aria-expanded" in low or "aria-controls" in low
            rows.append({
                "file": rel,
                "line": idx,
                "kind": "mobile_menu_button",
                "severity": "review" if not has_aria else "ok",
                "text": compact(s),
                "recommendation": "Mobile menu button should expose aria-label, aria-expanded, and aria-controls before any accessibility claim.",
            })

        if "<a " in low and "href=" in low:
            label_text = re.sub(r"<[^>]+>", " ", s)
            label_text = compact(label_text)
            rows.append({
                "file": rel,
                "line": idx,
                "kind": "nav_or_page_link",
                "severity": "ok" if label_text else "review",
                "text": compact(s),
                "recommendation": "Link has visible text." if label_text else "Link may need accessible text.",
            })

        if "onclick=" in low and "<button" not in low:
            rows.append({
                "file": rel,
                "line": idx,
                "kind": "click_handler_non_button",
                "severity": "review",
                "text": compact(s),
                "recommendation": "Interactive behavior outside button/link semantics should be reviewed.",
            })

    return rows

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

    findings = []
    for p in SCAN_FILES:
        findings.extend(scan_file(p))

    review_count = sum(1 for x in findings if x.get("severity") == "review")
    ok_count = sum(1 for x in findings if x.get("severity") == "ok")
    warning_count = sum(1 for x in findings if x.get("severity") == "warning")

    result = "ok" if not failures else "blocked"

    out_json = REPORT_DIR / f"accessibility-nav-semantics-probe-{stamp()}.json"
    out_md = REPORT_DIR / f"accessibility-nav-semantics-probe-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "probe": "learning-v2-accessibility-nav-semantics-probe",
        "target_family": TARGET_FAMILY,
        "result": result,
        "failures": failures,
        "findings": findings,
        "summary": {
            "total_findings": len(findings),
            "ok_count": ok_count,
            "review_count": review_count,
            "warning_count": warning_count,
        },
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "probe_only": True,
        },
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Accessibility Navigation Semantics Probe")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- total_findings: `{len(findings)}`")
    lines.append(f"- ok_count: `{ok_count}`")
    lines.append(f"- review_count: `{review_count}`")
    lines.append(f"- warning_count: `{warning_count}`")
    lines.append("- source_changed: `false`")
    lines.append("- state_written: `false`")
    lines.append("")
    lines.append("## Findings")
    lines.append("")

    for item in findings:
        lines.append(f"### `{item.get('file')}:{item.get('line')}`")
        lines.append("")
        lines.append(f"- kind: `{item.get('kind')}`")
        lines.append(f"- severity: `{item.get('severity')}`")
        lines.append(f"- recommendation: {item.get('recommendation')}")
        lines.append("")
        lines.append("```html")
        lines.append(item.get("text") or "")
        lines.append("```")
        lines.append("")

    lines.append("## Recommendation")
    lines.append("")
    lines.append("Keep this as observe-only evidence. Do not create an apply executor yet.")
    lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("accessibility_nav_semantics_probe =", result)
    print("target_family =", TARGET_FAMILY)
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("total_findings =", len(findings))
    print("ok_count =", ok_count)
    print("review_count =", review_count)
    print("warning_count =", warning_count)
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if findings:
        print()
        print("review_preview =")
        for x in findings[:10]:
            print(f"- {x.get('file')}:{x.get('line')} {x.get('kind')} {x.get('severity')}")

    if failures:
        print()
        print("failures:")
        for x in failures:
            print(" ", x)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
