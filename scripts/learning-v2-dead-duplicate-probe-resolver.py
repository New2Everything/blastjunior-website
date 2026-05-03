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

TARGET_FAMILY = "simplicity.dead_or_duplicate_entry_scan"

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
    reports = sorted(REPORT_DIR.glob("dead-duplicate-entry-probe-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def write_report(state, probe_path, probe, stage_after, apply):
    suffix = "apply" if apply else "dry-run"
    out = REPORT_DIR / f"dead-duplicate-probe-resolver-{suffix}-{stamp()}.md"

    duplicate_labels = probe.get("duplicate_labels") or {}
    auto_applied_comments = probe.get("auto_applied_comments") or []
    weak_candidates = probe.get("weak_candidates") or []

    lines = []
    lines.append("# Dead / Duplicate Probe Resolver")
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
    lines.append(f"- records_count: `{probe.get('records_count')}`")
    lines.append(f"- duplicate_label_count: `{len(duplicate_labels)}`")
    lines.append(f"- auto_applied_comment_count: `{len(auto_applied_comments)}`")
    lines.append(f"- weak_candidate_count: `{len(weak_candidates)}`")
    lines.append("")
    lines.append("## Recommendation")
    lines.append("")
    lines.append("Observation evidence exists. Do not apply source changes. Move to review/design-ready state.")
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

    print("dead_duplicate_probe_resolver =", "apply" if args.apply else "dry_run")
    print("current_topic =", state.get("current_topic"))
    print("current_stage =", state.get("current_stage"))
    print("current_target_family =", state.get("current_target_family"))

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("current_topic") != "simplicity":
        failures.append(f"current_topic_not_simplicity:{state.get('current_topic')}")

    if state.get("current_stage") != "dead_duplicate_probe":
        failures.append(f"current_stage_not_dead_duplicate_probe:{state.get('current_stage')}")

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
        failures.append("missing_dead_duplicate_probe_report")

    if probe.get("target_family") != TARGET_FAMILY:
        failures.append(f"probe_target_family_mismatch:{probe.get('target_family')}")

    duplicate_labels = probe.get("duplicate_labels") or {}
    auto_applied_comments = probe.get("auto_applied_comments") or []
    weak_candidates = probe.get("weak_candidates") or []

    if not duplicate_labels and not auto_applied_comments and not weak_candidates:
        stage_after = "dead_duplicate_track_complete"
        resolver_result = "would_track_complete"
    else:
        stage_after = "dead_duplicate_review_ready"
        resolver_result = "would_review_ready"

    if failures:
        print("dead_duplicate_probe_resolver_result = blocked")
        for x in failures:
            print("failure =", x)
        print("state_written = false")
        print("business_source_written = false")
        print("git_commit = false")
        print("git_push = false")
        print("deploy = false")
        raise SystemExit(2)

    report_path = write_report(state, probe_path, probe, stage_after, args.apply)

    print("dead_duplicate_probe_resolver_result =", "review_ready" if args.apply and stage_after == "dead_duplicate_review_ready" else resolver_result)
    print("latest_probe =", probe_path)
    print("resolver_report =", report_path)
    print("would_set_stage =", stage_after)
    print("duplicate_label_count =", len(duplicate_labels))
    print("auto_applied_comment_count =", len(auto_applied_comments))
    print("weak_candidate_count =", len(weak_candidates))
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
        "executor": "dead_duplicate_probe_resolver",
        "stage_before": "dead_duplicate_probe",
        "stage_after": stage_after,
        "target_family": TARGET_FAMILY,
        "probe_report": str(probe_path),
        "resolver_report": str(report_path),
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    })

    state["last_dead_duplicate_probe_resolver"] = {
        "at": now_iso(),
        "result": stage_after,
        "target_family": TARGET_FAMILY,
        "probe_report": str(probe_path),
        "resolver_report": str(report_path),
        "duplicate_label_count": len(duplicate_labels),
        "auto_applied_comment_count": len(auto_applied_comments),
        "weak_candidate_count": len(weak_candidates),
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }

    state["current_stage"] = stage_after
    state["next_action"] = (
        "Review dead/duplicate entry evidence and design a proposal-only executor. "
        "Do not modify website source."
    )
    state["updated_at"] = now_iso()

    save_json(STATE, state)

    print("state_written = true")
    print("state_updated = true")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
