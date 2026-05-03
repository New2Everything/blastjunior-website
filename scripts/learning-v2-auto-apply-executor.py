#!/usr/bin/env python3
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
BACKUP_DIR = BASE / "backups"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

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

def git_status():
    r = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return r.stdout.strip(), r.stderr.strip()

def safe_source_path(rel):
    rel_path = Path(rel)

    if rel_path.is_absolute():
        raise ValueError("absolute path is not allowed")

    full = (WORKSPACE / rel_path).resolve()

    allowed_roots = [
        (WORKSPACE / "public").resolve(),
        (WORKSPACE / "components").resolve(),
    ]

    if not any(str(full).startswith(str(root) + "/") or full == root for root in allowed_roots):
        raise ValueError(f"path outside allowed roots: {rel}")

    if not full.exists():
        raise FileNotFoundError(f"source file does not exist: {rel}")

    return rel_path, full

def apply_exact_line_change(full_path, line_no, expected_line, target_family):
    lines = full_path.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)

    if line_no < 1 or line_no > len(lines):
        raise ValueError(f"line number out of range: {line_no}")

    actual_line = lines[line_no - 1]
    actual_stripped = actual_line.strip()

    if actual_stripped != expected_line.strip():
        raise ValueError(
            "exact line mismatch; refusing to modify source\n"
            f"expected: {expected_line.strip()}\n"
            f"actual:   {actual_stripped}"
        )

    indent = actual_line[:len(actual_line) - len(actual_line.lstrip())]
    newline = "\n" if actual_line.endswith("\n") else ""

    marker = f"learning-v2:auto-applied:{target_family} removed/deprioritized source line: "

    replacement = (
        indent
        + "<!-- "
        + marker
        + expected_line.strip().replace("--", "—")
        + " -->"
        + newline
    )

    lines[line_no - 1] = replacement
    full_path.write_text("".join(lines), encoding="utf-8")

    return actual_stripped, replacement.strip()

def write_report(state_before, plan, target_family, backup_path, before_line, after_line, git_before, git_after):
    report_path = REPORT_DIR / f"simplicity-auto-apply-{stamp()}.md"

    lines = []
    lines.append("# Simplicity Auto Apply Report")
    lines.append("")
    lines.append(f"- generated_at: `{now_iso()}`")
    lines.append(f"- topic: `{state_before.get('current_topic')}`")
    lines.append(f"- stage_before: `{state_before.get('current_stage')}`")
    lines.append(f"- target_family: `{target_family}`")
    lines.append("- source_changed: `true`")
    lines.append("- git_commit: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Applied change")
    lines.append("")
    lines.append(f"- file: `{plan['source_file']}`")
    lines.append(f"- line: `{plan['line']}`")
    lines.append(f"- backup: `{backup_path}`")
    lines.append("")
    lines.append("### Before")
    lines.append("")
    lines.append("```html")
    lines.append(before_line)
    lines.append("```")
    lines.append("")
    lines.append("### After")
    lines.append("")
    lines.append("```html")
    lines.append(after_line)
    lines.append("```")
    lines.append("")
    lines.append("## Git status before")
    lines.append("")
    lines.append("```")
    lines.append(git_before or "(empty)")
    lines.append("```")
    lines.append("")
    lines.append("## Git status after")
    lines.append("")
    lines.append("```")
    lines.append(git_after or "(empty)")
    lines.append("```")
    lines.append("")
    lines.append("## Conclusion")
    lines.append("")
    lines.append("The self-evolution system modified local website source using an exact-line guarded apply executor.")
    lines.append("No commit or deploy was performed in this step.")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path

def main():
    state = load_state()
    topic = state.get("current_topic")
    stage = state.get("current_stage")

    print("auto_apply_topic =", topic)
    print("auto_apply_stage =", stage)

    if topic != "simplicity" or stage != "apply_planned":
        print("auto_apply_skip = true")
        return 0

    state_before = json.loads(json.dumps(state, ensure_ascii=False))

    last_apply_plan = state.get("last_apply_plan") or {}
    plan = last_apply_plan.get("plan") or {}

    source_file = plan.get("source_file")
    line_no = int(plan.get("line"))
    expected_line = plan.get("current_line") or plan.get("old_text_from_validate")

    target_family = (
        state.get("current_target_family")
        or (state.get("apply_ready") or {}).get("target_family")
        or "simplicity.generic"
    )

    if not source_file or not line_no or not expected_line:
        raise ValueError("missing source_file / line / expected_line in last_apply_plan")

    rel_path, full_path = safe_source_path(source_file)

    git_before, git_before_err = git_status()

    backup_path = BACKUP_DIR / f"{rel_path.name}.before-auto-apply-{stamp()}"
    shutil.copy2(full_path, backup_path)

    before_line, after_line = apply_exact_line_change(
        full_path=full_path,
        line_no=line_no,
        expected_line=expected_line,
        target_family=target_family,
    )

    git_after, git_after_err = git_status()

    report_path = write_report(
        state_before=state_before,
        plan=plan,
        target_family=target_family,
        backup_path=str(backup_path),
        before_line=before_line,
        after_line=after_line,
        git_before=git_before,
        git_after=git_after,
    )

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "simplicity_auto_apply_executor_v3_generic",
        "stage_before": "apply_planned",
        "stage_after": "applied",
        "target_family": target_family,
        "source_changed": True,
        "source_file": source_file,
        "line": line_no,
        "backup": str(backup_path),
        "report": str(report_path),
        "git_commit": False,
        "deploy": False,
    })

    state["last_auto_apply"] = {
        "at": now_iso(),
        "topic": "simplicity",
        "target_family": target_family,
        "stage_before": "apply_planned",
        "stage_after": "applied",
        "source_changed": True,
        "source_file": source_file,
        "line": line_no,
        "before": before_line,
        "after": after_line,
        "backup": str(backup_path),
        "report": str(report_path),
        "git_commit": False,
        "deploy": False,
    }

    state["current_stage"] = "applied"
    state["next_action"] = "Run post-apply validation. If validation fails, restore backup automatically."
    state["updated_at"] = now_iso()

    save_state(state)

    print("auto_apply_result = applied")
    print("target_family =", target_family)
    print("source_changed = true")
    print("source_file =", source_file)
    print("line =", line_no)
    print("backup =", backup_path)
    print("auto_apply_report =", report_path)
    print("git_commit = false")
    print("deploy = false")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
