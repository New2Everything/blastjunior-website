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

TARGET_FAMILY = "community.onboarding_experience"
PROBE_ID = "learning-v2-community-onboarding-experience-probe-v0"

SCAN_FILES = [
    WORKSPACE / "public/index.html",
    WORKSPACE / "components/nav.html",
    WORKSPACE / "public/about.html",
    WORKSPACE / "public/join.html",
    WORKSPACE / "public/gallery.html",
]

SIGNALS = {
    "first_successful_action": {
        "required_any": [
            "join", "try", "start", "sign up", "signup", "register", "learn more",
            "加入", "报名", "预约", "体验", "了解", "开始", "联系我们", "联系"
        ],
        "question": "Can a first-time parent or player quickly understand the first useful action to take?",
        "recommendation": "Make the first successful action obvious for new parents and players."
    },
    "onboarding_sequence": {
        "required_groups": [
            ["hado", "HADO", "AR", "未来运动", "科技体育"],
            ["why", "benefit", "growth", "team", "parent", "youth", "为什么", "成长", "团队", "家长", "青少年", "亲子"],
            ["join", "try", "register", "报名", "加入", "体验", "预约"]
        ],
        "question": "Does the page sequence learning, trust, and action in a low-cognitive-load order?",
        "recommendation": "Sequence the page as: what it is → why it matters → who it is for → how to join or try."
    },
    "motivation_to_next_step": {
        "required_any": [
            "parent", "child", "family", "youth", "team", "community", "club",
            "家长", "孩子", "亲子", "青少年", "团队", "社区", "俱乐部", "陪伴", "成长"
        ],
        "question": "Does the page connect parent/player motivation to a practical next step?",
        "recommendation": "Connect parent/player motivation with a clear practical next step."
    }
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def strip_html(text):
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def contains_any(text_lower, terms):
    hits = []
    for term in terms:
        if term.lower() in text_lower:
            hits.append(term)
    return hits

def evaluate_file(path):
    findings = []

    rel = str(path.relative_to(WORKSPACE)) if path.exists() or str(path).startswith(str(WORKSPACE)) else str(path)

    if not path.exists():
        return [{
            "file": rel,
            "dimension": "file_presence",
            "status": "review",
            "severity": "low",
            "evidence": "file not found during observe-only scan",
            "missing": ["file"],
            "recommendation": "Confirm whether this page exists or should be excluded from onboarding scan."
        }]

    raw = path.read_text(encoding="utf-8", errors="ignore")
    text = strip_html(raw)
    lower = text.lower()

    # Dimension 1: first successful action
    cfg = SIGNALS["first_successful_action"]
    hits = contains_any(lower, cfg["required_any"])
    findings.append({
        "file": rel,
        "dimension": "first_successful_action",
        "status": "ok" if hits else "missing",
        "severity": "low" if hits else "medium",
        "evidence": f"matched terms: {hits[:8]}" if hits else "no clear first-action terms found",
        "missing": [] if hits else ["clear join / try / learn-more / contact action"],
        "recommendation": cfg["recommendation"]
    })

    # Dimension 2: onboarding sequence
    cfg = SIGNALS["onboarding_sequence"]
    group_hits = []
    missing_groups = []
    for group in cfg["required_groups"]:
        hits = contains_any(lower, group)
        group_hits.append(hits)
        if not hits:
            missing_groups.append(group)

    if not missing_groups:
        status = "ok"
        severity = "low"
    elif len(missing_groups) == 1:
        status = "review"
        severity = "medium"
    else:
        status = "missing"
        severity = "high"

    findings.append({
        "file": rel,
        "dimension": "onboarding_sequence",
        "status": status,
        "severity": severity,
        "evidence": f"group hits: {group_hits}",
        "missing": missing_groups,
        "recommendation": cfg["recommendation"]
    })

    # Dimension 3: motivation to next step
    cfg = SIGNALS["motivation_to_next_step"]
    hits = contains_any(lower, cfg["required_any"])
    findings.append({
        "file": rel,
        "dimension": "motivation_to_next_step",
        "status": "ok" if hits else "review",
        "severity": "low" if hits else "medium",
        "evidence": f"matched terms: {hits[:8]}" if hits else "no parent/player/community motivation terms found",
        "missing": [] if hits else ["parent / youth / team / community motivation bridge"],
        "recommendation": cfg["recommendation"]
    })

    return findings

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

    all_findings = []
    for path in SCAN_FILES:
        all_findings.extend(evaluate_file(path))

    review_or_missing = [
        f for f in all_findings
        if f.get("status") in ("review", "missing")
    ]

    high_or_medium = [
        f for f in all_findings
        if f.get("severity") in ("high", "medium")
    ]

    payload = {
        "generated_at": now_iso(),
        "probe_id": PROBE_ID,
        "result": "ok" if not failures else "blocked",
        "target_family": TARGET_FAMILY,
        "scan_files": [str(p.relative_to(WORKSPACE)) for p in SCAN_FILES],
        "finding_count": len(all_findings),
        "review_or_missing_count": len(review_or_missing),
        "high_or_medium_count": len(high_or_medium),
        "findings": all_findings,
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "observe_only": True
        },
        "failures": failures
    }

    out_json = REPORT_DIR / f"community-onboarding-experience-probe-{stamp()}.json"
    out_md = REPORT_DIR / f"community-onboarding-experience-probe-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Community Onboarding Experience Probe")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- probe_id: `{PROBE_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- finding_count: `{payload['finding_count']}`")
    lines.append(f"- review_or_missing_count: `{payload['review_or_missing_count']}`")
    lines.append(f"- high_or_medium_count: `{payload['high_or_medium_count']}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Findings")
    lines.append("")

    for f in all_findings:
        lines.append(f"### `{f.get('file')}` / `{f.get('dimension')}`")
        lines.append("")
        lines.append(f"- status: `{f.get('status')}`")
        lines.append(f"- severity: `{f.get('severity')}`")
        lines.append(f"- evidence: {f.get('evidence')}")
        lines.append(f"- recommendation: {f.get('recommendation')}")
        if f.get("missing"):
            lines.append(f"- missing: `{f.get('missing')}`")
        lines.append("")

    if failures:
        lines.append("## Failures")
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("community_onboarding_experience_probe =", payload["result"])
    print("probe_id =", PROBE_ID)
    print("target_family =", TARGET_FAMILY)
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("finding_count =", payload["finding_count"])
    print("review_or_missing_count =", payload["review_or_missing_count"])
    print("high_or_medium_count =", payload["high_or_medium_count"])
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    print()
    print("finding_preview =")
    for f in review_or_missing[:10]:
        print(f"- {f.get('file')} {f.get('dimension')} {f.get('status')} severity={f.get('severity')} missing={f.get('missing')}")

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
