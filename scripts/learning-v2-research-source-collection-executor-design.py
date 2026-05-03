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

REQUESTS = RESEARCH_DIR / "real-source-collection-requests.jsonl"

DESIGN_ID = "learning-v2-research-source-collection-executor-design-v0"

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
    requests = load_jsonl(REQUESTS)

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

    if not requests:
        failures.append("missing_real_source_collection_requests")

    planned_topics = sorted({r.get("topic") for r in requests if r.get("topic")})
    planned_query_ids = sorted({r.get("query_id") for r in requests if r.get("query_id")})

    design = {
        "generated_at": now_iso(),
        "design_id": DESIGN_ID,
        "result": "ok" if not failures else "blocked",
        "failures": failures,
        "request_count": len(requests),
        "planned_topics": planned_topics,
        "planned_query_ids": planned_query_ids,
        "executor_name": "learning-v2-research-source-collection-executor.py",
        "execution_modes": {
            "manual_only_v0": {
                "description": "Read collection requests and generate manual collection templates. Does not browse.",
                "web_browsing": False,
                "writes_sources_jsonl": False,
                "writes_state": False,
                "safe_now": True,
            },
            "assisted_web_search_v1": {
                "description": "Later mode: use controlled web search to find candidate sources, but still require validation before writing sources.jsonl.",
                "web_browsing": True,
                "writes_sources_jsonl": False,
                "writes_state": False,
                "safe_now": False,
                "requires_extra_guard": True,
            },
            "validated_real_source_apply_v2": {
                "description": "Later mode: write validated real sources through existing real-source-intake schema only.",
                "web_browsing": False,
                "writes_sources_jsonl": True,
                "writes_state": False,
                "safe_now": False,
                "requires_schema_validation": True,
                "requires_duplicate_check": True,
            }
        },
        "required_guardrails": [
            "Do not modify website source.",
            "Do not write state.json.",
            "Do not commit.",
            "Do not push.",
            "Do not deploy.",
            "Do not ingest a source without query_id, topic, key_claims, and design_principles.",
            "Do not treat generated summaries as sources.",
            "Do not restart completed or disabled target-families.",
            "Route already completed target-family evidence to evidence reinforcement archive.",
            "Every collected source must pass real-source-intake before digesting."
        ],
        "recommended_build_sequence": [
            "Build manual collection packet generator.",
            "Dry-run against existing 5 collection requests.",
            "Baseline and integrity check.",
            "Generate one manual packet per request.",
            "Only later add web-search assisted candidate discovery.",
            "Only later add source validation and intake automation."
        ],
        "next_script": {
            "name": "learning-v2-research-manual-collection-packet-generator.py",
            "purpose": "Convert planned collection requests into copy-ready manual source collection packets.",
            "writes_sources_jsonl": False,
            "writes_state": False,
            "web_browsed_now": False,
            "safe_next_step": True
        },
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "design_only": True,
            "web_browsed_now": False
        }
    }

    out_json = REPORT_DIR / f"research-source-collection-executor-design-{stamp()}.json"
    out_md = REPORT_DIR / f"research-source-collection-executor-design-{stamp()}.md"

    out_json.write_text(json.dumps(design, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Research Source Collection Executor Design")
    lines.append("")
    lines.append(f"- generated_at: `{design['generated_at']}`")
    lines.append(f"- design_id: `{DESIGN_ID}`")
    lines.append(f"- result: `{design['result']}`")
    lines.append(f"- request_count: `{len(requests)}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- web_browsed_now: `false`")
    lines.append("")
    lines.append("## Planned topics")
    lines.append("")
    for topic in planned_topics:
        lines.append(f"- `{topic}`")
    lines.append("")
    lines.append("## Execution modes")
    lines.append("")
    for name, info in design["execution_modes"].items():
        lines.append(f"### `{name}`")
        lines.append("")
        lines.append(f"- description: {info.get('description')}")
        lines.append(f"- web_browsing: `{str(info.get('web_browsing')).lower()}`")
        lines.append(f"- writes_sources_jsonl: `{str(info.get('writes_sources_jsonl')).lower()}`")
        lines.append(f"- safe_now: `{str(info.get('safe_now')).lower()}`")
        lines.append("")
    lines.append("## Required guardrails")
    lines.append("")
    for item in design["required_guardrails"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Recommended build sequence")
    lines.append("")
    for item in design["recommended_build_sequence"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Next script")
    lines.append("")
    lines.append(f"- `{design['next_script']['name']}`")
    lines.append(f"- purpose: {design['next_script']['purpose']}")
    lines.append("")

    if failures:
        lines.append("## Failures")
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("research_source_collection_executor_design =", design["result"])
    print("design_id =", DESIGN_ID)
    print("design_json =", out_json)
    print("design_md =", out_md)
    print("request_count =", len(requests))
    print("planned_topics =", json.dumps(planned_topics, ensure_ascii=False))
    print("next_script = learning-v2-research-manual-collection-packet-generator.py")
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
