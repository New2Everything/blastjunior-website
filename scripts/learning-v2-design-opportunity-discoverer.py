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
OUTCOMES = BASE / "outcomes.jsonl"
PATTERNS = BASE / "patterns.jsonl"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

DISCOVERER_ID = "learning-v2-design-opportunity-discoverer-v0"

OPPORTUNITY_TYPES = [
    "bug_fix",
    "experience_friction",
    "missing_capability",
]

PUBLIC_FILES = [
    "public/index.html",
    "public/about.html",
    "public/gallery.html",
    "public/news.html",
    "public/profile.html",
    "public/standings.html",
    "public/teams.html",
]

CAPABILITY_CANDIDATES = [
    {
        "target_family": "parent.trust_path",
        "opportunity_type": "missing_capability",
        "capability": "parent trust path",
        "why_this_matters": "Parents who do not know HADO need a clear trust-building path before they allow children to participate.",
        "expected_user_value": "A parent can quickly understand safety, value, community, and next step.",
        "keywords": ["家长", "安全", "信任", "孩子", "成长", "为什么参加"],
        "suggested_scope": "public/about.html or public/index.html",
    },
    {
        "target_family": "beginner.hado_explanation",
        "opportunity_type": "missing_capability",
        "capability": "beginner HADO explanation layer",
        "why_this_matters": "First-time visitors may not understand what HADO is, how it works, or why it matters.",
        "expected_user_value": "A beginner can understand HADO in one short path without external explanation.",
        "keywords": ["什么是HADO", "HADO是什么", "新手", "第一次", "怎么玩", "AR竞技"],
        "suggested_scope": "public/index.html or public/about.html",
    },
    {
        "target_family": "event.storytelling_path",
        "opportunity_type": "missing_capability",
        "capability": "event storytelling path",
        "why_this_matters": "Events and competitions are emotional proof of community value, not just news items.",
        "expected_user_value": "Visitors can feel the club story, competitive spirit, and community identity.",
        "keywords": ["故事", "赛事故事", "比赛精神", "对抗赛", "荣耀", "反败为胜"],
        "suggested_scope": "public/news.html or new story section",
    },
    {
        "target_family": "conversion.inquiry_path",
        "opportunity_type": "experience_friction",
        "capability": "clear inquiry or joining path",
        "why_this_matters": "Users who are interested need a simple next action, otherwise interest is lost.",
        "expected_user_value": "A parent or student knows exactly how to try, join, ask, or visit.",
        "keywords": ["报名", "咨询", "加入", "体验", "联系我们", "预约"],
        "suggested_scope": "public/index.html, public/about.html, navigation",
    },
    {
        "target_family": "school.competition_journey",
        "opportunity_type": "missing_capability",
        "capability": "school / club / competition journey",
        "why_this_matters": "The site should explain how a child moves from beginner to club member to competition participant.",
        "expected_user_value": "Families can see a growth path rather than a one-time activity.",
        "keywords": ["成长路径", "校队", "俱乐部", "联赛", "训练", "比赛"],
        "suggested_scope": "public/about.html or dedicated journey section",
    },
    {
        "target_family": "community.identity_path",
        "opportunity_type": "experience_friction",
        "capability": "community belonging path",
        "why_this_matters": "A club website should make users feel there is a living community, not only pages of information.",
        "expected_user_value": "Visitors understand who the community is and why they may want to belong.",
        "keywords": ["社区", "伙伴", "队友", "归属", "兰星少年", "HADOer"],
        "suggested_scope": "public/about.html, public/gallery.html",
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
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def read_text(path):
    p = WORKSPACE / path
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore")

def count_jsonl(path):
    if not path.exists():
        return 0
    return len([line for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()])

def keyword_hits(text, keywords):
    hits = []
    for kw in keywords:
        if kw.lower() in text.lower():
            hits.append(kw)
    return hits

def scan_site_text():
    combined = {}
    for rel in PUBLIC_FILES:
        text = read_text(rel)
        combined[rel] = text
    return combined

def candidate_score(candidate, site_texts, disabled_families, applied_targets):
    all_text = "\n".join(site_texts.values())
    hits = keyword_hits(all_text, candidate["keywords"])

    is_disabled = candidate["target_family"] in disabled_families

    applied_text = json.dumps(applied_targets, ensure_ascii=False)
    was_applied = candidate["target_family"] in applied_text

    # Missing capability gets priority when evidence is weak, because absence is the opportunity.
    if candidate["opportunity_type"] == "missing_capability":
        base = 80
        if not hits:
            base += 15
        else:
            base -= min(len(hits) * 5, 20)
    elif candidate["opportunity_type"] == "experience_friction":
        base = 65
        if hits:
            base += min(len(hits) * 3, 15)
    else:
        base = 40

    if is_disabled:
        base -= 100
    if was_applied:
        base -= 20

    return {
        "score": base,
        "keyword_hits": hits,
        "is_disabled": is_disabled,
        "was_previously_applied_or_related": was_applied,
    }

def main():
    state = load_json(STATE, default={}) or {}
    disabled = state.get("disabled_target_families") or []
    applied = state.get("applied_targets") or []
    site_texts = scan_site_text()

    candidates = []
    for c in CAPABILITY_CANDIDATES:
        scoring = candidate_score(c, site_texts, disabled, applied)
        candidate = dict(c)
        candidate.update(scoring)
        candidate["evidence_source"] = [
            "local public/*.html keyword scan",
            "learning-v2 objective correction: design evolution not maintenance",
            "design opportunity loop v0 spec",
        ]
        candidate["risk_notes"] = [
            "dry-run only",
            "no website file changed",
            "requires proposal before source edits",
            "requires validation before apply",
        ]
        candidates.append(candidate)

    candidates.sort(key=lambda x: x["score"], reverse=True)

    recommended = None
    for c in candidates:
        if not c["is_disabled"]:
            recommended = c
            break

    result = "candidate_found" if recommended else "no_candidate"

    payload = {
        "generated_at": now_iso(),
        "discoverer_id": DISCOVERER_ID,
        "result": result,
        "objective": "self_learning_self_evolving_website_design_system",
        "opportunity_types": OPPORTUNITY_TYPES,
        "current_topic": state.get("current_topic"),
        "current_stage": state.get("current_stage"),
        "current_target_family": state.get("current_target_family"),
        "applied_targets_count": len(applied),
        "disabled_target_families_count": len(disabled),
        "patterns_count": count_jsonl(PATTERNS),
        "outcomes_count": count_jsonl(OUTCOMES),
        "candidates": candidates,
        "recommended_candidate": recommended,
        "policy": {
            "dry_run_only": True,
            "website_files_changed": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
        },
    }

    out_json = REPORT_DIR / f"design-opportunity-discovery-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"design-opportunity-discovery-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Design Opportunity Discovery",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- discoverer_id: `{DISCOVERER_ID}`",
        f"- result: `{result}`",
        f"- objective: `{payload['objective']}`",
        f"- patterns_count: `{payload['patterns_count']}`",
        f"- outcomes_count: `{payload['outcomes_count']}`",
        f"- current_target_family: `{payload['current_target_family']}`",
        "",
        "## Recommended Candidate",
        "",
    ]

    if recommended:
        lines += [
            f"- target_family: `{recommended['target_family']}`",
            f"- opportunity_type: `{recommended['opportunity_type']}`",
            f"- capability: {recommended['capability']}",
            f"- score: `{recommended['score']}`",
            f"- suggested_scope: `{recommended['suggested_scope']}`",
            "",
            "### Why this matters",
            "",
            recommended["why_this_matters"],
            "",
            "### Expected user value",
            "",
            recommended["expected_user_value"],
            "",
            "### Keyword hits",
            "",
        ]
        if recommended["keyword_hits"]:
            for h in recommended["keyword_hits"]:
                lines.append(f"- {h}")
        else:
            lines.append("- none; this supports a missing_capability interpretation")
    else:
        lines.append("- none")

    lines += [
        "",
        "## Candidate Ranking",
        "",
    ]

    for c in candidates:
        lines.append(
            f"- `{c['target_family']}` | type=`{c['opportunity_type']}` | score=`{c['score']}` | disabled=`{str(c['is_disabled']).lower()}` | hits={c['keyword_hits']}"
        )

    lines += [
        "",
        "## Safety",
        "",
        "- website_files_changed: `false`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
        "- restore_cloudflare_auto_deploy: `false`",
        "",
        "## Next Step",
        "",
        "If accepted, create an evidence packet and design hypothesis for the recommended candidate.",
        "",
    ]

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("design_opportunity_discovery =", result)
    if recommended:
        print("recommended_target_family =", recommended["target_family"])
        print("recommended_opportunity_type =", recommended["opportunity_type"])
        print("recommended_score =", recommended["score"])
        print("recommended_scope =", recommended["suggested_scope"])
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("website_files_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
