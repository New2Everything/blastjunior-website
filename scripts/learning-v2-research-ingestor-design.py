#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

DESIGN_ID = "learning-v2-research-ingestor-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

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

    result = "ok" if not failures else "blocked"

    design = {
        "generated_at": now_iso(),
        "design_id": DESIGN_ID,
        "result": result,
        "failures": failures,
        "current_state": {
            "mode": policy.get("mode"),
            "current_topic": state.get("current_topic"),
            "current_stage": state.get("current_stage"),
            "current_target_family": state.get("current_target_family"),
            "disabled_target_families": state.get("disabled_target_families") or [],
            "system_integrity": integrity.get("result"),
            "drift_count": integrity.get("drift_count"),
            "allow_source_changes": state.get("allow_source_changes"),
            "allow_git_commit": state.get("allow_git_commit"),
            "allow_deploy": state.get("allow_deploy"),
        },
        "purpose": {
            "one_sentence": "Let learning-v2 actively learn external website design knowledge, distill it into reusable design patterns, and convert patterns into safe target-family candidates.",
            "not_goal": [
                "Do not modify website source.",
                "Do not auto-commit.",
                "Do not auto-push.",
                "Do not auto-deploy.",
                "Do not treat external advice as directly executable source changes.",
            ],
        },
        "research_loop": [
            {
                "stage": "research_query_plan",
                "description": "Generate controlled research questions for web design, UX, accessibility, mobile navigation, information hierarchy, and conversion design.",
                "writes_state": False,
                "writes_business_source": False,
            },
            {
                "stage": "research_collect",
                "description": "Collect or receive external sources. v0 may be manual/offline; future versions may use controlled web search.",
                "writes_state": False,
                "writes_business_source": False,
            },
            {
                "stage": "research_digest",
                "description": "Summarize sources into concise claims with source metadata and confidence.",
                "writes_state": False,
                "writes_business_source": False,
            },
            {
                "stage": "pattern_extract",
                "description": "Extract reusable design patterns from research digests.",
                "writes_state": False,
                "writes_business_source": False,
            },
            {
                "stage": "target_family_propose",
                "description": "Map patterns to possible observe-only target families for this website.",
                "writes_state": False,
                "writes_business_source": False,
            }
        ],
        "proposed_artifacts": {
            "research_queries_jsonl": "learning-v2/research/queries.jsonl",
            "research_sources_jsonl": "learning-v2/research/sources.jsonl",
            "research_digests_jsonl": "learning-v2/research/digests.jsonl",
            "design_patterns_jsonl": "learning-v2/research/design-patterns.jsonl",
            "target_family_candidates_jsonl": "learning-v2/research/target-family-candidates.jsonl",
        },
        "source_quality_policy": {
            "preferred_sources": [
                "official design systems",
                "accessibility standards and guidelines",
                "credible UX research papers",
                "well-documented product case studies",
                "high-quality website examples with clear rationale"
            ],
            "avoid_sources": [
                "thin SEO listicles without evidence",
                "unattributed design opinions",
                "outdated advice without context",
                "visual inspiration without interaction rationale"
            ],
            "minimum_metadata": [
                "title",
                "source_type",
                "publisher_or_author",
                "url_or_reference",
                "retrieved_or_created_at",
                "topic",
                "claim_summary",
                "confidence"
            ]
        },
        "pattern_schema": {
            "pattern_id": "stable slug",
            "topic": "e.g. mobile-first / accessibility-basics / content-hierarchy",
            "principle": "short design principle",
            "evidence": "why this pattern matters",
            "applicability": "where it might apply on this website",
            "risk": "low / medium / high",
            "suggested_target_family": "future target-family slug",
            "requires_source_change": False,
            "observe_only_first": True
        },
        "guardrails": {
            "research_must_not_write_business_source": True,
            "research_must_not_create_apply_ready": True,
            "patterns_must_be_reviewed_as_observe_only_first": True,
            "new_target_family_must_probe_before_review": True,
            "new_target_family_must_have_dispatch_dry_run_before_apply": True,
            "source_change_allowed_required_before_any_website_edit": True,
        },
        "recommended_next_step": {
            "script": "learning-v2-research-query-planner.py",
            "goal": "Generate a controlled set of research questions and candidate source categories.",
            "must_be_dry_run_first": True,
            "must_not_browse_yet": True,
            "must_not_write_state": True,
        },
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "design_only": True,
        },
    }

    out_json = REPORT_DIR / f"research-ingestor-design-{stamp()}.json"
    out_md = REPORT_DIR / f"research-ingestor-design-{stamp()}.md"

    out_json.write_text(json.dumps(design, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Research Ingestor v0 Design")
    lines.append("")
    lines.append(f"- generated_at: `{design['generated_at']}`")
    lines.append(f"- design_id: `{DESIGN_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append("- source_changed: `false`")
    lines.append("- state_written: `false`")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append(design["purpose"]["one_sentence"])
    lines.append("")
    lines.append("## What this is not")
    lines.append("")
    for x in design["purpose"]["not_goal"]:
        lines.append(f"- {x}")
    lines.append("")
    lines.append("## Research loop")
    lines.append("")
    for item in design["research_loop"]:
        lines.append(f"### `{item['stage']}`")
        lines.append("")
        lines.append(item["description"])
        lines.append("")
        lines.append(f"- writes_state: `{str(item['writes_state']).lower()}`")
        lines.append(f"- writes_business_source: `{str(item['writes_business_source']).lower()}`")
        lines.append("")
    lines.append("## Proposed artifacts")
    lines.append("")
    for k, v in design["proposed_artifacts"].items():
        lines.append(f"- `{k}` -> `{v}`")
    lines.append("")
    lines.append("## Pattern schema")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(design["pattern_schema"], ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Guardrails")
    lines.append("")
    for k, v in design["guardrails"].items():
        lines.append(f"- `{k}` = `{str(v).lower()}`")
    lines.append("")
    lines.append("## Recommended next step")
    lines.append("")
    lines.append(f"- script: `{design['recommended_next_step']['script']}`")
    lines.append(f"- goal: {design['recommended_next_step']['goal']}")
    lines.append("- dry-run first: `true`")
    lines.append("- browse now: `false`")
    lines.append("- write state: `false`")
    lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("research_ingestor_design =", result)
    print("design_id =", DESIGN_ID)
    print("design_json =", out_json)
    print("design_md =", out_md)
    print("recommended_next_step = learning-v2-research-query-planner.py")
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

if __name__ == "__main__":
    main()
