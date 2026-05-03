#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
RESEARCH_DIR = BASE / "research"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PACKETS = RESEARCH_DIR / "manual-collection-packets.jsonl"

DESIGN_ID = "learning-v2-research-web-candidate-discovery-design-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def load_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    packets = load_jsonl(PACKETS)

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

    if not packets:
        failures.append("missing_manual_collection_packets")

    topics = sorted({p.get("topic") for p in packets if p.get("topic")})
    query_ids = sorted({p.get("query_id") for p in packets if p.get("query_id")})

    design = {
        "generated_at": now_iso(),
        "design_id": DESIGN_ID,
        "result": "ok" if not failures else "blocked",
        "failures": failures,
        "packet_count": len(packets),
        "topics": topics,
        "query_ids": query_ids,
        "future_executor": "learning-v2-research-web-candidate-discovery.py",
        "future_output_store": "learning-v2/research/web-source-candidates.jsonl",
        "purpose": "Use manual collection packets to discover candidate external sources, but do not ingest them directly.",
        "critical_rule": "Web discovery may only produce candidates. It must not write sources.jsonl.",
        "execution_stages": [
            {
                "stage": "candidate_discovery_dry_run",
                "web_browsing": True,
                "writes_web_source_candidates": False,
                "writes_sources_jsonl": False,
                "safe_first_step": True
            },
            {
                "stage": "candidate_discovery_apply",
                "web_browsing": True,
                "writes_web_source_candidates": True,
                "writes_sources_jsonl": False,
                "safe_after_dry_run": True
            },
            {
                "stage": "candidate_validation",
                "web_browsing": False,
                "writes_sources_jsonl": False,
                "requires_human_or_validator_review": True
            },
            {
                "stage": "real_source_intake",
                "web_browsing": False,
                "writes_sources_jsonl": True,
                "only_through_script": "learning-v2-research-real-source-intake.py"
            }
        ],
        "candidate_schema": {
            "candidate_id": "web-source-candidate-<query_id>-<timestamp>-<rank>",
            "packet_id": "manual collection packet id",
            "request_id": "real source request id",
            "query_id": "research query id",
            "topic": "research topic",
            "search_phrase": "search phrase used",
            "title": "candidate source title",
            "url": "candidate source url",
            "publisher_or_author": "publisher or author if available",
            "source_type_guess": "official guideline / design system / UX case study / paper / website case",
            "why_relevant": "short relevance explanation",
            "candidate_confidence": "low / medium / medium-high / high",
            "requires_validation_before_intake": True,
            "web_browsed_by_openclaw": True,
            "sources_jsonl_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False
        },
        "guardrails": [
            "Do not write sources.jsonl during web discovery.",
            "Do not modify website source.",
            "Do not write state.json.",
            "Do not commit, push, or deploy.",
            "Do not treat search snippets as verified source facts.",
            "Do not ingest a source without opening and validating it.",
            "Do not use generated pages, SEO spam, or unclear publishers when better sources exist.",
            "Prefer official guidelines, mature design systems, reputable UX case studies, or research papers.",
            "Every candidate must go through real-source-intake before becoming a real source.",
            "Every source must later go through digest → pattern → novelty guard."
        ],
        "recommended_next_script": {
            "name": "learning-v2-research-web-candidate-discovery.py",
            "default_mode": "dry_run",
            "first_version_should_not_browse": False,
            "first_version_should_not_write_sources": True,
            "first_version_should_write_candidates_only_with_apply": True
        },
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "web_browsed_now": False,
            "design_only": True
        }
    }

    out_json = REPORT_DIR / f"research-web-candidate-discovery-design-{stamp()}.json"
    out_md = REPORT_DIR / f"research-web-candidate-discovery-design-{stamp()}.md"

    out_json.write_text(json.dumps(design, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Web Candidate Discovery Design")
    lines.append("")
    lines.append(f"- generated_at: `{design['generated_at']}`")
    lines.append(f"- design_id: `{DESIGN_ID}`")
    lines.append(f"- result: `{design['result']}`")
    lines.append(f"- packet_count: `{len(packets)}`")
    lines.append("- web_browsed_now: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append(design["purpose"])
    lines.append("")
    lines.append("## Critical rule")
    lines.append("")
    lines.append(design["critical_rule"])
    lines.append("")
    lines.append("## Topics")
    lines.append("")
    for topic in topics:
        lines.append(f"- `{topic}`")
    lines.append("")
    lines.append("## Execution stages")
    lines.append("")
    for s in design["execution_stages"]:
        lines.append(f"### `{s['stage']}`")
        lines.append("")
        lines.append(f"- web_browsing: `{str(s.get('web_browsing')).lower()}`")
        lines.append(f"- writes_web_source_candidates: `{str(s.get('writes_web_source_candidates', False)).lower()}`")
        lines.append(f"- writes_sources_jsonl: `{str(s.get('writes_sources_jsonl', False)).lower()}`")
        lines.append("")
    lines.append("## Candidate schema")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(design["candidate_schema"], ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Guardrails")
    lines.append("")
    for g in design["guardrails"]:
        lines.append(f"- {g}")
    lines.append("")
    lines.append("## Recommended next script")
    lines.append("")
    lines.append(f"- `{design['recommended_next_script']['name']}`")
    lines.append("- default mode: `dry_run`")
    lines.append("- write candidates only with `--apply`")
    lines.append("- never write `sources.jsonl`")
    lines.append("")

    if failures:
        lines.append("## Failures")
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("research_web_candidate_discovery_design =", design["result"])
    print("design_id =", DESIGN_ID)
    print("design_json =", out_json)
    print("design_md =", out_md)
    print("packet_count =", len(packets))
    print("topics =", json.dumps(topics, ensure_ascii=False))
    print("future_executor = learning-v2-research-web-candidate-discovery.py")
    print("future_output_store = learning-v2/research/web-source-candidates.jsonl")
    print("web_browsed_now = false")
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
