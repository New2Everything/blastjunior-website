#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path("/root/.openclaw/workspace/learning-v2")
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
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main():
    state = load_state()

    topic = state.get("current_topic")
    stage = state.get("current_stage")

    print("pause_active_cycle_topic =", topic)
    print("pause_active_cycle_stage =", stage)

    report_path = REPORT_DIR / f"learning-v2-paused-active-cycle-{stamp()}.md"

    paused = {
        "at": now_iso(),
        "topic": topic,
        "stage": stage,
        "current_target_family": state.get("current_target_family"),
        "next_action_before_pause": state.get("next_action"),
        "reason": "system_build_only mode: pause active website-change cycle while building learning-v2 infrastructure",
        "source_changed": False,
    }

    lines = []
    lines.append("# Learning V2 Paused Active Cycle")
    lines.append("")
    lines.append(f"- generated_at: `{paused['at']}`")
    lines.append(f"- topic: `{topic}`")
    lines.append(f"- stage: `{stage}`")
    lines.append(f"- current_target_family: `{paused['current_target_family']}`")
    lines.append("- source_changed: `false`")
    lines.append("")
    lines.append("## Reason")
    lines.append("")
    lines.append(paused["reason"])
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")

    paused["report"] = str(report_path)

    state.setdefault("paused_cycles", [])
    if topic is not None or stage is not None:
        state["paused_cycles"].append(paused)

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "learning_v2_pause_active_cycle",
        "topic_before": topic,
        "stage_before": stage,
        "stage_after": "system_build_idle",
        "source_changed": False,
        "report": str(report_path),
    })

    state["previous_topic"] = topic
    state["previous_stage"] = stage
    state["current_topic"] = None
    state["current_stage"] = None
    state["next_action"] = "System build mode active. Build learning-v2 infrastructure; do not run website-change cycles."
    state["updated_at"] = now_iso()

    save_state(state)

    print("pause_active_cycle_result = system_build_idle")
    print("source_changed = false")
    print("report =", report_path)
    print("current_topic = null")
    print("current_stage = null")

if __name__ == "__main__":
    main()
