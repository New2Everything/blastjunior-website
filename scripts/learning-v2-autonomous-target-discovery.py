#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
RESEARCH = BASE / "research"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
CANDIDATES = RESEARCH / "target-family-candidates.jsonl"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

DISCOVERY_ID = "learning-v2-autonomous-target-discovery-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def read_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            obj["_jsonl_line"] = i
            rows.append(obj)
        except Exception as e:
            rows.append({
                "_jsonl_line": i,
                "_parse_error": str(e),
                "_raw": line[:240],
            })
    return rows

def score_candidate(c):
    score = 0
    if c.get("risk") == "low":
        score += 100
    if c.get("activation_allowed_now") is True:
        score += 50
    if c.get("observe_only_first") is True:
        score += 30
    score += int(c.get("pattern_count") or 0) * 10
    return score

def screen_candidate(c, disabled, completed):
    if "_parse_error" in c:
        return {
            "candidate_id": None,
            "target_family": None,
            "selector_ready": False,
            "score": 0,
            "blockers": [f"parse_error:{c.get('_parse_error')}"],
            "jsonl_line": c.get("_jsonl_line"),
        }

    tf = c.get("target_family")
    probe = c.get("recommended_probe_script")
    probe_path = WORKSPACE / "scripts" / probe if probe else None
    probe_exists = bool(probe_path and probe_path.exists())

    blockers = []

    if not tf:
        blockers.append("missing_target_family")
    if tf in disabled:
        blockers.append("target_family_disabled")
    if tf in completed:
        blockers.append("target_family_completed")
    if c.get("risk") != "low":
        blockers.append(f"risk_not_low:{c.get('risk')}")
    if c.get("activation_allowed_now") is not True:
        blockers.append(f"activation_allowed_now_not_true:{c.get('activation_allowed_now')}")
    if c.get("observe_only_first") is not True:
        blockers.append(f"observe_only_first_not_true:{c.get('observe_only_first')}")
    if not probe:
        blockers.append("recommended_probe_script_missing_field")
    elif not probe_exists:
        blockers.append(f"recommended_probe_script_missing:{probe}")

    return {
        "candidate_id": c.get("candidate_id"),
        "target_family": tf,
        "topic": c.get("topic"),
        "risk": c.get("risk"),
        "pattern_count": c.get("pattern_count"),
        "activation_allowed_now": c.get("activation_allowed_now"),
        "activation_status": c.get("activation_status"),
        "observe_only_first": c.get("observe_only_first"),
        "recommended_stage": c.get("recommended_stage"),
        "recommended_probe_script": probe,
        "recommended_probe_script_exists": probe_exists,
        "principles": c.get("principles") or [],
        "source_titles": c.get("source_titles") or [],
        "score": score_candidate(c),
        "selector_ready": not blockers,
        "blockers": blockers,
        "jsonl_line": c.get("_jsonl_line"),
    }

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    failures = []
    warnings = []

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

    disabled = set(state.get("disabled_target_families") or [])
    completed = set()
    for item in state.get("completed_tracks") or []:
        if isinstance(item, dict) and item.get("track_id"):
            completed.add(item["track_id"])
    for k, v in (state.get("track_status") or {}).items():
        if isinstance(v, dict) and v.get("status") == "complete":
            completed.add(k)

    candidates = read_jsonl(CANDIDATES)
    screened = [screen_candidate(c, disabled, completed) for c in candidates]

    ready = sorted(
        [x for x in screened if x["selector_ready"]],
        key=lambda x: (-x["score"], x.get("target_family") or ""),
    )
    blocked = sorted(
        [x for x in screened if not x["selector_ready"]],
        key=lambda x: (-x["score"], x.get("target_family") or ""),
    )

    selected = ready[0] if ready else None

    def has_blocker(item, name):
        return name in (item.get("blockers") or [])

    def has_blocker_prefix(item, prefix):
        return any(str(b).startswith(prefix) for b in (item.get("blockers") or []))

    def is_terminal_blocked(item):
        return (
            has_blocker(item, "target_family_disabled")
            or has_blocker(item, "target_family_completed")
        )

    # Important: completed/disabled candidates are evidence, not next work.
    # Prefer a non-terminal candidate that is only blocked by missing probe scaffolding.
    actionable_blocked = [
        x for x in blocked
        if not is_terminal_blocked(x)
    ]

    missing_probe_blocked = [
        x for x in actionable_blocked
        if has_blocker_prefix(x, "recommended_probe_script_missing")
    ]

    if missing_probe_blocked:
        top_blocked = missing_probe_blocked[0]
    elif actionable_blocked:
        top_blocked = actionable_blocked[0]
    else:
        top_blocked = blocked[0] if blocked else None

    if selected:
        discovery_status = "ready_candidate_found"
        recommended_next_step = "wire_selected_candidate_to_selector_and_dispatch_after_probe_verification"
    elif top_blocked and has_blocker_prefix(top_blocked, "recommended_probe_script_missing") and not is_terminal_blocked(top_blocked):
        discovery_status = "missing_probe_for_best_candidate"
        recommended_next_step = "create_observe_only_probe_scaffold_for_best_candidate"
    elif candidates:
        discovery_status = "candidates_exist_but_not_actionable"
        recommended_next_step = "repair_candidate_metadata_or_collect_more_sources"
    else:
        discovery_status = "no_candidates"
        recommended_next_step = "run_research_query_to_candidate_pipeline"

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "discovery_id": DISCOVERY_ID,
        "result": result,
        "discovery_status": discovery_status,
        "candidate_file": str(CANDIDATES),
        "candidate_count": len(candidates),
        "ready_candidate_count": len(ready),
        "blocked_candidate_count": len(blocked),
        "selected_candidate": selected,
        "top_blocked_candidate": top_blocked,
        "screened_candidates": screened,
        "recommended_next_step": recommended_next_step,
        "policy": {
            "autonomous_discovery_only": True,
            "state_written": False,
            "business_source_written": False,
            "source_change_gate_opened": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
        "warnings": warnings,
        "failures": failures,
    }

    out_json = REPORT_DIR / f"autonomous-target-discovery-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"autonomous-target-discovery-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Autonomous Target Discovery",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- discovery_id: `{DISCOVERY_ID}`",
        f"- result: `{result}`",
        f"- discovery_status: `{discovery_status}`",
        f"- candidate_count: `{len(candidates)}`",
        f"- ready_candidate_count: `{len(ready)}`",
        f"- recommended_next_step: `{recommended_next_step}`",
        "- state_written: `false`",
        "- business_source_written: `false`",
        "- source_change_gate_opened: `false`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
        "",
        "## Selected Candidate",
        "",
        json.dumps(selected, ensure_ascii=False, indent=2) if selected else "none",
        "",
        "## Top Blocked Candidate",
        "",
        json.dumps(top_blocked, ensure_ascii=False, indent=2) if top_blocked else "none",
    ]

    if failures:
        lines += ["", "## Failures"]
        lines += [f"- {x}" for x in failures]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("autonomous_target_discovery =", result)
    print("discovery_status =", discovery_status)
    print("candidate_count =", len(candidates))
    print("ready_candidate_count =", len(ready))
    print("blocked_candidate_count =", len(blocked))
    print("selected_candidate =", json.dumps(selected, ensure_ascii=False))
    print("top_blocked_candidate =", json.dumps(top_blocked, ensure_ascii=False))
    print("recommended_next_step =", recommended_next_step)
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("state_written = false")
    print("business_source_written = false")
    print("source_change_gate_opened = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
