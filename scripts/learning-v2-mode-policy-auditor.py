#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
MODE_POLICY = BASE / "mode-policy.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

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

def falseish(v):
    return v in (False, None, "", "None", 0)

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

    mode = current_mode(state)
    modes = policy.get("modes") or {}
    mode_rule = modes.get(mode) or {}

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

    governance = policy.get("mainline_governance") or {}
    mission_statement = governance.get("mission_statement") or ""

    add_check(
        "mainline_governance_exists",
        isinstance(governance, dict) and bool(governance),
        {"mainline_governance_present": bool(governance)}
    )

    add_check(
        "mission_statement_mentions_bug_and_learning_opportunity",
        ("bug" in mission_statement.lower()) and ("learning opportun" in mission_statement.lower()),
        {"mission_statement": mission_statement}
    )

    add_check(
        "bug_and_learning_opportunity_are_co_equal",
        governance.get("bug_discovery_and_learning_opportunity_discovery_are_co_equal") is True,
        {"value": governance.get("bug_discovery_and_learning_opportunity_discovery_are_co_equal")}
    )

    add_check(
        "not_bug_only_system",
        governance.get("must_not_degrade_to_bug_only_system") is True,
        {"value": governance.get("must_not_degrade_to_bug_only_system")}
    )

    add_check(
        "human_code_review_not_primary_safety_boundary",
        governance.get("human_code_review_is_not_primary_safety_boundary") is True,
        {"value": governance.get("human_code_review_is_not_primary_safety_boundary")}
    )

    add_check(
        "safety_boundary_is_system_gates",
        governance.get("safety_boundary_is_system_gates_auditors_baselines_policy") is True,
        {"value": governance.get("safety_boundary_is_system_gates_auditors_baselines_policy")}
    )

    add_check(
        "reduce_complexity_before_feature_growth",
        governance.get("reduce_own_complexity_before_feature_growth") is True,
        {"value": governance.get("reduce_own_complexity_before_feature_growth")}
    )

    add_check(
        "no_new_script_before_capability_lookup",
        governance.get("no_new_script_before_capability_lookup") is True,
        {"value": governance.get("no_new_script_before_capability_lookup")}
    )

    add_check(
        "reuse_or_extend_existing_tool_first",
        governance.get("reuse_or_extend_existing_tool_before_creating_new_tool") is True,
        {"value": governance.get("reuse_or_extend_existing_tool_before_creating_new_tool")}
    )

    add_check(
        "script_lifecycle_metadata_required",
        governance.get("every_script_must_have_capability_family") is True
        and governance.get("every_script_must_have_lifecycle_state") is True
        and governance.get("every_script_must_have_exit_or_retirement_path") is True,
        {
            "every_script_must_have_capability_family": governance.get("every_script_must_have_capability_family"),
            "every_script_must_have_lifecycle_state": governance.get("every_script_must_have_lifecycle_state"),
            "every_script_must_have_exit_or_retirement_path": governance.get("every_script_must_have_exit_or_retirement_path"),
        }
    )

    add_check(
        "current_mode_resolved",
        mode is not None,
        {"current_mode": mode}
    )

    add_check(
        "current_mode_known",
        mode in modes,
        {"current_mode": mode, "known_modes": sorted(modes.keys())}
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

    sep = state.get("self_evolution_policy") or {}

    add_check(
        "self_evolution_source_changes_blocked",
        sep.get("allow_source_changes") is False,
        {"self_evolution_policy.allow_source_changes": sep.get("allow_source_changes")}
    )

    add_check(
        "self_evolution_git_commit_blocked",
        sep.get("allow_git_commit") is False,
        {"self_evolution_policy.allow_git_commit": sep.get("allow_git_commit")}
    )

    add_check(
        "self_evolution_deploy_blocked",
        sep.get("allow_deploy") is False,
        {"self_evolution_policy.allow_deploy": sep.get("allow_deploy")}
    )

    if mode in modes:
        add_check(
            "mode_rule_source_changes_blocked",
            mode_rule.get("source_changes_allowed") is False,
            {"source_changes_allowed": mode_rule.get("source_changes_allowed")}
        )

        add_check(
            "mode_rule_git_commit_blocked",
            mode_rule.get("git_commit_allowed") is False,
            {"git_commit_allowed": mode_rule.get("git_commit_allowed")}
        )

        add_check(
            "mode_rule_git_push_blocked",
            mode_rule.get("git_push_allowed") is False,
            {"git_push_allowed": mode_rule.get("git_push_allowed")}
        )

        add_check(
            "mode_rule_deploy_blocked",
            mode_rule.get("deploy_allowed") is False,
            {"deploy_allowed": mode_rule.get("deploy_allowed")}
        )

    required_state = mode_rule.get("required_state") or {}
    for key, expected in required_state.items():
        actual = state.get(key)
        ok = (actual is expected) if isinstance(expected, bool) else (actual == expected)
        add_check(
            f"required_state_{key}",
            ok,
            {"key": key, "actual": actual, "expected": expected}
        )

    if mode == "system_build_only":
        add_check(
            "system_build_learning_cycle_disabled_or_unset",
            falseish(state.get("learning_cycle_enabled")),
            {"learning_cycle_enabled": state.get("learning_cycle_enabled")}
        )

        add_check(
            "system_build_topic_selector_disabled_or_unset",
            falseish(state.get("topic_selector_allowed")),
            {"topic_selector_allowed": state.get("topic_selector_allowed")}
        )

        add_check(
            "system_build_policy_learning_cycle_disabled",
            mode_rule.get("learning_cycle_enabled") is False,
            {"learning_cycle_enabled": mode_rule.get("learning_cycle_enabled")}
        )

        add_check(
            "system_build_policy_topic_selector_disabled",
            mode_rule.get("topic_selector_allowed") is False,
            {"topic_selector_allowed": mode_rule.get("topic_selector_allowed")}
        )

    elif mode == "learning_observe_only":
        add_check(
            "observe_learning_cycle_enabled",
            state.get("learning_cycle_enabled") is True,
            {"learning_cycle_enabled": state.get("learning_cycle_enabled")}
        )

        add_check(
            "observe_topic_selector_allowed",
            state.get("topic_selector_allowed") is True,
            {"topic_selector_allowed": state.get("topic_selector_allowed")}
        )

        add_check(
            "observe_policy_learning_cycle_enabled",
            mode_rule.get("learning_cycle_enabled") is True,
            {"learning_cycle_enabled": mode_rule.get("learning_cycle_enabled")}
        )

        add_check(
            "observe_policy_topic_selector_allowed",
            mode_rule.get("topic_selector_allowed") is True,
            {"topic_selector_allowed": mode_rule.get("topic_selector_allowed")}
        )

        add_check(
            "observe_still_blocks_source_commit_deploy",
            mode_rule.get("source_changes_allowed") is False
            and mode_rule.get("git_commit_allowed") is False
            and mode_rule.get("git_push_allowed") is False
            and mode_rule.get("deploy_allowed") is False
            and state.get("allow_source_changes") is False
            and state.get("allow_git_commit") is False
            and state.get("allow_deploy") is False,
            {
                "state_allow_source_changes": state.get("allow_source_changes"),
                "state_allow_git_commit": state.get("allow_git_commit"),
                "state_allow_deploy": state.get("allow_deploy"),
                "rule_source_changes_allowed": mode_rule.get("source_changes_allowed"),
                "rule_git_commit_allowed": mode_rule.get("git_commit_allowed"),
                "rule_git_push_allowed": mode_rule.get("git_push_allowed"),
                "rule_deploy_allowed": mode_rule.get("deploy_allowed"),
            }
        )

    elif mode is not None:
        add_check(
            "unsupported_current_mode_for_auditor",
            False,
            {"current_mode": mode}
        )

    result = "ok" if not failures else "blocked"

    report = {
        "generated_at": now_iso(),
        "auditor": "learning-v2-mode-policy-auditor",
        "result": result,
        "current_mode": mode,
        "policy_version": policy.get("version"),
        "failures": failures,
        "checks": checks,
        "note": "Supports both system_build_only pre-switch checks and learning_observe_only stable-state checks."
    }

    out = REPORT_DIR / f"mode-policy-audit-{stamp()}.json"
    save_json(out, report)

    state["last_mode_policy_audit"] = {
        "generated_at": report["generated_at"],
        "path": str(out),
        "result": result,
        "current_mode": mode,
        "failures": failures,
        "policy_version": policy.get("version"),
    }
    save_json(STATE, state)

    print("mode_policy_audit =", result)
    print("mode_policy_report =", out)
    print("current_mode =", mode)
    print("failure_count =", len(failures))
    print("policy_version =", policy.get("version"))

    if failures:
        print()
        print("failures:")
        for x in failures:
            print(" ", x)

    if result != "ok":
        raise SystemExit(2)

if __name__ == "__main__":
    main()
