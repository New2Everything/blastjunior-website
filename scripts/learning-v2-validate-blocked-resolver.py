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

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_state():
    return json.loads(STATE.read_text(encoding="utf-8"))

def save_state(state):
    STATE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

def write_report(state_before, track, apply):
    suffix = "apply" if apply else "dry-run"
    report_path = REPORT_DIR / f"simplicity-validate-blocked-track-complete-{suffix}-{stamp()}.md"

    lines = []
    lines.append("# Simplicity Validate Blocked Resolver Report")
    lines.append("")
    lines.append(f"- generated_at: `{now_iso()}`")
    lines.append(f"- mode: `{'apply' if apply else 'dry-run'}`")
    lines.append(f"- topic: `{state_before.get('current_topic')}`")
    lines.append(f"- stage_before: `{state_before.get('current_stage')}`")
    lines.append("- source_changed: `false`")
    lines.append(f"- state_written: `{'true' if apply else 'false'}`")
    lines.append("- result: `track_complete`")
    lines.append("")

    lines.append("## Completed track")
    lines.append("")
    lines.append(f"- track_id: `{track['track_id']}`")
    lines.append(f"- reason: `{track['reason']}`")
    lines.append(f"- matched_locations: `{track['matched_locations']}`")
    lines.append(f"- skipped_locations: `{track['skipped_locations']}`")
    lines.append("")

    lines.append("## Skipped locations")
    lines.append("")
    for s in track.get("skipped_locations_detail", []):
        lines.append(f"### `{s.get('file')}:{s.get('line')}`")
        lines.append("")
        lines.append(f"- reason: `{s.get('reason')}`")
        lines.append(f"- target: `{s.get('target')}`")
        lines.append("")
        lines.append("```")
        lines.append(s.get("text") or "")
        lines.append("```")
        lines.append("")

    lines.append("## Conclusion")
    lines.append("")
    lines.append("No eligible active section-more anchor remains for the current simplicity track.")
    lines.append("The system should not keep retrying this same target family.")
    lines.append("A new target-family executor is required before further autonomous source changes.")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually write track_complete state")
    args = ap.parse_args()

    state = load_state()
    topic = state.get("current_topic")
    stage = state.get("current_stage")
    policy = state.get("self_evolution_policy") or {}

    print("validate_blocked_resolver =", "apply" if args.apply else "dry_run")
    print("validate_blocked_resolver_topic =", topic)
    print("validate_blocked_resolver_stage =", stage)

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if topic != "simplicity" or stage != "validate_blocked":
        print("validate_blocked_resolver_skip = true")
        print("state_written = false")
        print("source_changed = false")
        return 0

    last_validate = state.get("last_validate") or {}
    matched = int(last_validate.get("matched_locations") or 0)
    skipped = int(last_validate.get("skipped_locations") or 0)

    if matched > 0:
        failures.append(f"matched_locations_not_zero:{matched}")

    if failures:
        print("validate_blocked_resolver_result = blocked")
        for x in failures:
            print("failure =", x)
        print("state_written = false")
        print("source_changed = false")
        print("business_source_written = false")
        print("git_commit = false")
        print("git_push = false")
        print("deploy = false")
        raise SystemExit(2)

    state_before = json.loads(json.dumps(state, ensure_ascii=False))

    track = {
        "at": now_iso(),
        "track_id": "simplicity.section_more_anchor",
        "topic": "simplicity",
        "stage_before": "validate_blocked",
        "stage_after": "track_complete",
        "result": "track_complete",
        "reason": "no eligible active section-more anchor targets remain",
        "matched_locations": matched,
        "skipped_locations": skipped,
        "skipped_locations_detail": last_validate.get("skipped_locations_detail") or [],
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }

    report_path = write_report(state_before, track, args.apply)
    track["report"] = str(report_path)

    print("validate_blocked_resolver_result =", "track_complete" if args.apply else "would_track_complete")
    print("track_id =", track["track_id"])
    print("matched_locations =", matched)
    print("skipped_locations =", skipped)
    print("would_set_stage = track_complete")
    print("source_changed = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("report =", report_path)

    if not args.apply:
        print("state_written = false")
        print("state_updated = false")
        return 0

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "simplicity_validate_blocked_resolver",
        "stage_before": "validate_blocked",
        "stage_after": "track_complete",
        "track_id": track["track_id"],
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "report": str(report_path),
    })

    state.setdefault("completed_tracks", [])
    existing = {x.get("track_id") for x in state["completed_tracks"] if isinstance(x, dict)}
    if track["track_id"] not in existing:
        state["completed_tracks"].append(track)

    state["last_track_complete"] = track
    state["current_stage"] = "track_complete"
    state["next_action"] = (
        "Current simplicity section-more track is complete. "
        "Build a new target-family executor before continuing autonomous source changes."
    )
    state["updated_at"] = now_iso()

    save_state(state)

    print("state_written = true")
    print("state_updated = true")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
