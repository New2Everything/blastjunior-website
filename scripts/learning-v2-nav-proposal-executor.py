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

def write_report(state_before, selected):
    report_path = REPORT_DIR / f"simplicity-nav-proposal-{stamp()}.md"

    lines = []
    lines.append("# Simplicity Nav Proposal Report")
    lines.append("")
    lines.append(f"- generated_at: `{now_iso()}`")
    lines.append(f"- topic: `{state_before.get('current_topic')}`")
    lines.append(f"- stage_before: `{state_before.get('current_stage')}`")
    lines.append("- target_family: `simplicity.nav_anchor_deprioritize`")
    lines.append("- source_changed: `false`")
    lines.append("")
    lines.append("## Selected nav candidate")
    lines.append("")
    lines.append(f"- file: `{selected['file']}`")
    lines.append(f"- line: `{selected['line']}`")
    lines.append(f"- label: `{selected['label']}`")
    lines.append(f"- href: `{selected['href']}`")
    lines.append(f"- reason: `{selected['reason']}`")
    lines.append("")
    lines.append("```html")
    lines.append(selected["text"])
    lines.append("```")
    lines.append("")
    lines.append("## Proposal")
    lines.append("")
    lines.append("Deprioritize this navigation entry by removing the active nav anchor from the rendered navigation.")
    lines.append("")
    lines.append("This is allowed only through exact-line match, backup, and post-apply validation.")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path

def main():
    state = load_state()
    topic = state.get("current_topic")
    stage = state.get("current_stage")

    print("nav_proposal_topic =", topic)
    print("nav_proposal_stage =", stage)

    if topic != "simplicity" or stage != "nav_inventory_ready":
        print("nav_proposal_skip = true")
        return 0

    state_before = json.loads(json.dumps(state, ensure_ascii=False))
    nav = state.get("last_nav_discover") or {}
    candidates = nav.get("candidates") or []

    if not candidates:
        state["current_stage"] = "nav_inventory_blocked"
        state["next_action"] = "No nav candidates available."
        save_state(state)
        print("nav_proposal_result = nav_inventory_blocked")
        return 0

    # Conservative selection: only one safe candidate was found by nav_discover.
    selected = candidates[0]

    report_path = write_report(state_before, selected)

    primary = {
        "type": "match",
        "target_family": "simplicity.nav_anchor_deprioritize",
        "target": selected.get("label"),
        "href": selected.get("href"),
        "file": selected.get("file"),
        "line": selected.get("line"),
        "text": selected.get("text"),
        "fingerprint": f"{selected.get('file')}:{selected.get('line')}:{selected.get('text')}",
        "priority_score": 100,
    }

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "simplicity_nav_proposal_executor",
        "stage_before": "nav_inventory_ready",
        "stage_after": "apply_ready",
        "target_family": "simplicity.nav_anchor_deprioritize",
        "selected": primary,
        "source_changed": False,
        "report": str(report_path),
    })

    state["last_nav_proposal"] = {
        "at": now_iso(),
        "topic": "simplicity",
        "target_family": "simplicity.nav_anchor_deprioritize",
        "stage_before": "nav_inventory_ready",
        "stage_after": "apply_ready",
        "selected": primary,
        "report": str(report_path),
        "source_changed": False,
    }

    state["current_target_family"] = "simplicity.nav_anchor_deprioritize"
    state["apply_ready"] = {
        "topic": "simplicity",
        "target_family": "simplicity.nav_anchor_deprioritize",
        "target": selected.get("label"),
        "primary_location": primary,
        "all_locations": [primary],
        "report": str(report_path),
        "allowed_next_step": "continue autonomous guarded apply; exact-line match, backup, and post-apply validation are required",
    }

    state["current_stage"] = "apply_ready"
    state["next_action"] = "Run autonomous guarded apply for selected nav candidate."
    state["updated_at"] = now_iso()

    save_state(state)

    print("nav_proposal_result = apply_ready")
    print("target_family = simplicity.nav_anchor_deprioritize")
    print("selected_location =", f"{selected.get('file')}:{selected.get('line')}")
    print("selected_label =", selected.get("label"))
    print("selected_href =", selected.get("href"))
    print("source_changed = false")
    print("report =", report_path)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
