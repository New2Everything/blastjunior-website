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

def write_report(track_id, state_before, apply):
    suffix = "apply" if apply else "dry-run"
    report_path = REPORT_DIR / f"learning-v2-track-finalized-{suffix}-{stamp()}.md"

    lines = []
    lines.append("# Learning V2 Track Finalized")
    lines.append("")
    lines.append(f"- generated_at: `{now_iso()}`")
    lines.append(f"- mode: `{'apply' if apply else 'dry-run'}`")
    lines.append(f"- topic: `{state_before.get('current_topic')}`")
    lines.append(f"- stage_before: `{state_before.get('current_stage')}`")
    lines.append(f"- track_id: `{track_id}`")
    lines.append("- source_changed: `false`")
    lines.append(f"- state_written: `{'true' if apply else 'false'}`")
    lines.append("")
    lines.append("## Result")
    lines.append("")
    lines.append("This target family is now marked as completed and disabled for future automatic selection.")
    lines.append("")
    lines.append("The selector may start a new cycle, but the system should not retry this same target family.")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually finalize track and clear current topic/stage")
    args = ap.parse_args()

    state = load_state()
    topic = state.get("current_topic")
    stage = state.get("current_stage")
    policy = state.get("self_evolution_policy") or {}

    print("track_complete_finalizer =", "apply" if args.apply else "dry_run")
    print("track_complete_finalizer_topic =", topic)
    print("track_complete_finalizer_stage =", stage)

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if stage != "track_complete":
        print("track_complete_finalizer_skip = true")
        print("state_written = false")
        print("source_changed = false")
        return 0

    if failures:
        print("track_complete_finalizer_result = blocked")
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
    last_track = state.get("last_track_complete") or {}
    track_id = last_track.get("track_id") or "unknown.track"

    report_path = write_report(track_id, state_before, args.apply)

    print("track_complete_finalizer_result =", "idle" if args.apply else "would_idle")
    print("disabled_target_family =", track_id)
    print("would_clear_current_topic = true")
    print("would_clear_current_stage = true")
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

    state.setdefault("disabled_target_families", [])
    if track_id not in state["disabled_target_families"]:
        state["disabled_target_families"].append(track_id)

    state.setdefault("track_status", {})
    state["track_status"][track_id] = {
        "status": "complete",
        "completed_at": now_iso(),
        "reason": last_track.get("reason"),
        "report": str(report_path),
    }

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "learning_v2_track_complete_finalizer",
        "stage_before": "track_complete",
        "stage_after": "idle",
        "track_id": track_id,
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "report": str(report_path),
    })

    state["previous_topic"] = topic
    state["previous_stage"] = stage
    state["current_topic"] = None
    state["current_stage"] = None
    state["current_target_family"] = None
    state["next_action"] = "Run selector for a new cycle. Do not retry disabled target families."
    state["updated_at"] = now_iso()

    save_state(state)

    print("current_topic = null")
    print("current_stage = null")
    print("state_written = true")
    print("state_updated = true")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
