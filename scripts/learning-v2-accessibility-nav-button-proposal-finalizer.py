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

def write_report(state, apply):
    suffix = "apply" if apply else "dry-run"
    out = REPORT_DIR / f"accessibility-nav-button-proposal-finalizer-{suffix}-{stamp()}.md"

    review = state.get("last_accessibility_nav_button_review") or {}
    top = review.get("top_candidate") or {}
    missing = ", ".join(top.get("missing") or [])

    lines = []
    lines.append("# Accessibility Nav Button Proposal Finalizer")
    lines.append("")
    lines.append(f"- generated_at: `{now_iso()}`")
    lines.append(f"- mode: `{'apply' if apply else 'dry-run'}`")
    lines.append(f"- topic: `{state.get('current_topic')}`")
    lines.append(f"- stage_before: `{state.get('current_stage')}`")
    lines.append(f"- target_family: `{state.get('current_target_family')}`")
    lines.append("- source_changed: `false`")
    lines.append(f"- state_written: `{'true' if apply else 'false'}`")
    lines.append("")
    lines.append("## Proposal summary")
    lines.append("")
    lines.append(f"- proposal_candidate_count: `{review.get('proposal_candidate_count')}`")
    lines.append(f"- top_candidate: `{top.get('file')}:{top.get('line')}`")
    lines.append(f"- missing: `{missing}`")
    lines.append(f"- apply_allowed_now: `{str(top.get('apply_allowed_now')).lower()}`")
    lines.append("")
    lines.append("## Conclusion")
    lines.append("")
    lines.append("This research-derived target family has completed an observe-only proposal cycle.")
    lines.append("No website source change is allowed in learning_observe_only.")
    lines.append("The track should be marked complete and then finalized to idle.")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write track_complete state only")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    print("accessibility_nav_button_proposal_finalizer =", "apply" if args.apply else "dry_run")
    print("current_topic =", state.get("current_topic"))
    print("current_stage =", state.get("current_stage"))
    print("current_target_family =", state.get("current_target_family"))

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("current_topic") != "accessibility-basics":
        failures.append(f"current_topic_not_accessibility_basics:{state.get('current_topic')}")

    if state.get("current_stage") != "accessibility_nav_button_proposal_ready":
        failures.append(f"current_stage_not_accessibility_nav_button_proposal_ready:{state.get('current_stage')}")

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

    review = state.get("last_accessibility_nav_button_review") or {}
    if review.get("target_family") != TARGET_FAMILY:
        failures.append(f"missing_or_mismatched_last_accessibility_nav_button_review:{review.get('target_family')}")

    top = review.get("top_candidate") or {}
    if top.get("apply_allowed_now") is not False:
        failures.append(f"top_candidate_apply_allowed_now_not_false:{top.get('apply_allowed_now')}")

    report_path = write_report(state, args.apply)

    if failures:
        print("accessibility_nav_button_proposal_finalizer_result = blocked")
        print("finalizer_report =", report_path)
        for x in failures:
            print("failure =", x)
        print("state_written = false")
        print("business_source_written = false")
        print("git_commit = false")
        print("git_push = false")
        print("deploy = false")
        raise SystemExit(2)

    print("accessibility_nav_button_proposal_finalizer_result =", "track_complete" if args.apply else "would_track_complete")
    print("finalizer_report =", report_path)
    print("would_set_stage = track_complete")
    print("track_id =", TARGET_FAMILY)
    print("source_changed = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if not args.apply:
        print("state_written = false")
        print("state_updated = false")
        return 0

    track = {
        "at": now_iso(),
        "track_id": TARGET_FAMILY,
        "topic": "accessibility-basics",
        "stage_before": "accessibility_nav_button_proposal_ready",
        "stage_after": "track_complete",
        "result": "track_complete",
        "reason": "research-derived observe-only nav button semantics scan produced proposal-only evidence; source changes remain blocked",
        "proposal_review": state.get("last_accessibility_nav_button_review"),
        "report": str(report_path),
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "accessibility_nav_button_proposal_finalizer",
        "stage_before": "accessibility_nav_button_proposal_ready",
        "stage_after": "track_complete",
        "target_family": TARGET_FAMILY,
        "report": str(report_path),
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    })

    state.setdefault("completed_tracks", [])
    existing = {x.get("track_id") for x in state["completed_tracks"] if isinstance(x, dict)}
    if TARGET_FAMILY not in existing:
        state["completed_tracks"].append(track)

    state["last_track_complete"] = track
    state["current_stage"] = "track_complete"
    state["next_action"] = "Finalize this completed observe-only target family to idle."
    state["updated_at"] = now_iso()

    save_json(STATE, state)

    print("state_written = true")
    print("state_updated = true")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
