#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_ROOTS = [
    WORKSPACE / "public",
    WORKSPACE / "components",
]

SOURCE_SUFFIXES = {
    ".html", ".htm", ".js", ".mjs", ".css", ".json"
}

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

def compact_line(s, limit=220):
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    if len(s) > limit:
        return s[:limit] + "..."
    return s

def collect_target_candidates(state):
    candidates = []

    def add(x):
        if not x:
            return
        if isinstance(x, str):
            x = x.strip()
            if x and x not in candidates:
                candidates.append(x)

    proposal = state.get("proposal")
    if isinstance(proposal, dict):
        for k in ["target", "target_text", "label", "object", "selected_target"]:
            add(proposal.get(k))

    for k in [
        "validate_target",
        "apply_target",
        "selected_target",
        "target",
        "next_action",
        "current_action",
        "summary",
    ]:
        add(state.get(k))

    for fallback in [
        "更多 >",
        "更多&gt;",
        "更多 &gt;",
        "更多",
        "More >",
        "More",
    ]:
        add(fallback)

    return candidates

def iter_source_files():
    seen = set()
    for root in SOURCE_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            if p in seen:
                continue
            seen.add(p)
            yield p

def comment_line_numbers(text):
    lines = set()
    for m in re.finditer(r"<!--.*?-->", text, flags=re.S):
        start_line = text.count("\n", 0, m.start()) + 1
        end_line = text.count("\n", 0, m.end()) + 1
        for n in range(start_line, end_line + 1):
            lines.add(n)
    return lines

def is_learning_applied_comment(line):
    s = line.strip()
    return (
        "learning-v2:auto-applied" in s
        or "learning-v2 proposal" in s
        or s.startswith("<!--") and s.endswith("-->")
    )

def line_matches(line, target):
    if target in line:
        return True

    if target == "更多 >":
        return (
            "更多&gt;" in line
            or "更多 &gt;" in line
            or ("更多" in line and "&gt;" in line)
        )

    if target == "更多":
        return "更多" in line

    if target.lower() == "more":
        return "more" in line.lower()

    return False

def target_fingerprint(file_rel, line_no, text):
    return f"{file_rel}:{line_no}:{text.strip()}"

def is_allowed_active_simplicity_match(rel, line, target):
    s = line.strip()

    if rel.endswith(".css"):
        return False, "css_not_allowed_as_apply_target"

    if "learning-v2:auto-applied" in s or "learning-v2 proposal" in s:
        return False, "learning_comment_not_allowed"

    if not ("<a " in s and "section-more" in s and "href=" in s):
        return False, "not_section_more_anchor"

    has_more_arrow = (
        "更多 >" in s
        or "更多&gt;" in s
        or "更多 &gt;" in s
        or "More >" in s
    )

    if not has_more_arrow:
        return False, "section_more_anchor_without_more_arrow"

    return True, "active_section_more_anchor"

def priority_score(match):
    file = match.get("file", "")
    text = match.get("text", "")
    score = 0

    if file == "public/index.html":
        score += 100
    if file.endswith(".html") or file.endswith(".htm"):
        score += 50
    if "<a " in text and "section-more" in text:
        score += 30
    if "href=" in text:
        score += 20
    if file.endswith(".css"):
        score -= 80
    if "class=" in text and not "<a " in text:
        score -= 20

    return score

def locate_sources(state, target_candidates):
    applied_targets = set(state.get("applied_targets") or [])

    matches = []
    skipped = []
    searched_files = 0

    for file_path in iter_source_files():
        searched_files += 1
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            matches.append({
                "type": "read_error",
                "file": str(file_path),
                "error": str(e),
            })
            continue

        rel = str(file_path.relative_to(WORKSPACE))
        commented_lines = comment_line_numbers(text)
        lines = text.splitlines()

        for idx, line in enumerate(lines, start=1):
            for target in target_candidates:
                if not line_matches(line, target):
                    continue

                line_clean = compact_line(line)
                fp = target_fingerprint(rel, idx, line_clean)

                if idx in commented_lines or is_learning_applied_comment(line):
                    skipped.append({
                        "reason": "inside_html_comment_or_learning_comment",
                        "target": target,
                        "file": rel,
                        "line": idx,
                        "text": line_clean,
                    })
                    break

                if fp in applied_targets:
                    skipped.append({
                        "reason": "already_applied_target",
                        "target": target,
                        "file": rel,
                        "line": idx,
                        "text": line_clean,
                    })
                    break

                allowed, reason = is_allowed_active_simplicity_match(rel, line, target)
                if not allowed:
                    skipped.append({
                        "reason": reason,
                        "target": target,
                        "file": rel,
                        "line": idx,
                        "text": line_clean,
                    })
                    break

                matches.append({
                    "type": "match",
                    "target": target,
                    "file": rel,
                    "line": idx,
                    "text": line_clean,
                    "fingerprint": fp,
                    "priority_score": 0,
                })
                break

    for m in matches:
        if m.get("type") == "match":
            m["priority_score"] = priority_score(m)

    return searched_files, matches, skipped

def choose_primary_location(matches):
    real_matches = [m for m in matches if m.get("type") == "match"]
    if not real_matches:
        return None

    real_matches.sort(key=priority_score, reverse=True)
    return real_matches[0]

