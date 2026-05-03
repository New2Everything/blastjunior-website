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

QUERY_PLAN_ID = "learning-v2-research-query-plan-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def latest_design_report():
    reports = sorted(REPORT_DIR.glob("research-ingestor-design-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def build_queries():
    return [
        {
            "query_id": "rq-mobile-nav-001",
            "topic": "mobile-first",
            "priority": 100,
            "research_question": "What are proven mobile navigation patterns for small community or sports club websites?",
            "source_types": ["design system", "UX case study", "mobile navigation guideline"],
            "expected_pattern_output": "Mobile navigation density and menu toggle design principles.",
            "target_family_hint": "mobile_first.nav_density",
            "risk": "low",
        },
        {
            "query_id": "rq-accessibility-nav-001",
            "topic": "accessibility-basics",
            "priority": 95,
            "research_question": "What accessibility semantics should a responsive navigation menu expose, especially aria-label, aria-expanded, and aria-controls?",
            "source_types": ["accessibility guideline", "official standard", "design system"],
            "expected_pattern_output": "Accessible mobile nav toggle pattern.",
            "target_family_hint": "accessibility.navigation_button_semantics",
            "risk": "low",
        },
        {
            "query_id": "rq-content-hierarchy-001",
            "topic": "content-hierarchy",
            "priority": 90,
            "research_question": "How should a sports club homepage prioritize identity, trust, events, joining, and community content?",
            "source_types": ["UX article", "sports club website case", "content strategy guideline"],
            "expected_pattern_output": "Homepage primary hierarchy pattern.",
            "target_family_hint": "content_hierarchy.homepage_primary_cta",
            "risk": "low-medium",
        },
        {
            "query_id": "rq-conversion-parent-001",
            "topic": "conversion-design",
            "priority": 88,
            "research_question": "What website content helps parents trust and join a youth sports or education club?",
            "source_types": ["conversion case study", "youth sports website", "education marketing guide"],
            "expected_pattern_output": "Parent trust and join CTA pattern.",
            "target_family_hint": "conversion.parent_join_path",
            "risk": "medium",
        },
        {
            "query_id": "rq-event-ux-001",
            "topic": "event-experience",
            "priority": 82,
            "research_question": "How do strong esports or sports event websites present schedules, standings, teams, and highlights?",
            "source_types": ["event website case", "sports UX case study", "league website example"],
            "expected_pattern_output": "League information architecture pattern.",
            "target_family_hint": "event_ux.schedule_standings_cards",
            "risk": "medium",
        },
        {
            "query_id": "rq-trust-signals-001",
            "topic": "content-hierarchy",
            "priority": 78,
            "research_question": "What trust signals should a youth sports homepage show before asking users to register or join?",
            "source_types": ["UX research", "landing page case study", "education/sports website example"],
            "expected_pattern_output": "Trust-before-CTA pattern.",
            "target_family_hint": "content_hierarchy.trust_signals_before_join",
            "risk": "low-medium",
        },
        {
            "query_id": "rq-simplicity-001",
            "topic": "simplicity",
            "priority": 75,
            "research_question": "How do design systems decide which secondary links or entry points should be hidden, grouped, or deprioritized?",
            "source_types": ["design system", "information architecture guide", "navigation UX article"],
            "expected_pattern_output": "Secondary-entry deprioritization pattern.",
            "target_family_hint": "simplicity.secondary_entry_grouping",
            "risk": "medium",
        },
        {
            "query_id": "rq-visual-identity-001",
            "topic": "visual-design",
            "priority": 70,
            "research_question": "How can futuristic sports websites balance energetic branding with readability and navigation clarity?",
            "source_types": ["sports website case", "visual design article", "brand system case"],
            "expected_pattern_output": "High-energy but readable visual hierarchy pattern.",
            "target_family_hint": "visual_design.energy_readability_balance",
            "risk": "medium",
        },
        {
            "query_id": "rq-community-ux-001",
            "topic": "community-experience",
            "priority": 65,
            "research_question": "How should community features such as chat, member lists, and galleries be presented without distracting from the primary join or event paths?",
            "source_types": ["community UX article", "club website case", "product case study"],
            "expected_pattern_output": "Community surface prioritization pattern.",
            "target_family_hint": "community_ux.secondary_surface_balance",
            "risk": "medium",
        },
        {
            "query_id": "rq-performance-ux-001",
            "topic": "performance-basics",
            "priority": 60,
            "research_question": "What front-page loading and interaction performance standards matter most for mobile-first sports or community websites?",
            "source_types": ["web performance guideline", "case study", "official documentation"],
            "expected_pattern_output": "Homepage performance budget pattern.",
            "target_family_hint": "performance.homepage_interaction_budget",
            "risk": "low",
        },
    ]

def write_report(plan, apply):
    suffix = "apply" if apply else "dry-run"
    out_json = REPORT_DIR / f"research-query-plan-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-query-plan-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Research Query Plan v0")
    lines.append("")
    lines.append(f"- generated_at: `{plan['generated_at']}`")
    lines.append(f"- query_plan_id: `{plan['query_plan_id']}`")
    lines.append(f"- result: `{plan['result']}`")
    lines.append(f"- apply: `{str(apply).lower()}`")
    lines.append(f"- query_count: `{len(plan['queries'])}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- web_browsed: `false`")
    lines.append("")
    lines.append("## Queries")
    lines.append("")
    for q in plan["queries"]:
        lines.append(f"### `{q['query_id']}`")
        lines.append("")
        lines.append(f"- topic: `{q['topic']}`")
        lines.append(f"- priority: `{q['priority']}`")
        lines.append(f"- target_family_hint: `{q['target_family_hint']}`")
        lines.append(f"- risk: `{q['risk']}`")
        lines.append(f"- question: {q['research_question']}")
        lines.append(f"- expected_pattern_output: {q['expected_pattern_output']}")
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
    ap.add_argument("--apply", action="store_true", help="write research/queries.jsonl; does not write state or website source")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    design_path, design = latest_design_report()

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

    if not design_path:
        failures.append("missing_research_ingestor_design_report")

    result = "ok" if not failures else "blocked"
    queries = build_queries()

    plan = {
        "generated_at": now_iso(),
        "query_plan_id": QUERY_PLAN_ID,
        "result": result,
        "apply": args.apply,
        "design_report": str(design_path) if design_path else None,
        "queries": queries,
        "guardrails": {
            "web_browsed": False,
            "do_not_modify_website_source": True,
            "do_not_write_state": True,
            "do_not_commit": True,
            "do_not_push": True,
            "do_not_deploy": True,
            "queries_are_not_evidence": True,
            "queries_require_later_source_collection": True,
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

    print("research_query_planner =", result)
    print("query_plan_id =", QUERY_PLAN_ID)
    print("query_count =", len(queries))
    print("report_json =", report_json)
    print("report_md =", report_md)
    print("design_report =", design_path)
    print("web_browsed = false")
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
        print("research_queries_written = false")
        return 0

    out = RESEARCH_DIR / "queries.jsonl"
    with out.open("a", encoding="utf-8") as f:
        for q in queries:
            row = dict(q)
            row["generated_at"] = plan["generated_at"]
            row["query_plan_id"] = QUERY_PLAN_ID
            row["status"] = "planned"
            row["web_browsed"] = False
            row["business_source_written"] = False
            row["git_commit"] = False
            row["git_push"] = False
            row["deploy"] = False
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("research_queries_written = true")
    print("research_queries_path =", out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
