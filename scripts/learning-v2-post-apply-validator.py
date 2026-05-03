#!/usr/bin/env python3
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from html.parser import HTMLParser
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

class BasicHTMLParser(HTMLParser):
    pass

def strip_html_comments(text):
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)

def validate_html_parse(text):
    parser = BasicHTMLParser()
    try:
        parser.feed(text)
        parser.close()
        return True, []
    except Exception as e:
        return False, [str(e)]

def read_line(full_path, line_no):
    lines = full_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if line_no < 1 or line_no > len(lines):
        return None
    return lines[line_no - 1].strip()

def restore_backup(backup, target):
    backup_path = Path(backup)
    if not backup_path.exists():
        raise FileNotFoundError(f"backup not found: {backup}")
    shutil.copy2(backup_path, target)

def extract_active_ids(html):
    active = strip_html_comments(html)
    return set(re.findall(r'\bid=["\']([^"\']+)["\']', active))

def count_active_anchors(html):
    active = strip_html_comments(html)
    return len(re.findall(r"<a\b[^>]*\bhref=[\"'][^\"']+[\"'][^>]*>", active, flags=re.I))

def structure_checks_for_file(source_file, backup_html, current_html):
    backup_active = strip_html_comments(backup_html)
    current_active = strip_html_comments(current_html)

    checks = []

    if "<nav" in backup_active.lower():
        checks.append({
            "name": "nav_structure_still_exists",
            "ok": "<nav" in current_active.lower() and "</nav>" in current_active.lower(),
            "detail": "nav container should remain present",
        })

        before_count = count_active_anchors(backup_html)
        after_count = count_active_anchors(current_html)

        checks.append({
            "name": "active_anchor_count_reasonable",
            "ok": after_count >= 1 and after_count >= before_count - 1,
            "detail": f"anchors before={before_count}, after={after_count}",
        })

        protected_needles = [
            'href="/"',
            'href="/login"',
        ]

        missing = [x for x in protected_needles if x in backup_active and x not in current_active]
        checks.append({
            "name": "protected_nav_links_preserved",
            "ok": len(missing) == 0,
            "detail": "missing: " + (", ".join(missing) if missing else "none"),
        })

    if "<section" in backup_active.lower():
        checks.append({
            "name": "section_structure_still_exists",
            "ok": "<section" in current_active.lower() and "</section>" in current_active.lower(),
            "detail": "section markup should remain present when it existed before",
        })

    if not checks:
        checks.append({
            "name": "basic_structure_nonempty",
            "ok": len(current_active.strip()) > 0,
            "detail": "active source should not be empty",
        })

    return checks

def write_report(state_before, checks, result, restored, source_file, backup, git_before, git_after):
    report_path = REPORT_DIR / f"simplicity-post-apply-validation-{stamp()}.md"

    lines = []
    lines.append("# Simplicity Post Apply Validation Report")
    lines.append("")
    lines.append(f"- generated_at: `{now_iso()}`")
    lines.append(f"- topic: `{state_before.get('current_topic')}`")
    lines.append(f"- stage_before: `{state_before.get('current_stage')}`")
    lines.append(f"- target_family: `{state_before.get('current_target_family')}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- restored_from_backup: `{str(restored).lower()}`")
    lines.append(f"- source_file: `{source_file}`")
    lines.append(f"- backup: `{backup}`")
    lines.append("- git_commit: `false`")
    lines.append("- deploy: `false`")
    lines.append("")

    lines.append("## Checks")
    lines.append("")
    for c in checks:
        status = "PASS" if c["ok"] else "FAIL"
        lines.append(f"- `{status}` {c['name']}: {c['detail']}")
    lines.append("")

    lines.append("## Git status before validation")
    lines.append("")
    lines.append("```")
    lines.append(git_before or "(empty)")
    lines.append("```")
    lines.append("")

    lines.append("## Git status after validation")
    lines.append("")
    lines.append("```")
    lines.append(git_after or "(empty)")
    lines.append("```")
    lines.append("")

    lines.append("## Conclusion")
    lines.append("")
    if result == "post_validated":
        lines.append("The auto-applied source change passed dynamic post-apply validation.")
    else:
        lines.append("The auto-applied source change failed validation and was rolled back from backup.")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path

