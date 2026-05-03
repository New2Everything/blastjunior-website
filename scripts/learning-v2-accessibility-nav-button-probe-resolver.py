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

def write_report(state, probe_path, probe, stage_after, apply):
    suffix = "apply" if apply else "dry-run"
    out = REPORT_DIR / f"accessibility-nav-button-probe-resolver-{suffix}-{stamp()}.md"

    summary = probe.get("summary") or {}
    findings = probe.get("findings") or []
    review_items = [x for x in findings if x.get("severity") == "review"]

    lines = []
    lines.append("# Accessibility Nav Button Probe Resolver")
    lines.append("")
    lines.append(f"- generated_at: `{now_iso()}`")
    lines.append(f"- mode: `{'apply' if apply else 'dry-run'}`")
    lines.append(f"- topic: `{state.get('current_topic')}`")
    lines.append(f"- stage_before: `{state.get('current_stage')}`")
    lines.append(f"- target_family: `{state.get('current_target_family')}`")
    lines.append(f"- stage_after: `{stage_after}`")
    lines.append(f"- latest_probe: `{probe_path}`")
    lines.append("- source_changed: `false`")
    lines.append(f"- state_written: `{'true' if apply else 'false'}`")
    lines.append("")
    lines.append("## Probe summary")
    lines.append("")
    lines.append(f"- total_findings: `{summary.get('total_findings')}`")
    lines.append(f"- ok_count: `{summary.get('ok_count')}`")
    lines.append(f"- review_count: `{summary.get('review_count')}`")
    lines.append(f"- warning_count: `{summary.get('warning_count')}`")
    lines.append(f"- missing_field_count: `{summary.get('missing_field_count')}`")
    lines.append("")
    lines.append("## Review items")
    lines.append("")
    if review_items:
        for item in review_items[:12]:
            missing = ", ".join(item.get("missing") or [])
            lines.append(f"- `{item.get('file')}:{item.get('line')}` `{item.get('kind')}` missing `{missing}` — {item.get('recommendation')}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Recommendation")
    lines.append("")
    lines.append("Observation evidence exists. Do not apply source changes. Move to review-ready state.")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write resolver result to state.json")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    probe_path, probe = latest_probe_report()

    print("accessibility_nav_button_probe_resolver =", "apply" if args.apply else "dry_run")
    print("current_topic =", state.get("current_topic"))
    print("current_stage =", state.get("current_stage"))
    print("current_target_family =", state.get("current_target_family"))

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("current_topic") != "accessibility-basics":
        failures.append(f"current_topic_not_accessibility_basics:{state.get('current_topic')}")

    if state.get("current_stage") != "accessibility_nav_button_probe":
        failures.append(f"current_stage_not_accessibility_nav_button_probe:{state.get('current_stage')}")

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

    summary = probe.get("summary") or {}
    review_count = int(summary.get("review_count") or 0)
    ok_count = int(summary.get("ok_count") or 0)
    warning_count = int(summary.get("warning_count") or 0)
    missing_field_count = int(summary.get("missing_field_count") or 0)

    if review_count > 0:
        stage_after = "accessibility_nav_button_review_ready"
        resolver_result = "would_review_ready"
    else:
        stage_after = "accessibility_nav_button_track_complete"
        resolver_result = "would_track_complete"

    if failures:
        print("accessibility_nav_button_probe_resolver_result = blocked")
        for x in failures:
            print("failure =", x)
        print("state_written = false")
        print("business_source_written = false")
        print("git_commit = false")
        print("git_push = false")
        print("deploy = false")
        raise SystemExit(2)

    report_path = write_report(state, probe_path, probe, stage_after, args.apply)

    print(
        "accessibility_nav_button_probe_resolver_result =",
        "review_ready" if args.apply and stage_after == "accessibility_nav_button_review_ready" else resolver_result
    )
    print("latest_probe =", probe_path)
    print("resolver_report =", report_path)
    print("would_set_stage =", stage_after)
    print("ok_count =", ok_count)
    print("review_count =", review_count)
    print("warning_count =", warning_count)
    print("missing_field_count =", missing_field_count)
    print("source_changed = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if not args.apply:
        print("state_written = false")
        print("state_updated = false")
        return 0

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "accessibility_nav_button_probe_resolver",
        "stage_before": "accessibility_nav_button_probe",
        "stage_after": stage_after,
        "target_family": TARGET_FAMILY,
        "probe_report": str(probe_path),
        "resolver_report": str(report_path),
        "ok_count": ok_count,
        "review_count": review_count,
        "warning_count": warning_count,
        "missing_field_count": missing_field_count,
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    })

    state["last_accessibility_nav_button_probe_resolver"] = {
        "at": now_iso(),
        "result": stage_after,
        "target_family": TARGET_FAMILY,
        "probe_report": str(probe_path),
        "resolver_report": str(report_path),
        "ok_count": ok_count,
        "review_count": review_count,
        "warning_count": warning_count,
        "missing_field_count": missing_field_count,
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }

    state["current_stage"] = stage_after
    state["next_action"] = (
        "Review nav button semantics evidence and design a proposal-only executor. "
        "Do not modify website source."
    )
    state["updated_at"] = now_iso()

    save_json(STATE, state)

    print("state_written = true")
    print("state_updated = true")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
