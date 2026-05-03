#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def load_state():
    if not STATE.exists():
        raise FileNotFoundError(f"state.json not found: {STATE}")
    return json.loads(STATE.read_text(encoding="utf-8"))

def save_state(state):
    STATE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

def run_git_status():
    try:
        r = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(WORKSPACE),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return "", str(e)

def safe_rel_path(path_text):
    p = Path(path_text)
    if p.is_absolute():
        raise ValueError("absolute source path is not allowed")
    full = (WORKSPACE / p).resolve()

    allowed_roots = [
        (WORKSPACE / "public").resolve(),
        (WORKSPACE / "components").resolve(),
    ]

    if not any(str(full).startswith(str(root) + "/") or full == root for root in allowed_roots):
        raise ValueError(f"source path outside allowed roots: {path_text}")

    return p, full

def read_line(full_path, line_no):
    lines = full_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if line_no < 1 or line_no > len(lines):
        return None
    return lines[line_no - 1]

def build_plan(state):
    apply_ready = state.get("apply_ready") or {}
    primary = apply_ready.get("primary_location") or {}

    file_text = primary.get("file")
    line_no = primary.get("line")
    old_text = primary.get("text")
    target = primary.get("target")

    if not file_text or not line_no:
        raise ValueError("missing primary location in apply_ready")

    rel_path, full_path = safe_rel_path(file_text)

    current_line = read_line(full_path, int(line_no))
    if current_line is None:
        raise ValueError(f"line not found: {file_text}:{line_no}")

    exact_match = current_line.strip() == str(old_text).strip()

    plan = {
        "topic": "simplicity",
        "target": target,
        "source_file": str(rel_path),
        "line": int(line_no),
        "old_text_from_validate": old_text,
        "current_line": current_line.strip(),
        "line_still_matches_validate": exact_match,
        "source_changed": False,
        "will_modify_source": False,
        "requires_explicit_human_approval": False,
        "autonomous_guarded_apply": True,
        "guardrails": [
            "Do not write to public/ or components/ during apply planning.",
            "Only generate a proposal report.",
            "Do not run sed/perl/python write operations against website source.",
            "Do not commit.",
            "Do not deploy.",
            "After this plan, autonomous apply may continue only with exact-line match, backup, and post-apply validation.",
        ],
        "proposal": {
            "intent": "lower homepage first-screen clutter by de-emphasizing the selected secondary '更多 >' entry",
            "candidate_change_type": "remove_or_hide_secondary_link",
            "candidate_patch_preview_only": [
                f"--- a/{rel_path}",
                f"+++ b/{rel_path}",
                f"@@ line {line_no} @@",
                f"- {current_line.strip()}",
                "+ <!-- learning-v2 proposal: remove/de-emphasize this secondary '更多 >' entry after approval -->",
            ],
        },
    }

    return plan

def write_report(state_before, plan, git_status, git_error):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = REPORT_DIR / f"simplicity-apply-plan-{ts}.md"

    lines = []
    lines.append("# Simplicity Apply Guardrails Report")
    lines.append("")
    lines.append(f"- generated_at: `{now_iso()}`")
    lines.append(f"- topic: `{state_before.get('current_topic')}`")
    lines.append(f"- stage_before: `{state_before.get('current_stage')}`")
    lines.append("- source_changed: `false`")
    lines.append("- will_modify_source: `false`")
    lines.append("- requires_explicit_human_approval: `false`")
    lines.append("")

    lines.append("## Target")
    lines.append("")
    lines.append(f"- file: `{plan['source_file']}`")
    lines.append(f"- line: `{plan['line']}`")
    lines.append(f"- target: `{plan.get('target')}`")
    lines.append(f"- line_still_matches_validate: `{str(plan['line_still_matches_validate']).lower()}`")
    lines.append("")

    lines.append("## Current source line")
    lines.append("")
    lines.append("```html")
    lines.append(plan["current_line"])
    lines.append("```")
    lines.append("")

    lines.append("## Patch preview only")
    lines.append("")
    lines.append("This is not applied. It is only a preview for future approval.")
    lines.append("")
    lines.append("```diff")
    for x in plan["proposal"]["candidate_patch_preview_only"]:
        lines.append(x)
    lines.append("```")
    lines.append("")

    lines.append("## Guardrails")
    lines.append("")
    for g in plan["guardrails"]:
        lines.append(f"- {g}")
    lines.append("")

    lines.append("## Git status snapshot before any source change")
    lines.append("")
    if git_error:
        lines.append(f"Git status error: `{git_error}`")
    elif git_status:
        lines.append("```")
        lines.append(git_status)
        lines.append("```")
    else:
        lines.append("Working tree appeared clean at snapshot time.")
    lines.append("")

    lines.append("## Conclusion")
    lines.append("")
    lines.append("Apply planning is ready for autonomous guarded apply. Source modification is allowed only through exact-line match, backup, and post-apply validation.")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path

def main():
    state = load_state()
    topic = state.get("current_topic")
    stage = state.get("current_stage")

    print("apply_guardrails_topic =", topic)
    print("apply_guardrails_stage =", stage)

    if topic != "simplicity" or stage != "apply_ready":
        print("apply_guardrails_skip = true")
        return 0

    state_before = json.loads(json.dumps(state, ensure_ascii=False))

    plan = build_plan(state)
    git_status, git_error = run_git_status()
    report_path = write_report(state_before, plan, git_status, git_error)

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "simplicity_apply_guardrails",
        "stage_before": "apply_ready",
        "stage_after": "apply_planned",
        "report": str(report_path),
        "source_changed": False,
        "will_modify_source": False,
        "requires_explicit_human_approval": False,
        "autonomous_guarded_apply": True,
    })

    state["last_apply_plan"] = {
        "at": now_iso(),
        "topic": "simplicity",
        "stage_before": "apply_ready",
        "stage_after": "apply_planned",
        "plan": plan,
        "report": str(report_path),
        "source_changed": False,
        "will_modify_source": False,
        "requires_explicit_human_approval": False,
        "autonomous_guarded_apply": True,
    }

    state["current_stage"] = "apply_planned"
    state["next_action"] = "Run autonomous auto-apply executor with exact-line match, backup, and post-apply validation."
    state["updated_at"] = now_iso()

    save_state(state)

    print("apply_guardrails_result = apply_planned")
    print("apply_guardrails_report =", report_path)
    print("source_changed = false")
    print("will_modify_source = false")
    print("requires_explicit_human_approval = false")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
