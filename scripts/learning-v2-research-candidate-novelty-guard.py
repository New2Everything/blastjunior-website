#!/usr/bin/env python3
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
RESEARCH_DIR = BASE / "research"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PATTERNS = RESEARCH_DIR / "design-patterns.jsonl"
CANDIDATES = RESEARCH_DIR / "target-family-candidates.jsonl"
EVIDENCE_ARCHIVE = RESEARCH_DIR / "evidence-reinforcements.jsonl"

GUARD_ID = "learning-v2-research-candidate-novelty-guard-v0"

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


def archived_evidence_families():
    rows = load_jsonl(EVIDENCE_ARCHIVE)
    return {r.get("target_family") for r in rows if r.get("target_family")}

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    patterns = load_jsonl(PATTERNS)
    existing_candidates = load_jsonl(CANDIDATES)

    disabled = set(state.get("disabled_target_families") or [])
    track_status = state.get("track_status") or {}
    archived_families = archived_evidence_families()

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

    if not patterns:
        failures.append("missing_real_design_patterns")

    grouped = defaultdict(list)
    for p in patterns:
        fam = p.get("suggested_target_family")
        if fam:
            grouped[fam].append(p)

    decisions = []

    existing_candidate_families = {
        c.get("target_family") for c in existing_candidates if c.get("target_family")
    }

    for fam, rows in sorted(grouped.items()):
        completed = (track_status.get(fam) or {}).get("status") == "complete"
        is_disabled = fam in disabled
        already_candidate = fam in existing_candidate_families

        already_archived_evidence = fam in archived_families

        if completed or is_disabled:
            if already_archived_evidence:
                decision = "already_archived_evidence_reinforcement"
                activation_allowed = False
                reason = "target_family_already_completed_or_disabled_and_evidence_already_archived"
            else:
                decision = "archive_as_evidence_reinforcement"
                activation_allowed = False
                reason = "target_family_already_completed_or_disabled"
        elif already_candidate:
            decision = "skip_duplicate_candidate"
            activation_allowed = False
            reason = "target_family_candidate_already_exists"
        else:
            decision = "eligible_new_candidate"
            activation_allowed = True
            reason = "target_family_is_not_completed_disabled_or_existing_candidate"

        decisions.append({
            "target_family": fam,
            "topic": rows[0].get("topic"),
            "pattern_count": len(rows),
            "pattern_ids": [r.get("pattern_id") for r in rows],
            "completed": completed,
            "disabled": is_disabled,
            "already_candidate": already_candidate,
            "already_archived_evidence": already_archived_evidence,
            "decision": decision,
            "activation_allowed": activation_allowed,
            "reason": reason,
            "principles": [r.get("principle") for r in rows],
        })

    novel_count = sum(1 for d in decisions if d["decision"] == "eligible_new_candidate")
    archived_count = sum(1 for d in decisions if d["decision"] == "archive_as_evidence_reinforcement")
    already_archived_count = sum(1 for d in decisions if d["decision"] == "already_archived_evidence_reinforcement")
    duplicate_count = sum(1 for d in decisions if d["decision"] == "skip_duplicate_candidate")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "guard_id": GUARD_ID,
        "result": result,
        "failures": failures,
        "input_pattern_count": len(patterns),
        "existing_candidate_count": len(existing_candidates),
        "decision_count": len(decisions),
        "novel_count": novel_count,
        "archived_evidence_reinforcement_count": archived_count,
        "already_archived_evidence_reinforcement_count": already_archived_count,
        "duplicate_candidate_count": duplicate_count,
        "decisions": decisions,
        "recommended_next_step": (
            "archive_evidence_reinforcement"
            if archived_count and not novel_count
            else "no_action_evidence_already_archived"
            if already_archived_count and not novel_count
            else "build_real_target_family_candidates"
            if novel_count
            else "no_action"
        ),
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "guard_only": True,
        },
    }

    out_json = REPORT_DIR / f"research-candidate-novelty-guard-{stamp()}.json"
    out_md = REPORT_DIR / f"research-candidate-novelty-guard-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Research Candidate Novelty Guard")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- guard_id: `{GUARD_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- input_pattern_count: `{len(patterns)}`")
    lines.append(f"- novel_count: `{novel_count}`")
    lines.append(f"- archived_evidence_reinforcement_count: `{archived_count}`")
    lines.append(f"- duplicate_candidate_count: `{duplicate_count}`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Decisions")
    lines.append("")
    for d in decisions:
        lines.append(f"### `{d['target_family']}`")
        lines.append("")
        lines.append(f"- topic: `{d['topic']}`")
        lines.append(f"- pattern_count: `{d['pattern_count']}`")
        lines.append(f"- completed: `{str(d['completed']).lower()}`")
        lines.append(f"- disabled: `{str(d['disabled']).lower()}`")
        lines.append(f"- already_candidate: `{str(d['already_candidate']).lower()}`")
        lines.append(f"- decision: `{d['decision']}`")
        lines.append(f"- activation_allowed: `{str(d['activation_allowed']).lower()}`")
        lines.append(f"- reason: `{d['reason']}`")
        lines.append("")
    if failures:
        lines.append("## Failures")
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("research_candidate_novelty_guard =", result)
    print("guard_id =", GUARD_ID)
    print("guard_json =", out_json)
    print("guard_md =", out_md)
    print("input_pattern_count =", len(patterns))
    print("existing_candidate_count =", len(existing_candidates))
    print("decision_count =", len(decisions))
    print("novel_count =", novel_count)
    print("archived_evidence_reinforcement_count =", archived_count)
    print("already_archived_evidence_reinforcement_count =", already_archived_count)
    print("duplicate_candidate_count =", duplicate_count)
    print("recommended_next_step =", payload["recommended_next_step"])

    for d in decisions:
        print()
        print("target_family =", d["target_family"])
        print("pattern_count =", d["pattern_count"])
        print("completed =", d["completed"])
        print("disabled =", d["disabled"])
        print("already_archived_evidence =", d.get("already_archived_evidence"))
        print("decision =", d["decision"])
        print("activation_allowed =", d["activation_allowed"])
        print("reason =", d["reason"])

    print()
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
