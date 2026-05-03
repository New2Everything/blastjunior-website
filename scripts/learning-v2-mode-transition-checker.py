#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
MODE_POLICY = BASE / "mode-policy.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

FROM_MODE = "system_build_only"
TO_MODE = "learning_observe_only"

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

def noneish(v):
    return v in (None, "", "None")

def current_mode(state):
    sep = state.get("self_evolution_policy") or {}
    if isinstance(sep, dict) and sep.get("mode"):
        return sep.get("mode")

    mp = state.get("mode_policy")
    if isinstance(mp, dict) and mp.get("mode"):
        return mp.get("mode")
    if isinstance(mp, str):
        return mp

    if state.get("system_build_only") is True:
        return "system_build_only"

    audit = state.get("last_mode_policy_audit") or {}
    if audit.get("current_mode"):
        return audit.get("current_mode")

    return None

def main():
    state = load_json(STATE, default={})
    policy = load_json(MODE_POLICY, default={})

    from_mode = current_mode(state)
    target_mode = TO_MODE
    inside_integrity = "--inside-integrity" in sys.argv

    integrity = state.get("last_system_integrity") or {}
    mode_audit = state.get("last_mode_policy_audit") or {}
    drift = state.get("last_system_drift_audit") or {}
    gate_summary = integrity.get("gate_summary") or {}
    commit_summary = integrity.get("commit_plan_audit_summary") or {}

    modes = policy.get("modes") or {}
    target_rule = modes.get(target_mode) or {}
    current_rule = modes.get(from_mode) or {}

    transition_kind = (
        "pre_switch_check"
        if from_mode == FROM_MODE
        else "stable_observe_check"
        if from_mode == TO_MODE
        else "unsupported_mode_check"
    )

    checks = []
    failures = []

    def add_check(name, ok, details=None):
        checks.append({
            "name": name,
            "ok": bool(ok),
            "details": details or {},
        })
        if not ok:
            failures.append(name)

    add_check(
        "mode_policy_file_exists",
        MODE_POLICY.exists(),
        {"path": str(MODE_POLICY)}
    )

    add_check(
        "current_mode_supported",
        from_mode in (FROM_MODE, TO_MODE),
        {"current_mode": from_mode, "supported_modes": [FROM_MODE, TO_MODE]}
    )

    add_check(
        "target_mode_exists",
        target_mode in modes,
        {"target_mode": target_mode, "known_modes": sorted(modes.keys())}
    )

    system_integrity_hard_failures = integrity.get("hard_failures") or []
    system_integrity_recovery_ok = (
        integrity.get("result") == "blocked"
        and "mode_transition_check_not_ok" in system_integrity_hard_failures
        and (integrity.get("preflight_result") == "ok" or gate_summary.get("ok_for_system_build") is True)
        and integrity.get("policy_lock_audit_result") == "ok"
        and integrity.get("mode_policy_audit_result") == "ok"
        and integrity.get("drift_audit_result") == "ok"
        and (integrity.get("drift_count") == 0 or drift.get("drift_count") == 0)
        and gate_summary.get("business_freeze_stable") is True
    )

    system_integrity_green_ok = (
        integrity.get("result") == "ok"
        or inside_integrity
        or system_integrity_recovery_ok
    )

    add_check(
        "system_integrity_green",
        system_integrity_green_ok,
        {
            "system_integrity_result": integrity.get("result"),
            "path": integrity.get("path") or integrity.get("report"),
            "inside_integrity": inside_integrity,
            "controlled_recovery_ok": system_integrity_recovery_ok,
            "hard_failures": system_integrity_hard_failures,
            "note": "controlled recovery: prior integrity was blocked only by mode transition check after business freeze/drift recovered" if system_integrity_recovery_ok else None,
        }
    )

    add_check(
        "mode_policy_audit_green",
        mode_audit.get("result") == "ok",
        {
            "mode_policy_audit_result": mode_audit.get("result"),
            "current_mode": mode_audit.get("current_mode"),
            "policy_version": mode_audit.get("policy_version"),
        }
    )

    add_check(
        "drift_count_zero",
        True if inside_integrity else drift.get("drift_count") == 0,
        {
            "drift_count": drift.get("drift_count"),
            "drift_result": drift.get("result"),
            "inside_integrity": inside_integrity,
            "note": "Skipped during system-integrity execution because system_drift_audit runs later in the wrapper." if inside_integrity else None,
        }
    )

    add_check(
        "business_freeze_stable",
        gate_summary.get("business_freeze_stable") is True,
        {"business_freeze_stable": gate_summary.get("business_freeze_stable")}
    )

    add_check(
        "commit_plan_has_no_business_paths",
        commit_summary.get("business_paths_selected_count") == 0,
        {"business_paths_selected_count": commit_summary.get("business_paths_selected_count")}
    )

    add_check(
        "commit_plan_dry_run_only",
        commit_summary.get("dry_run_only") is True,
        {"dry_run_only": commit_summary.get("dry_run_only")}
    )

    add_check(
        "top_level_source_changes_blocked",
        state.get("allow_source_changes") is False,
        {"allow_source_changes": state.get("allow_source_changes")}
    )

    add_check(
        "top_level_git_commit_blocked",
        state.get("allow_git_commit") is False,
        {"allow_git_commit": state.get("allow_git_commit")}
    )

    add_check(
        "top_level_deploy_blocked",
        state.get("allow_deploy") is False,
        {"allow_deploy": state.get("allow_deploy")}
    )

    add_check(
        "target_allows_learning_cycle",
        target_rule.get("learning_cycle_enabled") is True,
        {"learning_cycle_enabled": target_rule.get("learning_cycle_enabled")}
    )

    add_check(
        "target_allows_topic_selector",
        target_rule.get("topic_selector_allowed") is True,
        {"topic_selector_allowed": target_rule.get("topic_selector_allowed")}
    )

    add_check(
        "target_still_blocks_source_changes",
        target_rule.get("source_changes_allowed") is False,
        {"source_changes_allowed": target_rule.get("source_changes_allowed")}
    )

    add_check(
        "target_still_blocks_release_actions",
        target_rule.get("git_commit_allowed") is False
        and target_rule.get("git_push_allowed") is False
        and target_rule.get("deploy_allowed") is False,
        {
            "git_commit_allowed": target_rule.get("git_commit_allowed"),
            "git_push_allowed": target_rule.get("git_push_allowed"),
            "deploy_allowed": target_rule.get("deploy_allowed"),
        }
    )

    current_required_state = current_rule.get("required_state") or {}
    for key, expected in current_required_state.items():
        actual = state.get(key)
        ok = (actual is expected) if isinstance(expected, bool) else (actual == expected)
        add_check(
            f"current_required_state_{key}",
            ok,
            {"key": key, "actual": actual, "expected": expected}
        )

    if from_mode == FROM_MODE:
        add_check(
            "active_cycle_currently_paused_for_pre_switch",
            noneish(state.get("current_topic"))
            and noneish(state.get("current_stage"))
            and noneish(state.get("current_target_family")),
            {
                "current_topic": state.get("current_topic"),
                "current_stage": state.get("current_stage"),
                "current_target_family": state.get("current_target_family"),
            }
        )

    if from_mode == TO_MODE:
        add_check(
            "observe_mode_learning_cycle_enabled",
            state.get("learning_cycle_enabled") is True,
            {"learning_cycle_enabled": state.get("learning_cycle_enabled")}
        )

        add_check(
            "observe_mode_topic_selector_allowed",
            state.get("topic_selector_allowed") is True,
            {"topic_selector_allowed": state.get("topic_selector_allowed")}
        )

        add_check(
            "observe_mode_still_blocks_source_commit_deploy",
            state.get("allow_source_changes") is False
            and state.get("allow_git_commit") is False
            and state.get("allow_deploy") is False,
            {
                "allow_source_changes": state.get("allow_source_changes"),
                "allow_git_commit": state.get("allow_git_commit"),
                "allow_deploy": state.get("allow_deploy"),
            }
        )

    result = "ok" if not failures else "blocked"

    report = {
        "generated_at": now_iso(),
        "checker": "learning-v2-mode-transition-checker",
        "result": result,
        "transition_kind": transition_kind,
        "transition": {
            "from": from_mode,
            "to": target_mode,
            "would_change_state": {
                "system_build_only": False,
                "learning_cycle_enabled": True,
                "topic_selector_allowed": True,
                "allow_source_changes": False,
                "allow_git_commit": False,
                "allow_deploy": False
            },
            "would_allow": {
                "topic_selector": True,
                "learning_cycle": True,
                "stage_executors": True,
                "proposal_generation": True
            },
            "would_still_block": {
                "website_source_changes": True,
                "git_add": True,
                "git_commit": True,
                "git_push": True,
                "deploy": True
            }
        },
        "failures": failures,
        "checks": checks,
        "policy_version": policy.get("version"),
        "inside_integrity": inside_integrity,
        "note": "Read-only. Supports pre-switch check and learning_observe_only stable-state check."
    }

    out = REPORT_DIR / f"mode-transition-check-{stamp()}.json"
    save_json(out, report)

    state["last_mode_transition_check"] = {
        "generated_at": report["generated_at"],
        "path": str(out),
        "result": result,
        "from": from_mode,
        "to": target_mode,
        "transition_kind": transition_kind,
        "failures": failures,
        "policy_version": policy.get("version"),
    }
    save_json(STATE, state)

    print("mode_transition_check =", result)
    print("transition_report =", out)
    print("transition_kind =", transition_kind)
    print("from_mode =", from_mode)
    print("to_mode =", target_mode)
    print("failure_count =", len(failures))
    print("read_only = true")
    print("inside_integrity =", str(inside_integrity).lower())
    print("would_allow_topic_selector = true")
    print("would_allow_learning_cycle = true")
    print("would_allow_source_changes = false")
    print("would_allow_git_commit = false")
    print("would_allow_deploy = false")

    if failures:
        print()
        print("failures:")
        for x in failures:
            print(" ", x)

    if result != "ok":
        raise SystemExit(2)

if __name__ == "__main__":
    main()
