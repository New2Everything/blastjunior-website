#!/usr/bin/env python3
"""
Learning V2 Topic Selector

Default behavior is dry-run.
Use --apply to write current_topic/current_stage/current_target_family into state.json.

Selector is target-family aware:
- It must not reopen a completed/disabled target family.
- It only auto-seeds topics with a currently supported executor path.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
MODE_POLICY = BASE / "mode-policy.json"
INBOX = BASE / "inbox/directives-inbox.jsonl"
PATTERNS = BASE / "patterns.jsonl"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

ALL_TOPICS = [
    "homepage-information-hierarchy",
    "mobile-first",
    "accessibility-basics",
    "performance-basics",
    "color-psychology",
    "typography",
    "interaction-design",
    "content-hierarchy",
    "simplicity",
]

PRIORITY_TOPICS = [
    "simplicity",
    "content-hierarchy",
    "mobile-first",
    "accessibility-basics",
    "performance-basics",
    "interaction-design",
    "typography",
    "color-psychology",
    "homepage-information-hierarchy",
]

EXECUTOR_READY_TOPICS = {
    "simplicity",
    "accessibility-basics",
}

TOPIC_TARGET_FAMILIES = {
    "accessibility-basics": [
        {
            "target_family": "accessibility.navigation_button_semantics",
            "stage": "accessibility_nav_button_probe",
            "reason": "research-derived read-only target family for navigation button semantics observation",
        },
        {
            "target_family": "accessibility.navigation_semantics",
            "stage": "accessibility_nav_probe",
            "reason": "new read-only target family for navigation accessibility semantics observation",
        },
    ],
    "simplicity": [
        {
            "target_family": "simplicity.dead_or_duplicate_entry_scan",
            "stage": "dead_duplicate_probe",
            "reason": "new read-only target family for duplicate/weak/dead entry observation",
        },
        {
            "target_family": "simplicity.section_more_anchor",
            "stage": "discover",
            "reason": "legacy completed section-more target family",
        },
    ],
}

DONE_STAGES = ("done", "closed", "archived")

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def load_inbox():
    if not INBOX.exists():
        return []
    return [json.loads(l) for l in INBOX.read_text(encoding="utf-8").splitlines() if l.strip()]

def load_patterns():
    if not PATTERNS.exists():
        return set()
    topics_done = set()
    for line in PATTERNS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            if e.get("pattern") and e.get("confidence") in ("high", "medium-high"):
                topics_done.add(e.get("topic"))
    return topics_done

def current_mode(state, policy):
    known_modes = set((policy.get("modes") or {}).keys())

    sep = state.get("self_evolution_policy") or {}
    if isinstance(sep, dict) and sep.get("mode") in known_modes:
        return sep.get("mode")

    mp = state.get("mode_policy")
    if isinstance(mp, dict) and mp.get("mode") in known_modes:
        return mp.get("mode")
    if isinstance(mp, str) and mp in known_modes:
        return mp

    audit = state.get("last_mode_policy_audit") or {}
    if audit.get("current_mode") in known_modes:
        return audit.get("current_mode")

    if state.get("system_build_only") is True:
        return "system_build_only"

    return None

def completed_or_disabled_families(state):
    disabled = set(state.get("disabled_target_families") or [])
    completed = set()

    for item in state.get("completed_tracks") or []:
        if isinstance(item, dict) and item.get("track_id"):
            completed.add(item.get("track_id"))

    track_status = state.get("track_status") or {}
    for track_id, info in track_status.items():
        if isinstance(info, dict) and info.get("status") == "complete":
            completed.add(track_id)

    return disabled | completed

def first_available_target_family(topic, state):
    if topic not in EXECUTOR_READY_TOPICS:
        return None, "topic_has_no_dispatch_executor_ready"

    done = completed_or_disabled_families(state)
    families = TOPIC_TARGET_FAMILIES.get(topic) or []

    if not families:
        return None, "topic_has_no_target_family_defined"

    blocked = {}
    for item in families:
        family = item["target_family"]
        if family in done:
            blocked[family] = "target_family_completed_or_disabled"
            continue
        return item, None

    return None, {
        "reason": "all_known_target_families_completed_or_disabled",
        "blocked_families": blocked,
    }

def topic_block_reason(topic, state):
    item, reason = first_available_target_family(topic, state)
    if item:
        return None
    return reason

def select_topic(state, inbox_entries, patterns_topics):
    current = state.get("current_topic")
    current_stage = state.get("current_stage")
    current_target_family = state.get("current_target_family")

    if current and current_stage and current_stage not in DONE_STAGES:
        return {
            "selector_decision": "keep_current_topic",
            "selected_topic": current,
            "selected_stage": current_stage,
            "selected_target_family": current_target_family,
            "seed_reason": "existing active topic is not done/closed/archived",
            "state_update_needed": False,
            "rejected_topics": [],
            "blocked_topics": {},
            "candidates": [],
            "patterns_topics": sorted(t for t in patterns_topics if t),
        }

    rejected = set()
    for e in inbox_entries:
        raw = e.get("raw_text", "")
        if "预约体验" in raw or "加入俱乐部" in raw:
            rejected.add("homepage-information-hierarchy")

    blocked_topics = {}
    candidates = []
    target_family_by_topic = {}

    for t in ALL_TOPICS:
        if t in rejected:
            continue

        item, reason = first_available_target_family(t, state)
        if not item:
            blocked_topics[t] = reason
            continue

        candidates.append(t)
        target_family_by_topic[t] = item

    raw_all = " | ".join(e.get("raw_text", "") for e in inbox_entries)

    preferred = None
    seed_reason = None

    if "less is more" in raw_all.lower() or "简洁" in raw_all:
        if "simplicity" in candidates:
            preferred = "simplicity"
            seed_reason = "constitution/directives emphasize simplicity and less is more"

    if preferred is None:
        for t in PRIORITY_TOPICS:
            if t in candidates:
                preferred = t
                seed_reason = "selected from controlled priority topic list"
                break

    if preferred is None:
        return {
            "selector_decision": "no_auto_seed",
            "selected_topic": None,
            "selected_stage": None,
            "selected_target_family": None,
            "seed_reason": "no eligible executor-ready target family remains; build a new target-family executor first",
            "state_update_needed": False,
            "rejected_topics": sorted(rejected),
            "blocked_topics": blocked_topics,
            "candidates": candidates,
            "patterns_topics": sorted(t for t in patterns_topics if t),
        }

    selected_family = target_family_by_topic[preferred]

    return {
        "selector_decision": "smart_auto_seed",
        "selected_topic": preferred,
        "selected_stage": selected_family["stage"],
        "selected_target_family": selected_family["target_family"],
        "seed_reason": seed_reason + "; " + selected_family["reason"],
        "state_update_needed": True,
        "rejected_topics": sorted(rejected),
        "blocked_topics": blocked_topics,
        "candidates": candidates,
        "patterns_topics": sorted(t for t in patterns_topics if t),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually write selected topic/stage/target_family to state.json")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = load_json(MODE_POLICY, default={})
    inbox_entries = load_inbox()
    patterns_topics = load_patterns()

    mode = current_mode(state, policy)
    mode_rule = (policy.get("modes") or {}).get(mode) or {}
    integrity = state.get("last_system_integrity") or {}

    failures = []

    if mode != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{mode}")

    if state.get("learning_cycle_enabled") is not True:
        failures.append(f"learning_cycle_enabled_not_true:{state.get('learning_cycle_enabled')}")

    if state.get("topic_selector_allowed") is not True:
        failures.append(f"topic_selector_allowed_not_true:{state.get('topic_selector_allowed')}")

    if mode_rule.get("topic_selector_allowed") is not True:
        failures.append(f"mode_rule_topic_selector_not_allowed:{mode_rule.get('topic_selector_allowed')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    decision = select_topic(state, inbox_entries, patterns_topics)

    result = "ok" if not failures else "blocked"

    report = {
        "generated_at": now_iso(),
        "selector": "learning-v2-topic-selector",
        "result": result,
        "apply": args.apply,
        "mode": mode,
        "mode_policy_version": policy.get("version"),
        "current_topic_before": state.get("current_topic"),
        "current_stage_before": state.get("current_stage"),
        "current_target_family_before": state.get("current_target_family"),
        **decision,
        "disabled_target_families": state.get("disabled_target_families") or [],
        "completed_tracks": state.get("completed_tracks") or [],
        "track_status": state.get("track_status") or {},
        "failures": failures,
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "source_changes_allowed": False,
            "target_family_guard": True,
        },
    }

    out = REPORT_DIR / f"topic-selector-{stamp()}.json"
    save_json(out, report)

    print("topic_selector =", result)
    print("selector_report =", out)
    print("apply =", str(args.apply).lower())
    print("mode =", mode)
    print("selector_decision =", decision["selector_decision"])
    print("current_topic_before =", state.get("current_topic"))
    print("current_stage_before =", state.get("current_stage"))
    print("current_target_family_before =", state.get("current_target_family"))
    print("would_select_topic =", decision["selected_topic"])
    print("would_set_stage =", decision["selected_stage"])
    print("would_set_target_family =", decision["selected_target_family"])
    print("seed_reason =", decision["seed_reason"])
    print("blocked_topics =", json.dumps(decision.get("blocked_topics") or {}, ensure_ascii=False))

    if failures:
        print("state_updated = false")
        print("state_written = false")
        print("business_source_written = false")
        print("git_commit = false")
        print("git_push = false")
        print("deploy = false")
        print()
        print("failures:")
        for x in failures:
            print(" ", x)
        raise SystemExit(2)

    if args.apply and decision["state_update_needed"]:
        state["current_topic"] = decision["selected_topic"]
        state["current_stage"] = decision["selected_stage"]
        state["current_target_family"] = decision["selected_target_family"]
        state["next_action"] = None
        state["carry_over_issue"] = None
        state["last_topic_selector"] = {
            "generated_at": report["generated_at"],
            "result": result,
            "report": str(out),
            "selector_decision": decision["selector_decision"],
            "selected_topic": decision["selected_topic"],
            "selected_stage": decision["selected_stage"],
            "selected_target_family": decision["selected_target_family"],
            "seed_reason": decision["seed_reason"],
            "blocked_topics": decision.get("blocked_topics") or {},
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        }
        save_json(STATE, state)
        print("state_updated = true")
        print("state_written = true")
    else:
        print("state_updated = false")
        print("state_written = false")

    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
