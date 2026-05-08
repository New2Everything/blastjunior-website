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

DISCOVERER_ID = "learning-v2-design-opportunity-discoverer-v0.2"

PUBLIC_FILES = [
    "public/index.html",
    "public/about.html",
    "public/gallery.html",
    "public/news.html",
    "public/profile.html",
    "public/standings.html",
    "public/teams.html",
]

DESIGN_CAPABILITY_CANDIDATES = [
    {
        "target_family": "event.storytelling_path",
        "lane": "design_capability_scan",
        "opportunity_type": "missing_capability",
        "capability": "event storytelling path",
        "criticality": "normal",
        "why_this_matters": "Events and competitions are emotional proof of community value, not just news items.",
        "expected_user_value": "Visitors can feel the club story, competitive spirit, and community identity.",
        "keywords": ["故事", "赛事故事", "比赛精神", "对抗赛", "荣耀", "反败为胜"],
        "suggested_scope": "public/news.html or new story section",
    },
    {
        "target_family": "beginner.hado_explanation",
        "lane": "design_capability_scan",
        "opportunity_type": "missing_capability",
        "capability": "beginner HADO explanation layer",
        "criticality": "normal",
        "why_this_matters": "First-time visitors may not understand what HADO is, how it works, or why it matters.",
        "expected_user_value": "A beginner can understand HADO in one short path without external explanation.",
        "keywords": ["什么是HADO", "HADO是什么", "新手", "第一次", "怎么玩", "AR竞技"],
        "suggested_scope": "public/index.html or public/about.html",
    },
    {
        "target_family": "parent.trust_path",
        "lane": "design_capability_scan",
        "opportunity_type": "missing_capability",
        "capability": "parent trust path",
        "criticality": "normal",
        "why_this_matters": "Parents who do not know HADO need a clear trust-building path before they allow children to participate.",
        "expected_user_value": "A parent can quickly understand safety, value, community, and next step.",
        "keywords": ["家长", "安全", "信任", "孩子", "成长", "为什么参加"],
        "suggested_scope": "public/about.html or public/index.html",
    },
    {
        "target_family": "conversion.inquiry_path",
        "lane": "design_capability_scan",
        "opportunity_type": "experience_friction",
        "capability": "clear inquiry or joining path",
        "criticality": "normal",
        "why_this_matters": "Users who are interested need a simple next action, otherwise interest is lost.",
        "expected_user_value": "A parent or student knows exactly how to try, join, ask, or visit.",
        "keywords": ["报名", "咨询", "加入", "体验", "联系我们", "预约"],
        "suggested_scope": "public/index.html, public/about.html, navigation",
    },
    {
        "target_family": "school.competition_journey",
        "lane": "design_capability_scan",
        "opportunity_type": "missing_capability",
        "capability": "school / club / competition journey",
        "criticality": "normal",
        "why_this_matters": "The site should explain how a child moves from beginner to club member to competition participant.",
        "expected_user_value": "Families can see a growth path rather than a one-time activity.",
        "keywords": ["成长路径", "校队", "俱乐部", "联赛", "训练", "比赛"],
        "suggested_scope": "public/about.html or dedicated journey section",
    },
    {
        "target_family": "community.identity_path",
        "lane": "design_capability_scan",
        "opportunity_type": "experience_friction",
        "capability": "community belonging path",
        "criticality": "normal",
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

def read_text(rel):
    p = WORKSPACE / rel
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore")

def count_jsonl(path):
    if not path.exists():
        return 0
    return len([line for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()])

def public_file_exists(rel):
    return (WORKSPACE / rel).exists()

def keyword_hits(text, keywords):
    hits = []
    low = text.lower()
    for kw in keywords:
        if kw.lower() in low:
            hits.append(kw)
    return hits

def scan_site_texts():
    return {rel: read_text(rel) for rel in PUBLIC_FILES}

def get_attr(tag, attr):
    m = re.search(attr + r'=["\\\']([^"\\\']+)["\\\']', tag, flags=re.I)
    return m.group(1).strip() if m else None

def is_external_or_nonlocal_ref(ref):
    return not ref or ref.startswith((
        "http://",
        "https://",
        "mailto:",
        "tel:",
        "#",
        "javascript:",
        "data:",
    ))

def extract_internal_links(text):
    # Only anchor href values are page navigation links.
    # Asset href values such as stylesheet links are scanned separately.
    links = []
    for m in re.finditer(r'<a\b[^>]*href=["\\\']([^"\\\']+)["\\\']', text, flags=re.I):
        href = m.group(1).strip()
        if is_external_or_nonlocal_ref(href):
            continue
        links.append(href)
    return links

def normalize_local_asset_ref(ref, source_file):
    if is_external_or_nonlocal_ref(ref):
        return None

    clean = ref.split("#", 1)[0].split("?", 1)[0].strip()
    if not clean:
        return None

    if clean.startswith("/"):
        return "public/" + clean[1:]

    if clean.startswith("public/"):
        return clean

    return str((Path(source_file).parent / clean).as_posix())

def extract_asset_refs(source_file, text):
    refs = []

    for m in re.finditer(r'<link\b[^>]*>', text, flags=re.I):
        tag = m.group(0)
        href = get_attr(tag, "href")
        rel = (get_attr(tag, "rel") or "").lower()
        if href and ("stylesheet" in rel or href.lower().split("?", 1)[0].endswith(".css")):
            refs.append({
                "source_file": source_file,
                "tag": "link",
                "ref": href,
                "normalized_target": normalize_local_asset_ref(href, source_file),
            })

    for m in re.finditer(r'<script\b[^>]*>', text, flags=re.I):
        tag = m.group(0)
        src = get_attr(tag, "src")
        if src:
            refs.append({
                "source_file": source_file,
                "tag": "script",
                "ref": src,
                "normalized_target": normalize_local_asset_ref(src, source_file),
            })

    for m in re.finditer(r'<img\b[^>]*>', text, flags=re.I):
        tag = m.group(0)
        src = get_attr(tag, "src")
        if src:
            refs.append({
                "source_file": source_file,
                "tag": "img",
                "ref": src,
                "normalized_target": normalize_local_asset_ref(src, source_file),
            })

    return [x for x in refs if x["normalized_target"]]

def normalize_local_href(href):
    href = href.split("#", 1)[0].split("?", 1)[0]
    if not href:
        return None
    if href.startswith("/"):
        href = href[1:]
    if href.endswith("/"):
        href = href[:-1]
    if not href:
        return "public/index.html"
    if "." not in Path(href).name:
        href = href + ".html"
    if not href.startswith("public/"):
        href = "public/" + href
    return href

def scan_quality_bugs(site_texts):
    candidates = []

    # 1) Missing expected public files.
    expected = [
        "public/index.html",
        "public/news.html",
        "public/gallery.html",
        "public/about.html",
    ]
    missing = [rel for rel in expected if not public_file_exists(rel)]
    if missing:
        candidates.append({
            "target_family": "quality.missing_expected_public_file",
            "lane": "quality_bug_scan",
            "opportunity_type": "bug_fix",
            "criticality": "high",
            "capability": "expected public files exist",
            "why_this_matters": "A missing expected public page can break navigation or user access.",
            "expected_user_value": "Users can open expected site pages without 404.",
            "suggested_scope": ", ".join(missing),
            "evidence": {"missing_files": missing},
            "score": 120,
        })

    # 2) Missing local asset references.
    missing_assets = []
    for rel, text in site_texts.items():
        for asset in extract_asset_refs(rel, text):
            target = asset.get("normalized_target")
            if target and not (WORKSPACE / target).exists():
                missing_assets.append(asset)

    if missing_assets:
        candidates.append({
            "target_family": "quality.missing_asset_reference",
            "lane": "quality_bug_scan",
            "opportunity_type": "bug_fix",
            "criticality": "high",
            "capability": "local asset references resolve",
            "why_this_matters": "Missing CSS, JS, or image assets can break page styling, behavior, or visual meaning.",
            "expected_user_value": "Users see correctly styled and functional pages.",
            "suggested_scope": "asset references / affected source files",
            "evidence": {"missing_assets": missing_assets[:20], "missing_asset_count": len(missing_assets)},
            "score": 118,
        })

    # 3) Broken local internal page href targets.
    broken_links = []
    for rel, text in site_texts.items():
        for href in extract_internal_links(text):
            target = normalize_local_href(href)
            if not target:
                continue
            if not (WORKSPACE / target).exists():
                broken_links.append({
                    "source_file": rel,
                    "href": href,
                    "normalized_target": target,
                })

    if broken_links:
        candidates.append({
            "target_family": "quality.broken_internal_links",
            "lane": "quality_bug_scan",
            "opportunity_type": "bug_fix",
            "criticality": "high",
            "capability": "internal page links resolve",
            "why_this_matters": "Broken internal page links create direct navigation failures.",
            "expected_user_value": "Users can navigate without hitting missing local pages.",
            "suggested_scope": "public navigation / affected source files",
            "evidence": {"broken_links": broken_links[:20], "broken_link_count": len(broken_links)},
            "score": 115,
        })

    # 3) Obvious duplicate nav labels in nav component.
    nav_text = read_text("components/nav.html")
    if nav_text:
        labels = re.findall(r'<a[^>]*>([^<]+)</a>', nav_text, flags=re.I)
        clean = [x.strip() for x in labels if x.strip()]
        dupes = sorted({x for x in clean if clean.count(x) > 1})
        if dupes:
            candidates.append({
                "target_family": "quality.duplicate_navigation",
                "lane": "quality_bug_scan",
                "opportunity_type": "bug_fix",
                "criticality": "medium",
                "capability": "navigation labels are not duplicated unintentionally",
                "why_this_matters": "Duplicate navigation can confuse users and weaken wayfinding.",
                "expected_user_value": "Users see a clear navigation structure.",
                "suggested_scope": "components/nav.html",
                "evidence": {"duplicate_labels": dupes},
                "score": 85,
            })

    # 4) Missing title in key public pages.
    missing_titles = []
    for rel, text in site_texts.items():
        if text and not re.search(r'<title>.+?</title>', text, flags=re.I | re.S):
            missing_titles.append(rel)
    if missing_titles:
        candidates.append({
            "target_family": "quality.missing_page_title",
            "lane": "quality_bug_scan",
            "opportunity_type": "bug_fix",
            "criticality": "medium",
            "capability": "public pages have title tags",
            "why_this_matters": "Missing title tags hurt usability, SEO, and browser navigation.",
            "expected_user_value": "Users and search engines can identify each page.",
            "suggested_scope": ", ".join(missing_titles),
            "evidence": {"missing_titles": missing_titles},
            "score": 80,
        })

    return sorted(candidates, key=lambda x: x["score"], reverse=True)

def score_design_candidate(candidate, site_texts, disabled_families, applied_targets):
    all_text = "\n".join(site_texts.values())
    hits = keyword_hits(all_text, candidate["keywords"])

    is_disabled = candidate["target_family"] in disabled_families
    applied_text = json.dumps(applied_targets, ensure_ascii=False)
    was_applied = candidate["target_family"] in applied_text

    if candidate["opportunity_type"] == "missing_capability":
        score = 80
        if not hits:
            score += 15
        else:
            score -= min(len(hits) * 5, 20)
    elif candidate["opportunity_type"] == "experience_friction":
        score = 65
        if hits:
            score += min(len(hits) * 3, 15)
    else:
        score = 40

    if is_disabled:
        score -= 100
    if was_applied:
        score -= 20

    out = dict(candidate)
    out.update({
        "score": score,
        "keyword_hits": hits,
        "is_disabled": is_disabled,
        "was_previously_applied_or_related": was_applied,
        "evidence": {
            "keyword_hits": hits,
            "scan_method": "local public html keyword scan",
            "absence_supports_missing_capability": not hits and candidate["opportunity_type"] == "missing_capability",
        },
    })
    return out

def select_recommendation(quality_bug_candidates, design_capability_candidates):
    critical_bugs = [
        c for c in quality_bug_candidates
        if c.get("criticality") == "high"
    ]
    if critical_bugs:
        return critical_bugs[0], "quality_bug_scan", "critical quality bug exists; bug_fix takes priority"

    if design_capability_candidates:
        return design_capability_candidates[0], "design_capability_scan", "no critical bug found; choose highest-value design evolution candidate"

    if quality_bug_candidates:
        return quality_bug_candidates[0], "quality_bug_scan", "no design candidate found; choose available quality candidate"

    return None, None, "no candidate found"

def main():
    state = load_json(STATE, default={}) or {}
    disabled = state.get("disabled_target_families") or []
    applied = state.get("applied_targets") or []
    site_texts = scan_site_texts()

    quality_bug_candidates = scan_quality_bugs(site_texts)

    design_capability_candidates = [
        score_design_candidate(c, site_texts, disabled, applied)
        for c in DESIGN_CAPABILITY_CANDIDATES
    ]
    design_capability_candidates.sort(key=lambda x: x["score"], reverse=True)

    recommended, recommended_lane, selection_reason = select_recommendation(
        quality_bug_candidates,
        design_capability_candidates,
    )

    result = "candidate_found" if recommended else "no_candidate"

    payload = {
        "generated_at": now_iso(),
        "discoverer_id": DISCOVERER_ID,
        "result": result,
        "objective": "self_learning_self_evolving_website_design_system_plus_quality_maintenance",
        "lanes": [
            "quality_bug_scan",
            "design_capability_scan",
        ],
        "current_topic": state.get("current_topic"),
        "current_stage": state.get("current_stage"),
        "current_target_family": state.get("current_target_family"),
        "applied_targets_count": len(applied),
        "disabled_target_families_count": len(disabled),
        "patterns_count": count_jsonl(PATTERNS),
        "outcomes_count": count_jsonl(OUTCOMES),
        "quality_bug_candidates": quality_bug_candidates,
        "design_capability_candidates": design_capability_candidates,
        "recommended_candidate": recommended,
        "recommended_lane": recommended_lane,
        "selection_reason": selection_reason,
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
        f"- quality_bug_candidates_count: `{len(quality_bug_candidates)}`",
        f"- design_capability_candidates_count: `{len(design_capability_candidates)}`",
        f"- recommended_lane: `{recommended_lane}`",
        f"- selection_reason: {selection_reason}",
        "",
        "## Recommended Candidate",
        "",
    ]

    if recommended:
        lines += [
            f"- target_family: `{recommended.get('target_family')}`",
            f"- lane: `{recommended.get('lane')}`",
            f"- opportunity_type: `{recommended.get('opportunity_type')}`",
            f"- criticality: `{recommended.get('criticality')}`",
            f"- capability: {recommended.get('capability')}",
            f"- score: `{recommended.get('score')}`",
            f"- suggested_scope: `{recommended.get('suggested_scope')}`",
            "",
            "### Why this matters",
            "",
            recommended.get("why_this_matters", ""),
            "",
            "### Expected user value",
            "",
            recommended.get("expected_user_value", ""),
        ]
    else:
        lines.append("- none")

    lines += [
        "",
        "## Quality Bug Candidates",
        "",
    ]

    if quality_bug_candidates:
        for c in quality_bug_candidates:
            lines.append(
                f"- `{c['target_family']}` | criticality=`{c['criticality']}` | score=`{c['score']}` | scope=`{c['suggested_scope']}`"
            )
    else:
        lines.append("- none")

    lines += [
        "",
        "## Design Capability Candidates",
        "",
    ]

    for c in design_capability_candidates:
        lines.append(
            f"- `{c['target_family']}` | type=`{c['opportunity_type']}` | score=`{c['score']}` | disabled=`{str(c.get('is_disabled')).lower()}` | hits={c.get('keyword_hits')}"
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
    print("quality_bug_candidates_count =", len(quality_bug_candidates))
    print("design_capability_candidates_count =", len(design_capability_candidates))
    if recommended:
        print("recommended_lane =", recommended_lane)
        print("recommended_target_family =", recommended.get("target_family"))
        print("recommended_opportunity_type =", recommended.get("opportunity_type"))
        print("recommended_criticality =", recommended.get("criticality"))
        print("recommended_score =", recommended.get("score"))
        print("selection_reason =", selection_reason)
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("website_files_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
