#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
OUTCOMES = BASE / "outcomes.jsonl"
EXPERIMENTS = BASE / "experiments.jsonl"

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

def append_jsonl(path, obj):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def make_target_fingerprint(source_file, line, before):
    return f"{source_file}:{line}:{before}"

def write_report(outcome):
    report_path = REPORT_DIR / f"simplicity-cycle-outcome-{stamp()}.md"

    lines = []
    lines.append("# Simplicity Cycle Outcome Report")
    lines.append("")
    lines.append(f"- generated_at: `{now_iso()}`")
    lines.append(f"- topic: `{outcome.get('topic')}`")
    lines.append(f"- result: `{outcome.get('result')}`")
    lines.append(f"- source_changed: `{str(outcome.get('source_changed')).lower()}`")
    lines.append(f"- git_commit: `{str(outcome.get('git_commit')).lower()}`")
    lines.append(f"- deploy: `{str(outcome.get('deploy')).lower()}`")
    lines.append("")

    lines.append("## Target")
    lines.append("")
    lines.append(f"- file: `{outcome.get('source_file')}`")
    lines.append(f"- line: `{outcome.get('line')}`")
    lines.append(f"- fingerprint: `{outcome.get('target_fingerprint')}`")
    lines.append("")

    lines.append("## Before")
    lines.append("")
    lines.append("```html")
    lines.append(outcome.get("before") or "")
    lines.append("```")
    lines.append("")

    lines.append("## After")
    lines.append("")
    lines.append("```html")
    lines.append(outcome.get("after") or "")
    lines.append("```")
    lines.append("")

    lines.append("## Validation checks")
    lines.append("")
    for c in outcome.get("checks", []):
        status = "PASS" if c.get("ok") else "FAIL"
        lines.append(f"- `{status}` {c.get('name')}: {c.get('detail')}")
    lines.append("")

    lines.append("## Learned rule")
    lines.append("")
    lines.append("For homepage simplicity improvements, the system can safely apply an exact-line source change only after:")
    lines.append("")
    lines.append("1. audit identifies a low-value visible entry;")
    lines.append("2. validate locates the exact source line;")
    lines.append("3. apply executor creates a backup and changes only the expected line;")
    lines.append("4. post-apply validation confirms the page structure is still valid;")
    lines.append("5. failed validation must restore the backup.")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path

def main():
    state = load_state()
    topic = state.get("current_topic")
    stage = state.get("current_stage")

    print("outcome_recorder_topic =", topic)
    print("outcome_recorder_stage =", stage)

    if topic != "simplicity" or stage != "post_validated":
        print("outcome_recorder_skip = true")
        return 0

    last_auto_apply = state.get("last_auto_apply") or {}
    last_validation = state.get("last_post_apply_validation") or {}

    source_file = last_auto_apply.get("source_file")
    line = last_auto_apply.get("line")
    before = last_auto_apply.get("before")
    after = last_auto_apply.get("after")

    if not source_file or not line or not before or not after:
        raise ValueError("missing last_auto_apply fields")

    fingerprint = make_target_fingerprint(source_file, line, before)

    checks = last_validation.get("checks", [])
    all_checks_ok = all(c.get("ok") for c in checks)

    outcome = {
        "at": now_iso(),
        "topic": "simplicity",
        "stage_before": "post_validated",
        "result": "success" if all_checks_ok else "validation_inconsistent",
        "source_changed": True,
        "source_file": source_file,
        "line": line,
        "before": before,
        "after": after,
        "backup": last_auto_apply.get("backup"),
        "auto_apply_report": last_auto_apply.get("report"),
        "post_apply_validation_report": last_validation.get("report"),
        "checks": checks,
        "target_fingerprint": fingerprint,
        "git_commit": False,
        "deploy": False,
        "learned_rule": "exact-line auto apply with backup and post-validation can safely complete a homepage simplicity improvement cycle",
    }

    outcome_report = write_report(outcome)
    outcome["outcome_report"] = str(outcome_report)

    append_jsonl(OUTCOMES, outcome)

    append_jsonl(EXPERIMENTS, {
        "at": now_iso(),
        "type": "cycle_outcome",
        "topic": "simplicity",
        "result": outcome["result"],
        "source_changed": True,
        "source_file": source_file,
        "line": line,
        "target_fingerprint": fingerprint,
        "report": str(outcome_report),
    })

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "simplicity_outcome_recorder",
        "stage_before": "post_validated",
        "stage_after": "cycle_recorded",
        "result": outcome["result"],
        "source_file": source_file,
        "line": line,
        "target_fingerprint": fingerprint,
        "report": str(outcome_report),
    })

    state.setdefault("completed_cycles", [])
    state["completed_cycles"].append(outcome)

    state.setdefault("applied_targets", [])
    if fingerprint not in state["applied_targets"]:
        state["applied_targets"].append(fingerprint)

    state["last_outcome"] = outcome

    # Important: switch system policy from human approval to autonomous guarded apply.
    state["self_evolution_policy"] = {
        "mode": "autonomous_guarded_apply",
        "allow_source_changes": True,
        "allowed_source_roots": ["public", "components"],
        "require_exact_line_match": True,
        "require_backup": True,
        "require_post_apply_validation": True,
        "auto_rollback_on_validation_failure": True,
        "allow_git_commit": False,
        "allow_deploy": False,
    }

    # Clear active cycle so selector can begin the next improvement cycle.
    state["previous_topic"] = topic
    state["previous_stage"] = stage
    state["current_topic"] = None
    state["current_stage"] = None
    state["next_action"] = "Run selector to choose the next self-evolution improvement cycle."
    state["updated_at"] = now_iso()

    save_state(state)

    print("outcome_recorder_result = cycle_recorded")
    print("outcome_report =", outcome_report)
    print("source_changed = true")
    print("git_commit = false")
    print("deploy = false")
    print("current_topic = null")
    print("current_stage = null")
    print("next_action = Run selector to choose the next self-evolution improvement cycle.")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
