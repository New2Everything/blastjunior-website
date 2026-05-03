#!/usr/bin/env python3
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

SOURCE_SUFFIXES = {".html", ".htm", ".js", ".mjs"}

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

def strip_comments(text):
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)

def strip_tags(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&")
    return re.sub(r"\s+", " ", text).strip()

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

def classify_anchor(text, href):
    label = text.strip()
    href = href.strip()

    protected_keywords = [
        "首页", "Home", "登录", "Login", "注册", "Register",
        "个人", "Profile", "上传", "Upload", "投稿", "发布"
    ]

    low_priority_keywords = [
        "画廊", "Gallery", "成员", "Member", "赞助", "Sponsor",
        "关于", "About", "联系", "Contact"
    ]

    if any(k in label or k.lower() in href.lower() for k in protected_keywords):
        return "protected", "core_navigation_or_account_action"

    if any(k in label or k.lower() in href.lower() for k in low_priority_keywords):
        return "candidate", "potential_low_priority_navigation_entry"

    return "review", "needs_more_context"

def find_nav_anchors():
    anchors = []

    for file_path in iter_source_files():
        try:
            raw = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        text = strip_comments(raw)
        rel = str(file_path.relative_to(WORKSPACE))

        for nav_match in re.finditer(r"<nav\b[^>]*>.*?</nav>", text, flags=re.I | re.S):
            nav_block = nav_match.group(0)
            nav_start = nav_match.start()

            for a in re.finditer(
                r"<a\b([^>]*)\bhref=[\"']([^\"']+)[\"']([^>]*)>(.*?)</a>",
                nav_block,
                flags=re.I | re.S
            ):
                attrs_before = a.group(1) or ""
                href = a.group(2) or ""
                attrs_after = a.group(3) or ""
                inner = a.group(4) or ""

                full_anchor = a.group(0)
                anchor_start = nav_start + a.start()
                line = text.count("\n", 0, anchor_start) + 1
                label = strip_tags(inner)

                status, reason = classify_anchor(label, href)

                anchors.append({
                    "file": rel,
                    "line": line,
                    "href": href,
                    "label": label,
                    "status": status,
                    "reason": reason,
                    "text": re.sub(r"\s+", " ", full_anchor).strip(),
                    "attrs": re.sub(r"\s+", " ", (attrs_before + " " + attrs_after)).strip(),
                    "source_changed": False,
                })

    return anchors

def write_report(state_before, anchors):
    report_path = REPORT_DIR / f"simplicity-nav-discover-{stamp()}.md"

    candidates = [a for a in anchors if a["status"] == "candidate"]
    protected = [a for a in anchors if a["status"] == "protected"]
    review = [a for a in anchors if a["status"] == "review"]

    lines = []
    lines.append("# Simplicity Nav Discover Report")
    lines.append("")
    lines.append(f"- generated_at: `{now_iso()}`")
    lines.append(f"- topic: `{state_before.get('current_topic')}`")
    lines.append(f"- stage_before: `{state_before.get('current_stage')}`")
    lines.append("- target_family: `simplicity.nav_anchor_deprioritize`")
    lines.append("- source_changed: `false`")
    lines.append(f"- total_nav_anchors: `{len(anchors)}`")
    lines.append(f"- candidate_count: `{len(candidates)}`")
    lines.append(f"- protected_count: `{len(protected)}`")
    lines.append(f"- review_count: `{len(review)}`")
    lines.append("")

    for title, group in [
        ("Candidate anchors", candidates),
        ("Protected anchors", protected),
        ("Review anchors", review),
    ]:
        lines.append(f"## {title}")
        lines.append("")
        if not group:
            lines.append("none")
            lines.append("")
            continue

        for a in group:
            lines.append(f"### `{a['file']}:{a['line']}`")
            lines.append("")
            lines.append(f"- label: `{a['label']}`")
            lines.append(f"- href: `{a['href']}`")
            lines.append(f"- status: `{a['status']}`")
            lines.append(f"- reason: `{a['reason']}`")
            lines.append("")
            lines.append("```html")
            lines.append(a["text"])
            lines.append("```")
            lines.append("")

    lines.append("## Conclusion")
    lines.append("")
    if candidates:
        lines.append("Nav candidates were found. Next step: build a strict nav proposal executor before any source change.")
    else:
        lines.append("No safe nav candidates were found. The system should not modify nav source yet.")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path

def main():
    state = load_state()
    topic = state.get("current_topic")
    stage = state.get("current_stage")

    print("nav_discover_topic =", topic)
    print("nav_discover_stage =", stage)

    if topic != "simplicity" or stage != "nav_discover":
        print("nav_discover_skip = true")
        return 0

    state_before = json.loads(json.dumps(state, ensure_ascii=False))
    anchors = find_nav_anchors()
    report_path = write_report(state_before, anchors)

    candidates = [a for a in anchors if a["status"] == "candidate"]

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "simplicity_nav_discover_executor",
        "stage_before": "nav_discover",
        "stage_after": "nav_inventory_ready" if candidates else "nav_inventory_blocked",
        "candidate_count": len(candidates),
        "total_nav_anchors": len(anchors),
        "source_changed": False,
        "report": str(report_path),
    })

    state["last_nav_discover"] = {
        "at": now_iso(),
        "topic": "simplicity",
        "target_family": "simplicity.nav_anchor_deprioritize",
        "stage_before": "nav_discover",
        "stage_after": "nav_inventory_ready" if candidates else "nav_inventory_blocked",
        "anchors": anchors,
        "candidates": candidates,
        "candidate_count": len(candidates),
        "total_nav_anchors": len(anchors),
        "report": str(report_path),
        "source_changed": False,
    }

    if candidates:
        state["current_stage"] = "nav_inventory_ready"
        state["next_action"] = "Build nav proposal executor. Do not modify nav source until strict candidate rules are added."
        print("nav_discover_result = nav_inventory_ready")
    else:
        state["current_stage"] = "nav_inventory_blocked"
        state["next_action"] = "No safe nav candidate found. Choose another target family."
        print("nav_discover_result = nav_inventory_blocked")

    state["updated_at"] = now_iso()
    save_state(state)

    print("candidate_count =", len(candidates))
    print("total_nav_anchors =", len(anchors))
    print("nav_discover_report =", report_path)
    print("source_changed = false")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
