#!/usr/bin/env python3
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

def write_report(state_before, discovery):
    report_path = REPORT_DIR / f"simplicity-discover-{stamp()}.md"

    lines = []
    lines.append("# Simplicity Discover Report")
    lines.append("")
    lines.append(f"- generated_at: `{now_iso()}`")
    lines.append(f"- topic: `{state_before.get('current_topic')}`")
    lines.append(f"- stage_before: `{state_before.get('current_stage')}`")
    lines.append(f"- stage_after: `{discovery['stage_after']}`")
    lines.append(f"- target_family: `{discovery['target_family']}`")
    lines.append("- source_changed: `false`")
    lines.append("")
    lines.append("## Discovery summary")
    lines.append("")
    lines.append(discovery["summary"])
    lines.append("")
    lines.append("## Sources")
    lines.append("")
    for s in discovery["sources"]:
        lines.append(f"- {s}")
    lines.append("")
    lines.append("## Disabled target families")
    lines.append("")
    if discovery["disabled_target_families"]:
        for t in discovery["disabled_target_families"]:
            lines.append(f"- `{t}`")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Next action")
    lines.append("")
    lines.append(discovery["next_action"])
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path

def main():
    state = load_state()
    topic = state.get("current_topic")
    stage = state.get("current_stage")

    print("discover_executor_topic =", topic)
    print("discover_executor_stage =", stage)

    if topic != "simplicity" or stage != "discover":
        print("discover_executor_skip = true")
        return 0

    state_before = json.loads(json.dumps(state, ensure_ascii=False))
    disabled = state.get("disabled_target_families") or []
    applied_targets = state.get("applied_targets") or []

    if "simplicity.section_more_anchor" in disabled:
        stage_after = "nav_discover"
        target_family = "simplicity.nav_anchor_deprioritize"
        summary = (
            "The section-more anchor track is complete. "
            "Start a new simplicity target family: active navigation anchors. "
            "The next step should inventory real <nav> links only, without modifying website source."
        )
        next_action = "Scan active <nav> anchors and prepare a nav target inventory."
    else:
        stage_after = "synthesize"
        target_family = "simplicity.section_more_anchor"
        summary = (
            "Continue the homepage simplicity improvement cycle. "
            "Look for active low-value section-more anchors while avoiding already-applied targets and comments."
        )
        next_action = (
            "Run synthesize stage for simplicity. "
            "Synthesize should audit active homepage entries only and ignore already-applied or commented-out targets."
        )

    discovery = {
        "topic": "simplicity",
        "stage_before": "discover",
        "stage_after": stage_after,
        "target_family": target_family,
        "summary": summary,
        "sources": [
            "learning-v2/state.json",
            "learning-v2/outcomes.jsonl",
            "learning-v2 completed_tracks",
            "public/ active markup",
            "components/ active markup",
            "constitution/directives: simplicity, less-is-more, reduce first-screen clutter",
        ],
        "disabled_target_families": disabled,
        "applied_targets": applied_targets,
        "next_action": next_action,
        "source_changed": False,
    }

    report_path = write_report(state_before, discovery)

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "simplicity_discover_executor_v2_target_family_router",
        "stage_before": "discover",
        "stage_after": stage_after,
        "target_family": target_family,
        "report": str(report_path),
        "source_changed": False,
    })

    state["last_discover"] = {
        "at": now_iso(),
        **discovery,
        "report": str(report_path),
    }

    state["current_target_family"] = target_family
    state["sources"] = discovery["sources"]
    state["summary"] = discovery["summary"]
    state["next_action"] = discovery["next_action"]
    state["current_stage"] = stage_after
    state["updated_at"] = now_iso()

    save_state(state)

    print("discover_executor_result =", stage_after)
    print("target_family =", target_family)
    print("discover_report =", report_path)
    print("source_changed = false")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