def main():
    state = load_state()
    topic = state.get("current_topic")
    stage = state.get("current_stage")

    print("post_apply_validator_topic =", topic)
    print("post_apply_validator_stage =", stage)

    if topic != "simplicity" or stage != "applied":
        print("post_apply_validator_skip = true")
        return 0

    state_before = json.loads(json.dumps(state, ensure_ascii=False))
    last_auto_apply = state.get("last_auto_apply") or {}

    source_file = last_auto_apply.get("source_file")
    line_no = int(last_auto_apply.get("line"))
    before = last_auto_apply.get("before")
    after = last_auto_apply.get("after")
    backup = last_auto_apply.get("backup")
    target_family = last_auto_apply.get("target_family") or state.get("current_target_family") or "simplicity.generic"

    if not source_file or not line_no or not before or not after or not backup:
        raise ValueError("missing last_auto_apply fields")

    rel_path, full_path = safe_source_path(source_file)
    backup_path = Path(backup)

    git_before, git_before_err = git_status()

    html = full_path.read_text(encoding="utf-8", errors="ignore")
    html_without_comments = strip_html_comments(html)
    current_line = read_line(full_path, line_no)

    backup_html = backup_path.read_text(encoding="utf-8", errors="ignore") if backup_path.exists() else ""
    backup_ids = extract_active_ids(backup_html)
    current_ids = extract_active_ids(html)
    missing_ids = sorted(backup_ids - current_ids)

    marker = f"learning-v2:auto-applied:{target_family}"

    checks = []

    checks.append({
        "name": "backup_exists",
        "ok": backup_path.exists(),
        "detail": backup,
    })

    checks.append({
        "name": "target_line_matches_expected_after",
        "ok": current_line == after.strip(),
        "detail": f"line {line_no}: {current_line}",
    })

    checks.append({
        "name": "active_old_line_removed",
        "ok": before.strip() not in html_without_comments,
        "detail": "old active source line should not appear outside HTML comments",
    })

    checks.append({
        "name": "auto_applied_marker_exists",
        "ok": marker in html,
        "detail": marker,
    })

    checks.append({
        "name": "active_ids_preserved",
        "ok": len(missing_ids) == 0,
        "detail": "missing ids: " + (", ".join(missing_ids) if missing_ids else "none"),
    })

    checks.extend(structure_checks_for_file(source_file, backup_html, html))

    parse_ok, parse_errors = validate_html_parse(html)
    checks.append({
        "name": "basic_html_parse",
        "ok": parse_ok,
        "detail": "ok" if parse_ok else "; ".join(parse_errors),
    })

    all_ok = all(c["ok"] for c in checks)
    restored = False

    if all_ok:
        result = "post_validated"
        state["current_stage"] = "post_validated"
        state["next_action"] = "Record learning outcome and allow selector to continue next improvement cycle."
    else:
        restore_backup(backup, full_path)
        restored = True
        result = "rolled_back"
        state["current_stage"] = "rolled_back"
        state["next_action"] = "Investigate failed post-apply validation before next auto-apply attempt."

    git_after, git_after_err = git_status()

    report_path = write_report(
        state_before=state_before,
        checks=checks,
        result=result,
        restored=restored,
        source_file=source_file,
        backup=backup,
        git_before=git_before,
        git_after=git_after,
    )

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "simplicity_post_apply_validator_v3_dynamic_structure",
        "stage_before": "applied",
        "stage_after": result,
        "target_family": target_family,
        "source_file": source_file,
        "line": line_no,
        "restored_from_backup": restored,
        "report": str(report_path),
        "git_commit": False,
        "deploy": False,
    })

    state["last_post_apply_validation"] = {
        "at": now_iso(),
        "topic": "simplicity",
        "target_family": target_family,
        "stage_before": "applied",
        "stage_after": result,
        "source_file": source_file,
        "line": line_no,
        "checks": checks,
        "restored_from_backup": restored,
        "backup": backup,
        "report": str(report_path),
        "git_commit": False,
        "deploy": False,
    }

    state["updated_at"] = now_iso()
    save_state(state)

    print("post_apply_validator_result =", result)
    print("restored_from_backup =", str(restored).lower())
    print("post_apply_validation_report =", report_path)
    print("git_commit = false")
    print("deploy = false")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