def write_report(state_before, searched_files, matches, skipped, primary, apply):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "apply" if apply else "dry-run"
    report_path = REPORT_DIR / f"simplicity-validate-locator-{suffix}-{ts}.md"

    real_matches = [m for m in matches if m.get("type") == "match"]

    lines = []
    lines.append("# Simplicity Validate Locator Report")
    lines.append("")
    lines.append(f"- generated_at: `{now_iso()}`")
    lines.append(f"- mode: `{'apply' if apply else 'dry-run'}`")
    lines.append(f"- topic: `{state_before.get('current_topic')}`")
    lines.append(f"- stage_before: `{state_before.get('current_stage')}`")
    lines.append(f"- searched_files: `{searched_files}`")
    lines.append(f"- matched_locations: `{len(real_matches)}`")
    lines.append(f"- skipped_locations: `{len(skipped)}`")
    lines.append(f"- source_changed: `false`")
    lines.append(f"- state_written: `{'true' if apply else 'false'}`")
    lines.append("")

    if primary:
        lines.append("## Primary location")
        lines.append("")
        lines.append(f"- file: `{primary['file']}`")
        lines.append(f"- line: `{primary['line']}`")
        lines.append(f"- target: `{primary['target']}`")
        lines.append(f"- priority_score: `{primary.get('priority_score')}`")
        lines.append(f"- fingerprint: `{primary.get('fingerprint')}`")
        lines.append("")
        lines.append("```html")
        lines.append(primary["text"])
        lines.append("```")
        lines.append("")
    else:
        lines.append("## Primary location")
        lines.append("")
        lines.append("No reliable active source location found.")
        lines.append("")

    lines.append("## Validation conclusion")
    lines.append("")
    if primary:
        lines.append("The validate executor found a likely active source location for the next lightweight simplicity target.")
        lines.append("")
        lines.append("Would advance to `apply_ready` if --apply is used.")
    else:
        lines.append("The validate executor did not find a reliable active location.")
        lines.append("")
        lines.append("Would advance to `validate_blocked` if --apply is used.")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually write validate result to state.json")
    args = ap.parse_args()

    state = load_state()
    topic = state.get("current_topic")
    stage = state.get("current_stage")

    print("validate_executor =", "apply" if args.apply else "dry_run")
    print("validate_executor_topic =", topic)
    print("validate_executor_stage =", stage)

    if topic != "simplicity" or stage != "validate":
        print("validate_executor_skip = true")
        print("state_written = false")
        print("source_changed = false")
        return 0

    if state.get("allow_source_changes") is not False:
        print("validate_executor_result = blocked")
        print("failure = allow_source_changes_not_false")
        raise SystemExit(2)

    if state.get("allow_git_commit") is not False:
        print("validate_executor_result = blocked")
        print("failure = allow_git_commit_not_false")
        raise SystemExit(2)

    if state.get("allow_deploy") is not False:
        print("validate_executor_result = blocked")
        print("failure = allow_deploy_not_false")
        raise SystemExit(2)

    state_before = json.loads(json.dumps(state, ensure_ascii=False))

    target_candidates = collect_target_candidates(state)
    searched_files, matches, skipped = locate_sources(state, target_candidates)
    primary = choose_primary_location(matches)
    report_path = write_report(state_before, searched_files, matches, skipped, primary, args.apply)

    real_matches = [m for m in matches if m.get("type") == "match"]

    print("searched_files =", searched_files)
    print("matched_locations =", len(real_matches))
    print("skipped_locations =", len(skipped))
    print("validate_report =", report_path)

    if primary:
        print("validate_executor_result =", "apply_ready" if args.apply else "would_apply_ready")
        print("primary_location =", f"{primary['file']}:{primary['line']}")
        print("primary_text =", primary["text"])
        would_stage = "apply_ready"
    else:
        print("validate_executor_result =", "validate_blocked" if args.apply else "would_validate_blocked")
        would_stage = "validate_blocked"

    print("would_set_stage =", would_stage)
    print("source_changed = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if not args.apply:
        print("state_written = false")
        print("state_updated = false")
        return 0

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "simplicity_validate_locator_v2",
        "stage_before": "validate",
        "matched_locations": len(real_matches),
        "skipped_locations": len(skipped),
        "report": str(report_path),
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    })

    state["last_validate"] = {
        "at": now_iso(),
        "topic": "simplicity",
        "stage_before": "validate",
        "searched_files": searched_files,
        "matched_locations": len(real_matches),
        "skipped_locations": len(skipped),
        "primary_location": primary,
        "active_locations": real_matches,
        "skipped_locations_detail": skipped,
        "report": str(report_path),
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }

    if primary:
        state["current_stage"] = "apply_ready"
        state["apply_ready"] = {
            "topic": "simplicity",
            "target": primary.get("target"),
            "primary_location": primary,
            "all_locations": real_matches,
            "skipped_locations": skipped,
            "report": str(report_path),
            "allowed_next_step": "continue autonomous guarded apply; exact-line match, backup, and post-apply validation are required",
        }
        state["next_action"] = "Build or run apply guardrails, then autonomous auto-apply executor."
    else:
        state["current_stage"] = "validate_blocked"
        state["next_action"] = "No active source location found; selector should choose another target."

    state["updated_at"] = now_iso()
    save_state(state)

    print("state_written = true")
    print("state_updated = true")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
