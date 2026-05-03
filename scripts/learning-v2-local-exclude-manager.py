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

EXCLUDE = WORKSPACE / ".git" / "info" / "exclude"

RULES = [
    "",
    "# learning-v2 runtime artifacts - local only",
    "learning-v2/reports/",
    "learning-v2/snapshots/",
    "learning-v2/backups/",
    "learning-v2/state.json",
    "learning-v2/outcomes.jsonl",
    "learning-v2/experiments.jsonl",
    "learning-v2/*.tmp",
    "learning-v2/*.log",
    "# end learning-v2 runtime artifacts",
    "",
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def run(cmd):
    r = subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "cmd": " ".join(cmd),
        "returncode": r.returncode,
        "stdout": r.stdout.strip(),
        "stderr": r.stderr.strip(),
    }

def load_state():
    return json.loads(STATE.read_text(encoding="utf-8"))

def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main():
    if not EXCLUDE.exists():
        raise FileNotFoundError(f"git exclude not found: {EXCLUDE}")

    before = EXCLUDE.read_text(encoding="utf-8", errors="ignore")

    marker_start = "# learning-v2 runtime artifacts - local only"
    marker_end = "# end learning-v2 runtime artifacts"

    if marker_start in before and marker_end in before:
        print("local_exclude_rules_already_present = true")
        after = before
        changed = False
    else:
        after = before.rstrip() + "\n" + "\n".join(RULES)
        EXCLUDE.write_text(after, encoding="utf-8")
        changed = True
        print("local_exclude_rules_added = true")

    git_status = run(["git", "status", "--short"])

    report_path = REPORT_DIR / f"learning-v2-local-exclude-{stamp()}.md"
    lines = []
    lines.append("# Learning V2 Local Exclude Report")
    lines.append("")
    lines.append(f"- generated_at: `{now_iso()}`")
    lines.append("- source_changed: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append(f"- exclude_file: `{EXCLUDE}`")
    lines.append(f"- exclude_changed: `{str(changed).lower()}`")
    lines.append("")
    lines.append("## Added local-only rules")
    lines.append("")
    lines.append("```gitignore")
    lines.append("\n".join(RULES).strip())
    lines.append("```")
    lines.append("")
    lines.append("## Git status after local exclude")
    lines.append("")
    lines.append("```")
    lines.append(git_status["stdout"] or "(empty)")
    lines.append("```")
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")

    state = load_state()
    state["local_exclude_policy"] = {
        "at": now_iso(),
        "exclude_file": str(EXCLUDE),
        "rules": [x for x in RULES if x.strip()],
        "exclude_changed": changed,
        "report": str(report_path),
        "source_changed": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }
    state["next_action"] = "Rerun change ledger and release planner after local exclude rules."
    state["updated_at"] = now_iso()
    save_state(state)

    print("local_exclude_result = ok")
    print("exclude_changed =", str(changed).lower())
    print("source_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("report =", report_path)

if __name__ == "__main__":
    main()
