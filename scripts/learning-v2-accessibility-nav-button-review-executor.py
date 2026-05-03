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

TARGET_FAMILY = "accessibility.navigation_button_semantics"

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
    reports = sorted(REPORT_DIR.glob("accessibility-nav-button-semantics-probe-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def build_items(probe):
    findings = probe.get("findings") or []
    items = []

    for x in findings:
        if x.get("severity") != "review":
            continue

        missing = x.get("missing") or []
        item = dict(x)
        item["proposal_type"] = "nav_button_semantics_proposal"
        item["proposal_summary"] = (
            "Proposal-only: document the missing navigation button semantics "
            f"({', '.join(missing)}) before any source-change executor exists."
        )
        item["candidate_fix_shape"] = {
            "add_type_button": "type=\"button\"" in missing or "type" in missing,
            "add_aria_label": "aria-label" in missing,
            "add_aria_expanded": "aria-expanded" in missing,
            "add_aria_controls": "aria-controls" in missing,
            "requires_js_state_review": "aria-expanded" in missing,
            "requires_controlled_menu_id_review": "aria-controls" in missing,
        }
        item["apply_allowed_now"] = False
        item["source_write_risk"] = False
        items.append(item)

    return items

def write_report(state, probe_path, probe, items, apply):
    suffix = "apply" if apply else "dry-run"
    out = REPORT_DIR / f"accessibility-nav-button-review-executor-{suffix}-{stamp()}.md"

    summary = probe.get("summary") or {}

    lines = []
    lines.append("# Accessibility Nav Button Review Executor")
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
    lines.append(f"- missing_field_count: `{summary.get('missing_field_count')}`")
    lines.append("")
    lines.append("## Proposal-only candidates")
    lines.append("")

    if not items:
        lines.append("No review candidate found.")
        lines.append("")
    else:
        for idx, item in enumerate(items, 1):
            missing = ", ".join(item.get("missing") or [])
            lines.append(f"### {idx}. `{item.get('proposal_type')}`")
            lines.append("")
            lines.append(f"- location: `{item.get('file')}:{item.get('line')}`")
            lines.append(f"- kind: `{item.get('kind')}`")
            lines.append(f"- missing: `{missing}`")
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
    lines.append("If applied, it only advances state to `accessibility_nav_button_proposal_ready`.")
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

    print("accessibility_nav_button_review_executor =", "apply" if args.apply else "dry_run")
    print("current_topic =", state.get("current_topic"))
    print("current_stage =", state.get("current_stage"))
    print("current_target_family =", state.get("current_target_family"))

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("current_topic") != "accessibility-basics":
        failures.append(f"current_topic_not_accessibility_basics:{state.get('current_topic')}")

    if state.get("current_stage") != "accessibility_nav_button_review_ready":
        failures.append(f"current_stage_not_accessibility_nav_button_review_ready:{state.get('current_stage')}")

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
        failures.append("missing_accessibility_nav_button_semantics_probe_report")

    if probe.get("target_family") != TARGET_FAMILY:
        failures.append(f"probe_target_family_mismatch:{probe.get('target_family')}")

    items = build_items(probe)
    report_path = write_report(state, probe_path, probe, items, args.apply)

    if failures:
        print("accessibility_nav_button_review_executor_result = blocked")
        print("review_report =", report_path)
        for x in failures:
            print("failure =", x)
        print("state_written = false")
        print("business_source_written = false")
        print("git_commit = false")
        print("git_push = false")
        print("deploy = false")
        raise SystemExit(2)

    print("accessibility_nav_button_review_executor_result =", "proposal_ready" if args.apply else "would_proposal_ready")
    print("latest_probe =", probe_path)
    print("review_report =", report_path)
    print("proposal_candidate_count =", len(items))
    print("would_set_stage = accessibility_nav_button_proposal_ready")
    print("source_changed = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if items:
        top = items[0]
        print("top_candidate =", f"{top.get('file')}:{top.get('line')}")
        print("top_candidate_type =", top.get("proposal_type"))
        print("top_candidate_missing =", top.get("missing"))
        print("top_candidate_apply_allowed_now =", str(top.get("apply_allowed_now")).lower())

    if not args.apply:
        print("state_written = false")
        print("state_updated = false")
        return 0

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "accessibility_nav_button_review_executor",
        "stage_before": "accessibility_nav_button_review_ready",
        "stage_after": "accessibility_nav_button_proposal_ready",
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

    state["last_accessibility_nav_button_review"] = {
        "at": now_iso(),
        "result": "accessibility_nav_button_proposal_ready",
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

    state["current_stage"] = "accessibility_nav_button_proposal_ready"
    state["next_action"] = (
        "Review nav button proposal-only candidates. No website source change is allowed in learning_observe_only."
    )
    state["updated_at"] = now_iso()

    save_json(STATE, state)

    print("state_written = true")
    print("state_updated = true")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
