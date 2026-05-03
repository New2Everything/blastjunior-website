#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

PROBE_ID = "learning-v2-community-engagement-path-probe-v0"
TARGET_FAMILY = "community.engagement_path"

SCAN_FILES = [
    "public/index.html",
    "public/about.html",
    "public/gallery.html",
    "public/news.html",
    "components/nav.html",
]

DIMENSIONS = [
    {
        "dimension": "clear_engagement_next_step",
        "severity_if_missing": "high",
        "keywords": [
            "join", "try", "contact", "register", "book", "visit", "watch",
            "gallery", "event", "team", "parent", "student",
            "加入", "体验", "联系", "报名", "预约", "参观", "观看",
            "画廊", "赛事", "活动", "战队", "队伍", "家长", "学生"
        ],
        "recommendation": "Add or clarify one obvious engagement next step for new visitors.",
    },
    {
        "dimension": "low_cognitive_load_sequence",
        "severity_if_missing": "medium",
        "keywords": [
            "step", "first", "next", "start", "how", "simple",
            "1.", "2.", "3.", "①", "②", "③",
            "第一步", "第二步", "第三步", "先", "然后", "下一步", "开始", "简单"
        ],
        "recommendation": "Break the engagement path into a simple sequence so users know what to do first.",
    },
    {
        "dimension": "community_social_proof",
        "severity_if_missing": "medium",
        "keywords": [
            "team", "teams", "player", "players", "family", "club", "hpl",
            "photo", "gallery", "event", "match", "league",
            "战队", "队伍", "选手", "球员", "家庭", "家长", "俱乐部",
            "照片", "画廊", "赛事", "比赛", "联赛", "超级联赛"
        ],
        "recommendation": "Show clearer proof that real players, teams, families, and events exist.",
    },
    {
        "dimension": "return_path_after_browsing",
        "severity_if_missing": "medium",
        "keywords": [
            "join", "try", "contact", "register", "book", "next",
            "加入", "体验", "联系", "报名", "预约", "下一步"
        ],
        "recommendation": "Add a return path from browsing pages back to a concrete community action.",
    },
    {
        "dimension": "safe_navigation_to_engagement",
        "severity_if_missing": "low",
        "keywords": [
            "gallery", "teams", "standings", "news", "contact", "events",
            "画廊", "战队", "排名", "新闻", "联系", "赛事", "活动"
        ],
        "recommendation": "Expose engagement destinations clearly in navigation.",
    },
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def normalize_text(text):
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def snippet_around(text, keyword, width=70):
    low = text.lower()
    k = keyword.lower()
    idx = low.find(k)
    if idx < 0:
        return None
    start = max(0, idx - width)
    end = min(len(text), idx + len(keyword) + width)
    return text[start:end].strip()

def scan_keyword_hits(files, keywords, only_files=None):
    hits = []
    for rel, info in files.items():
        if only_files and rel not in only_files:
            continue
        text = info.get("normalized_text") or ""
        low = text.lower()
        for kw in keywords:
            if kw.lower() in low:
                hits.append({
                    "file": rel,
                    "keyword": kw,
                    "snippet": snippet_around(text, kw),
                })
                break
    return hits

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    failures = []
    warnings = []
    findings = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    for key in [
        "source_changes_allowed",
        "git_commit_allowed",
        "git_push_allowed",
        "deploy_allowed",
    ]:
        if policy.get(key) is not False:
            failures.append(f"policy_{key}_not_false:{policy.get(key)}")

    scanned = {}
    for rel in SCAN_FILES:
        p = WORKSPACE / rel
        if not p.exists():
            findings.append({
                "file": rel,
                "dimension": "file_presence",
                "status": "missing",
                "severity": "medium",
                "evidence": "",
                "missing": "Declared scan file does not exist.",
                "recommendation": "Either create this page later through a controlled source-change loop, or remove it from the engagement-path scan set if it is intentionally absent.",
            })
            scanned[rel] = {
                "exists": False,
                "size_bytes": None,
                "normalized_text": "",
            }
            continue

        if not p.is_file():
            findings.append({
                "file": rel,
                "dimension": "file_presence",
                "status": "missing",
                "severity": "medium",
                "evidence": "",
                "missing": "Declared scan path exists but is not a file.",
                "recommendation": "Replace this scan path with a real file or remove it from the probe scope.",
            })
            scanned[rel] = {
                "exists": False,
                "size_bytes": None,
                "normalized_text": "",
            }
            continue

        raw = p.read_text(encoding="utf-8", errors="ignore")
        scanned[rel] = {
            "exists": True,
            "size_bytes": p.stat().st_size,
            "normalized_text": normalize_text(raw),
        }

    existing_files = [rel for rel, info in scanned.items() if info.get("exists")]

    for dim in DIMENSIONS:
        dimension = dim["dimension"]
        keywords = dim["keywords"]

        only_files = None
        if dimension == "return_path_after_browsing":
            only_files = {"public/gallery.html", "public/news.html", "public/about.html"}
        elif dimension == "safe_navigation_to_engagement":
            only_files = {"components/nav.html", "public/index.html"}

        hits = scan_keyword_hits(scanned, keywords, only_files=only_files)

        if hits:
            if len(hits) >= 2 or dimension in ("safe_navigation_to_engagement", "community_social_proof"):
                status = "ok"
                severity = "low"
                missing = ""
            else:
                status = "review"
                severity = "medium"
                missing = "Only weak or single-location evidence found."
        else:
            status = "missing"
            severity = dim["severity_if_missing"]
            missing = "No matching engagement-path evidence found."

        evidence = "; ".join(
            [
                f"{h['file']} matched {h['keyword']}: {h['snippet'][:160] if h.get('snippet') else ''}"
                for h in hits[:5]
            ]
        )

        findings.append({
            "file": ",".join(sorted({h["file"] for h in hits})) if hits else ",".join(sorted(only_files or existing_files)),
            "dimension": dimension,
            "status": status,
            "severity": severity,
            "evidence": evidence,
            "missing": missing,
            "recommendation": dim["recommendation"],
        })

    review_or_missing_count = len([x for x in findings if x.get("status") in ("review", "missing")])
    high_or_medium_count = len([x for x in findings if x.get("severity") in ("high", "medium")])

    result = "ok" if not failures else "blocked"

    out_json = REPORT_DIR / f"community-engagement-path-probe-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"community-engagement-path-probe-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "probe_id": PROBE_ID,
        "result": result,
        "target_family": TARGET_FAMILY,
        "scan_files": SCAN_FILES,
        "existing_scan_files": existing_files,
        "finding_count": len(findings),
        "review_or_missing_count": review_or_missing_count,
        "high_or_medium_count": high_or_medium_count,
        "findings": findings,
        "policy": {
            "observe_only": True,
            "state_written": False,
            "business_source_written": False,
            "source_change_gate_opened": False,
            "human_review_required": False,
            "machine_policy_gate": True,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
        "warnings": warnings,
        "failures": failures,
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Community Engagement Path Probe")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- probe_id: `{PROBE_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- finding_count: `{len(findings)}`")
    lines.append(f"- review_or_missing_count: `{review_or_missing_count}`")
    lines.append(f"- high_or_medium_count: `{high_or_medium_count}`")
    lines.append("- observe_only: `true`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- human_review_required: `false`")
    lines.append("- machine_policy_gate: `true`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Findings")
    for f in findings:
        lines.append(f"- `{f['dimension']}` file=`{f['file']}` status=`{f['status']}` severity=`{f['severity']}`")
    if warnings:
        lines.append("")
        lines.append("## Warnings")
        for w in warnings:
            lines.append(f"- {w}")
    if failures:
        lines.append("")
        lines.append("## Failures")
        for f in failures:
            lines.append(f"- {f}")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("community_engagement_path_probe =", result)
    print("target_family =", TARGET_FAMILY)
    print("scan_files =", json.dumps(SCAN_FILES, ensure_ascii=False))
    print("existing_scan_files =", json.dumps(existing_files, ensure_ascii=False))
    print("finding_count =", len(findings))
    print("review_or_missing_count =", review_or_missing_count)
    print("high_or_medium_count =", high_or_medium_count)
    print("observe_only = True")
    print("state_written = False")
    print("business_source_written = False")
    print("source_change_gate_opened = False")
    print("human_review_required = False")
    print("machine_policy_gate = True")
    print("git_commit = False")
    print("git_push = False")
    print("deploy = False")
    print("report_json =", out_json)
    print("report_md =", out_md)
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
