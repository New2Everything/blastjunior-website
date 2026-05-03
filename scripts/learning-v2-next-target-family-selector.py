#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
RESEARCH = BASE / "research"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SELECTOR_ID = "learning-v2-next-target-family-selector-v0"
CANDIDATE_FILE = RESEARCH / "target-family-candidates.jsonl"

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
                "_raw": line[:300],
            })
    return rows

def completed_target_families_from_snapshots():
    completed = set()
    sources = []

    patterns = [
        "learning-v2-*-controlled-change-closed-*.md",
        "learning-v2-two-controlled-loops-capability-summary-*.md",
        "*controlled-ledger-acceptance-apply-*.md",
    ]

    for pat in patterns:
        for p in SNAPSHOT_DIR.glob(pat):
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for m in re.finditer(r"target_family:\s*`?([A-Za-z0-9_.-]+)`?", text):
                tf = m.group(1).strip()
                if tf:
                    completed.add(tf)
                    sources.append({
                        "target_family": tf,
                        "source": str(p),
                    })

    return sorted(completed), sources

def score_candidate(c):
    # Simple deterministic score for v0.
    # Prefer low risk, activation-ready, more pattern support.
    score = 0
    if c.get("risk") == "low":
        score += 100
    if c.get("activation_allowed_now") is True:
        score += 50
    if c.get("observe_only_first") is True:
        score += 30
    score += int(c.get("pattern_count") or 0) * 10
    return score

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    disabled = set(state.get("disabled_target_families") or [])
    completed, completed_sources = completed_target_families_from_snapshots()
    completed_set = set(completed)

    candidates = read_jsonl(CANDIDATE_FILE)

    failures = []
    warnings = []

    if not CANDIDATE_FILE.exists():
        failures.append(f"candidate_file_missing:{CANDIDATE_FILE}")

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

    screened = []

    for c in candidates:
        if "_parse_error" in c:
            screened.append({
                "candidate_id": None,
                "target_family": None,
                "selector_status": "invalid_jsonl_row",
                "blockers": [c["_parse_error"]],
                "jsonl_line": c.get("_jsonl_line"),
            })
            continue

        tf = c.get("target_family")
        probe = c.get("recommended_probe_script")
        probe_path = WORKSPACE / "scripts" / probe if probe else None
        probe_exists = bool(probe_path and probe_path.exists())

        blockers = []

        if not tf:
            blockers.append("missing_target_family")

        if tf in disabled:
            blockers.append("target_family_disabled")

        if tf in completed_set:
            blockers.append("target_family_already_completed")

        if c.get("risk") != "low":
            blockers.append(f"risk_not_low:{c.get('risk')}")

        if c.get("observe_only_first") is not True:
            blockers.append(f"observe_only_first_not_true:{c.get('observe_only_first')}")

        if c.get("activation_allowed_now") is not True:
            blockers.append(f"activation_allowed_now_not_true:{c.get('activation_allowed_now')}")

        if not probe:
            blockers.append("recommended_probe_script_missing_field")
        elif not probe_exists:
            blockers.append(f"recommended_probe_script_missing:{probe}")

        selector_ready = not blockers

        screened.append({
            "candidate_id": c.get("candidate_id"),
            "target_family": tf,
            "topic": c.get("topic"),
            "pattern_count": c.get("pattern_count"),
            "risk": c.get("risk"),
            "observe_only_first": c.get("observe_only_first"),
            "activation_allowed_now": c.get("activation_allowed_now"),
            "activation_status": c.get("activation_status"),
            "recommended_stage": c.get("recommended_stage"),
            "recommended_probe_script": probe,
            "recommended_probe_script_exists": probe_exists,
            "disabled": tf in disabled if tf else False,
            "completed": tf in completed_set if tf else False,
            "selector_score": score_candidate(c),
            "selector_ready": selector_ready,
            "selector_status": "ready_for_observe_only_probe" if selector_ready else "blocked",
            "blockers": blockers,
            "next_step": c.get("next_step"),
            "jsonl_line": c.get("_jsonl_line"),
        })

    ready = sorted(
        [x for x in screened if x.get("selector_ready")],
        key=lambda x: (-x.get("selector_score", 0), x.get("target_family") or ""),
    )

    blocked_new = sorted(
        [
            x for x in screened
            if not x.get("selector_ready")
            and not x.get("completed")
            and not x.get("disabled")
            and x.get("target_family")
        ],
        key=lambda x: (-x.get("selector_score", 0), x.get("target_family") or ""),
    )

    selected = ready[0] if ready else None
    top_blocked = blocked_new[0] if blocked_new else None

    if selected:
        selection_status = "selected_ready_candidate"
        recommended_next_step = "run_selected_observe_only_probe"
    elif top_blocked and any(str(b).startswith("recommended_probe_script_missing") for b in top_blocked.get("blockers", [])):
        selection_status = "no_ready_candidate"
        recommended_next_step = "design_missing_observe_only_probe_for_top_blocked_candidate"
    else:
        selection_status = "no_ready_candidate"
        recommended_next_step = "collect_or_build_more_target_family_candidates"

    result = "ok" if not failures else "blocked"

    out_json = REPORT_DIR / f"next-target-family-selector-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"next-target-family-selector-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "selector_id": SELECTOR_ID,
        "result": result,
        "selection_status": selection_status,
        "candidate_file": str(CANDIDATE_FILE),
        "candidate_count": len(candidates),
        "ready_candidate_count": len(ready),
        "completed_target_families": completed,
        "completed_target_family_sources": completed_sources,
        "disabled_target_families": sorted(disabled),
        "selected_candidate": selected,
        "top_blocked_candidate": top_blocked,
        "screened_candidates": screened,
        "recommended_next_step": recommended_next_step,
        "policy": {
            "read_only_selector": True,
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
    lines.append("# Learning V2 Next Target Family Selector")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- selector_id: `{SELECTOR_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- selection_status: `{selection_status}`")
    lines.append(f"- candidate_count: `{len(candidates)}`")
    lines.append(f"- ready_candidate_count: `{len(ready)}`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- human_review_required: `false`")
    lines.append("- machine_policy_gate: `true`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Selected Candidate")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(selected, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Top Blocked Candidate")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(top_blocked, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Screened Candidates")
    lines.append("")
    for item in screened:
        lines.append(f"- `{item.get('target_family')}` status=`{item.get('selector_status')}` blockers=`{item.get('blockers')}`")
    if failures:
        lines.append("")
        lines.append("## Failures")
        for f in failures:
            lines.append(f"- {f}")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("next_target_family_selector =", result)
    print("selection_status =", selection_status)
    print("candidate_count =", len(candidates))
    print("ready_candidate_count =", len(ready))
    print("selected_target_family =", selected.get("target_family") if selected else None)
    print("top_blocked_target_family =", top_blocked.get("target_family") if top_blocked else None)
    print("top_blocked_blockers =", json.dumps(top_blocked.get("blockers") if top_blocked else [], ensure_ascii=False))
    print("recommended_next_step =", recommended_next_step)
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
