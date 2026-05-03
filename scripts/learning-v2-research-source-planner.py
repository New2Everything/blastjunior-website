#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
RESEARCH_DIR = BASE / "research"
REPORT_DIR = BASE / "reports"
RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

QUERIES = RESEARCH_DIR / "queries.jsonl"
SOURCE_PLAN_ID = "learning-v2-research-source-plan-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def load_queries():
    if not QUERIES.exists():
        return []
    return [
        json.loads(line)
        for line in QUERIES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

def source_strategy_for(q):
    topic = q.get("topic")
    question = q.get("research_question")
    qid = q.get("query_id")

    common = {
        "query_id": qid,
        "topic": topic,
        "research_question": question,
        "target_family_hint": q.get("target_family_hint"),
        "status": "source_plan_ready",
        "web_browsed": False,
        "source_collection_allowed_now": False,
        "source_quality_requirements": [
            "prefer primary or authoritative sources",
            "record title, publisher, URL/reference, retrieval date, and claim summary",
            "separate evidence from opinion",
            "do not convert source advice directly into website edits",
            "map each claim to observe-only target-family candidates first",
        ],
    }

    if topic == "accessibility-basics":
        common.update({
            "preferred_source_types": [
                "official accessibility guideline",
                "WAI-ARIA documentation",
                "major design system accessibility docs",
                "browser/platform accessibility reference"
            ],
            "search_queries": [
                "responsive navigation menu aria-label aria-expanded aria-controls accessibility",
                "mobile menu button aria-expanded aria-controls best practices",
                "navigation landmark aria-label accessibility guideline"
            ],
            "trusted_source_examples": [
                "W3C WAI",
                "MDN Web Docs",
                "Google Material Design accessibility",
                "Apple Human Interface Guidelines accessibility"
            ],
            "reject_if": [
                "only visual advice with no accessibility rationale",
                "no mention of keyboard, screen reader, or semantic behavior"
            ],
        })

    elif topic == "mobile-first":
        common.update({
            "preferred_source_types": [
                "mobile UX guideline",
                "design system navigation pattern",
                "case study with responsive nav examples"
            ],
            "search_queries": [
                "mobile navigation patterns community website sports club",
                "responsive navigation menu density UX best practices",
                "mobile first navigation design system examples"
            ],
            "trusted_source_examples": [
                "Nielsen Norman Group",
                "Google Material Design",
                "Apple Human Interface Guidelines",
                "Gov.uk Design System"
            ],
            "reject_if": [
                "pure visual inspiration without interaction rationale",
                "desktop-only navigation advice"
            ],
        })

    elif topic == "content-hierarchy":
        common.update({
            "preferred_source_types": [
                "content strategy guideline",
                "landing page UX research",
                "sports or education club case study"
            ],
            "search_queries": [
                "sports club homepage content hierarchy trust join events",
                "youth sports website homepage trust signals join CTA",
                "education club landing page information hierarchy parents"
            ],
            "trusted_source_examples": [
                "Nielsen Norman Group",
                "HubSpot case studies",
                "credible education marketing research",
                "official club/league website examples"
            ],
            "reject_if": [
                "generic SEO article with no UX evidence",
                "advice focused only on sales funnels without trust context"
            ],
        })

    elif topic == "conversion-design":
        common.update({
            "preferred_source_types": [
                "conversion UX case study",
                "parent decision-making content study",
                "education or youth sports marketing guide"
            ],
            "search_queries": [
                "parents trust youth sports club website join CTA",
                "youth education landing page trust signals parents",
                "sports club registration page conversion UX"
            ],
            "trusted_source_examples": [
                "Nielsen Norman Group",
                "Baymard if relevant",
                "credible education marketing case studies",
                "real youth sports club websites"
            ],
            "reject_if": [
                "aggressive conversion advice unsuitable for children/parents",
                "unattributed marketing claims"
            ],
        })

    elif topic == "event-experience":
        common.update({
            "preferred_source_types": [
                "league website case study",
                "sports schedule UX example",
                "esports event information architecture"
            ],
            "search_queries": [
                "sports league website schedule standings teams UX",
                "esports event website information architecture schedule standings",
                "community sports event website highlights teams UX"
            ],
            "trusted_source_examples": [
                "official league websites",
                "event platform UX case studies",
                "credible sports UX examples"
            ],
            "reject_if": [
                "only visual gallery with no structure",
                "ticketing-only examples unrelated to standings or teams"
            ],
        })

    elif topic == "simplicity":
        common.update({
            "preferred_source_types": [
                "information architecture guideline",
                "navigation simplification case study",
                "design system navigation guidance"
            ],
            "search_queries": [
                "navigation secondary links grouping deprioritization UX",
                "information architecture simplify navigation menu design system",
                "when to hide secondary navigation links UX"
            ],
            "trusted_source_examples": [
                "Nielsen Norman Group",
                "Gov.uk Design System",
                "Material Design navigation",
                "Atlassian Design System"
            ],
            "reject_if": [
                "advice that blindly removes links without considering user tasks",
                "pure minimalism opinion without usability rationale"
            ],
        })

    elif topic == "performance-basics":
        common.update({
            "preferred_source_types": [
                "official web performance guideline",
                "Core Web Vitals documentation",
                "mobile performance case study"
            ],
            "search_queries": [
                "mobile homepage performance budget community website",
                "Core Web Vitals interaction latency homepage UX",
                "web performance budget mobile first site guidelines"
            ],
            "trusted_source_examples": [
                "web.dev",
                "Chrome Developers",
                "MDN Web Docs",
                "Google Core Web Vitals"
            ],
            "reject_if": [
                "performance claims without metrics",
                "desktop-only performance advice"
            ],
        })

    else:
        common.update({
            "preferred_source_types": q.get("source_types") or [
                "credible UX article",
                "design system",
                "case study"
            ],
            "search_queries": [
                question,
                f"{topic} UX design pattern website case study",
                f"{topic} design system guideline"
            ],
            "trusted_source_examples": [
                "Nielsen Norman Group",
                "official design systems",
                "credible product case studies"
            ],
            "reject_if": [
                "thin article without evidence",
                "no clear source attribution"
            ],
        })

    return common

def write_report(plan, apply):
    suffix = "apply" if apply else "dry-run"
    out_json = REPORT_DIR / f"research-source-plan-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-source-plan-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Research Source Plan v0")
    lines.append("")
    lines.append(f"- generated_at: `{plan['generated_at']}`")
    lines.append(f"- source_plan_id: `{plan['source_plan_id']}`")
    lines.append(f"- result: `{plan['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- source_plan_count: `{len(plan['source_plans'])}`")
    lines.append("- web_browsed: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Source plans")
    lines.append("")

    for sp in plan["source_plans"]:
        lines.append(f"### `{sp['query_id']}`")
        lines.append("")
        lines.append(f"- topic: `{sp['topic']}`")
        lines.append(f"- target_family_hint: `{sp['target_family_hint']}`")
        lines.append(f"- source_collection_allowed_now: `{str(sp['source_collection_allowed_now']).lower()}`")
        lines.append("")
        lines.append("Preferred source types:")
        for x in sp["preferred_source_types"]:
            lines.append(f"- {x}")
        lines.append("")
        lines.append("Search queries:")
        for x in sp["search_queries"]:
            lines.append(f"- {x}")
        lines.append("")
        lines.append("Trusted source examples:")
        for x in sp["trusted_source_examples"]:
            lines.append(f"- {x}")
        lines.append("")
        lines.append("Reject if:")
        for x in sp["reject_if"]:
            lines.append(f"- {x}")
        lines.append("")

    lines.append("## Guardrails")
    lines.append("")
    for k, v in plan["guardrails"].items():
        lines.append(f"- `{k}` = `{str(v).lower()}`")
    lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")
    return out_json, out_md

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write research/source-plans.jsonl; does not browse, write state, or modify website source")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    queries = load_queries()

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("current_topic") is not None:
        failures.append(f"current_topic_not_idle:{state.get('current_topic')}")

    if state.get("current_stage") is not None:
        failures.append(f"current_stage_not_idle:{state.get('current_stage')}")

    if state.get("current_target_family") is not None:
        failures.append(f"current_target_family_not_idle:{state.get('current_target_family')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if not queries:
        failures.append("missing_research_queries")

    source_plans = [source_strategy_for(q) for q in queries]
    result = "ok" if not failures else "blocked"

    plan = {
        "generated_at": now_iso(),
        "source_plan_id": SOURCE_PLAN_ID,
        "result": result,
        "apply": args.apply,
        "query_count": len(queries),
        "source_plan_count": len(source_plans),
        "source_plans": source_plans,
        "guardrails": {
            "web_browsed": False,
            "source_collection_allowed_now": False,
            "do_not_modify_website_source": True,
            "do_not_write_state": True,
            "do_not_commit": True,
            "do_not_push": True,
            "do_not_deploy": True,
            "source_plans_are_not_evidence": True,
            "must_collect_sources_in_later_controlled_step": True,
        },
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
        "failures": failures,
    }

    report_json, report_md = write_report(plan, args.apply)

    print("research_source_planner =", result)
    print("source_plan_id =", SOURCE_PLAN_ID)
    print("query_count =", len(queries))
    print("source_plan_count =", len(source_plans))
    print("report_json =", report_json)
    print("report_md =", report_md)
    print("web_browsed = false")
    print("source_collection_allowed_now = false")
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if failures:
        print()
        print("failures:")
        for x in failures:
            print(" ", x)
        raise SystemExit(2)

    if not args.apply:
        print("source_plans_written = false")
        return 0

    out = RESEARCH_DIR / "source-plans.jsonl"
    with out.open("a", encoding="utf-8") as f:
        for sp in source_plans:
            row = dict(sp)
            row["generated_at"] = plan["generated_at"]
            row["source_plan_id"] = SOURCE_PLAN_ID
            row["status"] = "planned"
            row["web_browsed"] = False
            row["business_source_written"] = False
            row["git_commit"] = False
            row["git_push"] = False
            row["deploy"] = False
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("source_plans_written = true")
    print("source_plans_path =", out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
