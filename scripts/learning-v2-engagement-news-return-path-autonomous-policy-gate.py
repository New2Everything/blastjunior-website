#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

GATE_ID = "learning-v2-engagement-news-return-path-autonomous-policy-gate-v0"

TARGET_FAMILY = "community.engagement_path"
TARGET_FILE = "public/news.html"
CHANGE_PLAN_ID = "controlled-change-engagement-news-return-path-cta-v0"

LOW_RISK_ALLOWED_FILES = {
    "public/news.html",
}

BLOCKED_TARGETS = [
    "components/nav.html",
    "components/nav.css",
    "workers/",
    "functions/",
    "src/",
    "api/",
    "wrangler.toml",
    "package.json",
    "package-lock.json",
]

BLOCKED_ADDED_LINE_MARKERS = [
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

REQUIRED_ADDED_MARKERS = [
    "news-engagement-return-path",
    "news-engagement-return-path-title",
    "看完俱乐部动态",
    "下一步可以很简单",
    "看看 HADO 精彩瞬间",
    "回到首页了解如何开始",
    'href="/gallery.html"',
    'href="/index.html"',
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

def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for value in obj.values():
            found = find_key(value, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = find_key(item, key)
            if found is not None:
                return found
    return None

def latest_report(pattern):
    reports = sorted(REPORT_DIR.glob(pattern))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def latest_integrity_report():
    reports = sorted(REPORT_DIR.glob("system-integrity-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def diff_added_lines(diff_text):
    lines = []
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            lines.append(line[1:])
    return lines

def diff_removed_lines(diff_text):
    lines = []
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("-"):
            lines.append(line[1:])
    return lines

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    dry_path, dry = latest_report("engagement-news-return-path-source-change-dry-run-*.json")
    integrity_path, integrity = latest_integrity_report()

    failures = []
    warnings = []

    target_file = dry.get("target_file")
    diff_path = dry.get("diff_path")
    diff_text = ""
    if diff_path and Path(diff_path).exists():
        diff_text = Path(diff_path).read_text(encoding="utf-8", errors="ignore")

    added_lines = diff_added_lines(diff_text)
    removed_lines = diff_removed_lines(diff_text)
    added_text = "\n".join(added_lines)

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if not integrity_path:
        failures.append("missing_latest_system_integrity_report")
    elif integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    integrity_drift_count = integrity.get("drift_count")
    if integrity_drift_count is None:
        integrity_drift_count = find_key(integrity, "drift_count")

    integrity_business_freeze_stable = integrity.get("business_freeze_stable")
    if integrity_business_freeze_stable is None:
        integrity_business_freeze_stable = find_key(integrity, "business_freeze_stable")

    # Some integrity reports print these values from nested step reports rather than storing
    # them as top-level fields. If integrity itself is ok and the nested values are absent,
    # confirm them from the latest drift-audit report before blocking.
    if integrity_drift_count is None or integrity_business_freeze_stable is None:
        drift_reports = sorted(REPORT_DIR.glob("system-drift-audit-*.json"))
        if drift_reports:
            latest_drift = load_json(drift_reports[-1], default={})
            if integrity_drift_count is None:
                integrity_drift_count = latest_drift.get("drift_count")
            if integrity_business_freeze_stable is None:
                integrity_business_freeze_stable = latest_drift.get("business_freeze_stable")

    if integrity_drift_count != 0:
        failures.append(f"drift_count_not_zero:{integrity_drift_count}")

    if integrity_business_freeze_stable is not True:
        failures.append(f"business_freeze_not_stable:{integrity_business_freeze_stable}")

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

    if not dry_path:
        failures.append("missing_engagement_news_return_path_dry_run_report")

    if dry.get("result") != "ok":
        failures.append(f"dry_run_not_ok:{dry.get('result')}")

    if dry.get("target_family") != TARGET_FAMILY:
        failures.append(f"dry_run_target_family_mismatch:{dry.get('target_family')}")

    if dry.get("change_plan_id") != CHANGE_PLAN_ID:
        failures.append(f"dry_run_change_plan_id_mismatch:{dry.get('change_plan_id')}")

    if target_file != TARGET_FILE:
        failures.append(f"dry_run_target_file_mismatch:{target_file}")

    if target_file not in LOW_RISK_ALLOWED_FILES:
        failures.append(f"target_file_not_low_risk_allowed:{target_file}")

    for blocked in BLOCKED_TARGETS:
        if target_file and target_file.startswith(blocked):
            failures.append(f"target_file_blocked:{target_file}")

    if dry.get("source_written") is not False:
        failures.append(f"dry_run_claims_source_written:{dry.get('source_written')}")

    if dry.get("state_written") is not False:
        failures.append(f"dry_run_claims_state_written:{dry.get('state_written')}")

    if dry.get("business_source_written") is not False:
        failures.append(f"dry_run_claims_business_source_written:{dry.get('business_source_written')}")

    if dry.get("changed_in_dry_run") is not True:
        failures.append(f"dry_run_not_changed:{dry.get('changed_in_dry_run')}")

    if dry.get("proposed_contains_required_markers") is not True:
        failures.append(f"dry_run_required_markers_not_true:{dry.get('proposed_contains_required_markers')}")

    if dry.get("removed_line_count") != 0:
        failures.append(f"removed_line_count_not_zero:{dry.get('removed_line_count')}")

    if dry.get("added_line_count", 0) <= 0:
        failures.append(f"added_line_count_not_positive:{dry.get('added_line_count')}")

    if dry.get("added_line_count", 999) > 20:
        failures.append(f"added_line_count_too_large:{dry.get('added_line_count')}")

    if not diff_path:
        failures.append("dry_run_diff_path_missing")
    elif not Path(diff_path).exists():
        failures.append(f"dry_run_diff_file_missing:{diff_path}")

    if not added_lines:
        failures.append("diff_added_lines_missing")

    if removed_lines:
        failures.append(f"diff_removed_lines_present:{len(removed_lines)}")

    for marker in REQUIRED_ADDED_MARKERS:
        if marker not in added_text:
            failures.append(f"added_lines_missing_required_marker:{marker}")

    for marker in BLOCKED_ADDED_LINE_MARKERS:
        if marker.lower() in added_text.lower():
            failures.append(f"blocked_added_line_marker_found:{marker}")

    section_marker = 'class="card news-engagement-return-path"'
    title_marker = 'id="news-engagement-return-path-title"'
    section_marker_count = added_text.count(section_marker)
    title_id_count = added_text.count(title_marker)

    if section_marker_count != 1:
        failures.append(f"unexpected_section_marker_count:{section_marker_count}")

    if title_id_count != 1:
        failures.append(f"unexpected_title_id_count:{title_id_count}")

    autonomous_decision = "allow_next_dry_apply_gate" if not failures else "blocked"
    recommended_next_step = (
        "build_engagement_news_return_path_gate_readiness"
        if autonomous_decision == "allow_next_dry_apply_gate"
        else "stop_and_generate_autonomous_block_report"
    )

    payload = {
        "generated_at": now_iso(),
        "gate_id": GATE_ID,
        "result": "ok" if not failures else "blocked",
        "autonomous_decision": autonomous_decision,
        "recommended_next_step": recommended_next_step,
        "target_family": TARGET_FAMILY,
        "target_file": target_file,
        "change_plan_id": CHANGE_PLAN_ID,
        "dry_run_report": str(dry_path) if dry_path else None,
        "integrity_report": str(integrity_path) if integrity_path else None,
        "decision_basis": {
            "human_review_required": False,
            "machine_policy_gate": True,
            "single_target_file": target_file,
            "page_local_change": target_file in LOW_RISK_ALLOWED_FILES,
            "source_written": dry.get("source_written"),
            "state_written": False,
            "business_source_written": False,
            "added_line_count": dry.get("added_line_count"),
            "removed_line_count": dry.get("removed_line_count"),
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
        "policy": {
            "state_written": False,
            "source_written": False,
            "business_source_written": False,
            "source_change_gate_opened": False,
            "human_review_required": False,
            "machine_policy_gate": True,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "autonomous_gate_only": True,
        },
        "warnings": warnings,
        "failures": failures,
    }

    out_json = REPORT_DIR / f"engagement-news-return-path-autonomous-policy-gate-{stamp()}.json"
    out_md = REPORT_DIR / f"engagement-news-return-path-autonomous-policy-gate-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Engagement News Return Path Autonomous Policy Gate")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- gate_id: `{GATE_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- autonomous_decision: `{autonomous_decision}`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")
    lines.append(f"- target_file: `{target_file}`")
    lines.append("- source_written: `false`")
    lines.append("- state_written: `false`")
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

    print("engagement_news_return_path_autonomous_policy_gate =", payload["result"])
    print("gate_id =", GATE_ID)
    print("target_family =", TARGET_FAMILY)
    print("target_file =", target_file)
    print("dry_run_report =", dry_path)
    print("integrity_report =", integrity_path)
    print("autonomous_decision =", autonomous_decision)
    print("recommended_next_step =", recommended_next_step)
    print("source_written = False")
    print("state_written = False")
    print("business_source_written = False")
    print("source_change_gate_opened = False")
    print("human_review_required = False")
    print("machine_policy_gate = True")
    print("git_commit = False")
    print("git_push = False")
    print("deploy = False")
    print("gate_json =", out_json)
    print("gate_md =", out_md)

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
