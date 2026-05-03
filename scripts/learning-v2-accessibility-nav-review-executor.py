#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FAMILY = "accessibility.navigation_semantics"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def latest_probe_report():
    reports = sorted(REPORT_DIR.glob("accessibility-nav-semantics-probe-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def priority(item):
    kind = item.get("kind")
    line = int(item.get("line") or 0)
    score = 0

    if kind == "mobile_menu_button":
        score += 100
    elif kind == "nav_landmark":
        score += 80
    elif kind == "nav_or_page_link":
        score += 40
    elif kind == "click_handler_non_button":
        score += 60

    return score * 10000 - line

def build_items(probe):
    findings = probe.get("findings") or []
    items = [x for x in findings if x.get("severity") == "review"]

    out = []
    for x in items:
        item = dict(x)
        item["priority_score"] = priority(item)
        kind = item.get("kind")

        if kind == "mobile_menu_button":
            item["proposal_type"] = "mobile_menu_button_semantics_review"
            item["proposal_summary"] = "Review aria-label / aria-expanded / aria-controls for the mobile menu toggle."
        elif kind == "nav_landmark":
            item["proposal_type"] = "nav_landmark_label_review"
            item["proposal_summary"] = "Review whether the main nav landmark needs an aria-label."
        elif kind == "nav_or_page_link":
            item["proposal_type"] = "link_accessible_text_review"
            item["proposal_summary"] = "Review whether link visible text and accessible name are reliable."
        else:
            item["proposal_type"] = "accessibility_semantics_review"
            item["proposal_summary"] = "Manual accessibility semantics review."

        item["apply_allowed_now"] = False
        out.append(item)

    out.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
    return out

def write_report(state, probe_path, probe, items, apply):
    suffix = "apply" if apply else "dry-run"
    out = REPORT_DIR / f"accessibility-nav-review-executor-{suffix}-{stamp()}.md"

    summary = probe.get("summary") or {}

    lines = []
    lines.append("# Accessibility Nav Review Executor")
    lines.append("")
    lines.append(f"- generated_at: `{now_iso()}`")
    lines.append(f"- mode: `{'apply' if apply else 'dry-run'}`")
    lines.append(f"- topic: `{state.get('current_topic')}`")
    lines.append(f"- stage_before: `{state.get('current_stage')}`")
    lines.append(f"- target_family: `{state.get('current_target_family')}`")
    lines.append(f"- latest_probe: `{probe_path}`")
    lines.append("- source_changed: `false`")
    lines.append(f"- state_written: `{'true' if apply else 'false'}`")
    lines.append("")
    lines.append("## Evidence summary")
    lines.append("")
    lines.append(f"- total_findings: `{summary.get('total_findings')}`")
    lines.append(f"- ok_count: `{summary.get('ok_count')}`")
    lines.append(f"- review_count: `{summary.get('review_count')}`")
    lines.append(f"- warning_count: `{summary.get('warning_count')}`")
    lines.append("")
    lines.append("## Proposal-only candidates")
    lines.append("")

    if not items:
        lines.append("No review candidate found.")
        lines.append("")
    else:
        for idx, item in enumerate(items, 1):
            lines.append(f"### {idx}. `{item.get('proposal_type')}`")
            lines.append("")
            lines.append(f"- location: `{item.get('file')}:{item.get('line')}`")
            lines.append(f"- kind: `{item.get('kind')}`")
            lines.append(f"- priority_score: `{item.get('priority_score')}`")
            lines.append(f"- apply_allowed_now: `{str(item.get('apply_allowed_now')).lower()}`")
            lines.append(f"- recommendation: {item.get('recommendation')}")
            lines.append(f"- proposal: {item.get('proposal_summary')}")
            lines.append("")
            lines.append("```html")
            lines.append(item.get("text") or "")
            lines.append("```")
            lines.append("")

    lines.append("## Decision")
    lines.append("")
    lines.append("This executor is proposal-only. It must not modify website source in learning_observe_only.")
    lines.append("If applied, it only advances state to `accessibility_nav_proposal_ready`.")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write proposal-ready state only")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    probe_path, probe = latest_probe_report()

    print("accessibility_nav_review_executor =", "apply" if args.apply else "dry_run")
    print("current_topic =", state.get("current_topic"))
    print("current_stage =", state.get("current_stage"))
    print("current_target_family =", state.get("current_target_family"))

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("current_topic") != "accessibility-basics":
        failures.append(f"current_topic_not_accessibility_basics:{state.get('current_topic')}")

    if state.get("current_stage") != "accessibility_nav_review_ready":
        failures.append(f"current_stage_not_accessibility_nav_review_ready:{state.get('current_stage')}")

    if state.get("current_target_family") != TARGET_FAMILY:
        failures.append(f"target_family_mismatch:{state.get('current_target_family')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if not probe_path:
        failures.append("missing_accessibility_nav_semantics_probe_report")

    if probe.get("target_family") != TARGET_FAMILY:
        failures.append(f"probe_target_family_mismatch:{probe.get('target_family')}")

    items = build_items(probe)
    report_path = write_report(state, probe_path, probe, items, args.apply)

    if failures:
        print("accessibility_nav_review_executor_result = blocked")
        print("review_report =", report_path)
        for x in failures:
            print("failure =", x)
        print("state_written = false")
        print("business_source_written = false")
        print("git_commit = false")
        print("git_push = false")
        print("deploy = false")
        raise SystemExit(2)

    print("accessibility_nav_review_executor_result =", "proposal_ready" if args.apply else "would_proposal_ready")
    print("latest_probe =", probe_path)
    print("review_report =", report_path)
    print("proposal_candidate_count =", len(items))
    print("would_set_stage = accessibility_nav_proposal_ready")
    print("source_changed = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if items:
        top = items[0]
        print("top_candidate =", f"{top.get('file')}:{top.get('line')}")
        print("top_candidate_type =", top.get("proposal_type"))
        print("top_candidate_apply_allowed_now =", str(top.get("apply_allowed_now")).lower())

    if not args.apply:
        print("state_written = false")
        print("state_updated = false")
        return 0

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "accessibility_nav_review_executor",
        "stage_before": "accessibility_nav_review_ready",
        "stage_after": "accessibility_nav_proposal_ready",
        "target_family": TARGET_FAMILY,
        "probe_report": str(probe_path),
        "review_report": str(report_path),
        "proposal_candidate_count": len(items),
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    })

    state["last_accessibility_nav_review"] = {
        "at": now_iso(),
        "result": "accessibility_nav_proposal_ready",
        "target_family": TARGET_FAMILY,
        "probe_report": str(probe_path),
        "review_report": str(report_path),
        "proposal_candidate_count": len(items),
        "top_candidate": items[0] if items else None,
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }

    state["current_stage"] = "accessibility_nav_proposal_ready"
    state["next_action"] = (
        "Review accessibility proposal-only candidates. No website source change is allowed in learning_observe_only."
    )
    state["updated_at"] = now_iso()

    save_json(STATE, state)

    print("state_written = true")
    print("state_updated = true")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
