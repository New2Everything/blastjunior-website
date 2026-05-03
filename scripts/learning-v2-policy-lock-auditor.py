#!/usr/bin/env python3
import json
import subprocess
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

def noneish(v):
    return v in (None, "", "None")

def run(cmd):
    p = subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "cmd": cmd,
        "returncode": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
        "ok": p.returncode == 0,
    }

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

def main():
    state = load_json(STATE, default={})
    policy = load_json(MODE_POLICY, default={})
    mode = current_mode(state, policy)
    modes = policy.get("modes") or {}
    mode_rule = modes.get(mode) or {}
    required_state = mode_rule.get("required_state") or {}

    release_gate = run(["python3", "scripts/learning-v2-release-gate.py"])
    state_after_gate = load_json(STATE, default={})
    last_release_gate = state_after_gate.get("last_release_gate") or {}
    release_gate_summary = last_release_gate.get("summary") or {}
    latest_release_gate_report = last_release_gate.get("report") or last_release_gate.get("path")

    release_gate_report_data = load_json(latest_release_gate_report, default={}) if latest_release_gate_report else {}
    release_gate_checks = release_gate_report_data.get("checks") or []

    def release_gate_check(name):
        for item in release_gate_checks:
            if item.get("name") == name:
                return item
        return {}

    rg_source = release_gate_check("source_changes_disabled")
    rg_commit = release_gate_check("git_commit_disabled")
    rg_deploy = release_gate_check("deploy_disabled")

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
        "current_mode_known",
        mode in modes,
        {"current_mode": mode, "known_modes": sorted(modes.keys())}
    )

    for key, expected in required_state.items():
        actual = state.get(key)
        ok = (actual is expected) if isinstance(expected, bool) else (actual == expected)
        add_check(
            f"required_state_{key}",
            ok,
            {"key": key, "actual": actual, "expected": expected}
        )

    if mode_rule.get("active_cycle_must_be_paused") is True:
        add_check(
            "active_cycle_paused_when_required",
            noneish(state.get("current_topic"))
            and noneish(state.get("current_stage"))
            and noneish(state.get("current_target_family")),
            {
                "current_topic": state.get("current_topic"),
                "current_stage": state.get("current_stage"),
                "current_target_family": state.get("current_target_family"),
            }
        )
    else:
        add_check(
            "active_cycle_pause_not_required_by_mode",
            True,
            {
                "current_topic": state.get("current_topic"),
                "current_stage": state.get("current_stage"),
                "current_target_family": state.get("current_target_family"),
                "active_cycle_must_be_paused": mode_rule.get("active_cycle_must_be_paused"),
            }
        )

    add_check(
        "source_changes_disabled_direct_state",
        state.get("allow_source_changes") is False,
        {"allow_source_changes": state.get("allow_source_changes")}
    )

    add_check(
        "git_commit_disabled_direct_state",
        state.get("allow_git_commit") is False,
        {"allow_git_commit": state.get("allow_git_commit")}
    )

    add_check(
        "deploy_disabled_direct_state",
        state.get("allow_deploy") is False,
        {"allow_deploy": state.get("allow_deploy")}
    )

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

    add_check(
        "release_gate_command_ok",
        release_gate["ok"],
        {
            "returncode": release_gate["returncode"],
            "stderr": release_gate["stderr"][-500:] if release_gate["stderr"] else "",
        }
    )

    add_check(
        "release_gate_saw_source_changes_disabled",
        rg_source.get("ok") is True and (rg_source.get("details") or {}).get("allow_source_changes") is False,
        {
            "check_ok": rg_source.get("ok"),
            "allow_source_changes": (rg_source.get("details") or {}).get("allow_source_changes"),
            "release_gate_report": latest_release_gate_report,
        }
    )

    add_check(
        "release_gate_saw_git_commit_disabled",
        rg_commit.get("ok") is True and (rg_commit.get("details") or {}).get("allow_git_commit") is False,
        {
            "check_ok": rg_commit.get("ok"),
            "allow_git_commit": (rg_commit.get("details") or {}).get("allow_git_commit"),
            "release_gate_report": latest_release_gate_report,
        }
    )

    add_check(
        "release_gate_saw_deploy_disabled",
        rg_deploy.get("ok") is True and (rg_deploy.get("details") or {}).get("allow_deploy") is False,
        {
            "check_ok": rg_deploy.get("ok"),
            "allow_deploy": (rg_deploy.get("details") or {}).get("allow_deploy"),
            "release_gate_report": latest_release_gate_report,
        }
    )

    add_check(
        "release_gate_system_build_allowed",
        release_gate_summary.get("ok_for_system_build") is True,
        {"ok_for_system_build": release_gate_summary.get("ok_for_system_build")}
    )

    add_check(
        "release_gate_commit_still_disabled",
        release_gate_summary.get("ok_for_commit") is False,
        {"ok_for_commit": release_gate_summary.get("ok_for_commit")}
    )

    add_check(
        "release_gate_deploy_still_disabled",
        release_gate_summary.get("ok_for_deploy") is False,
        {"ok_for_deploy": release_gate_summary.get("ok_for_deploy")}
    )

    result = "ok" if not failures else "blocked"

    report = {
        "generated_at": now_iso(),
        "auditor": "learning-v2-policy-lock-auditor",
        "result": result,
        "current_mode": mode,
        "policy_version": policy.get("version"),
        "failures": failures,
        "checks": checks,
        "latest_release_gate_report": latest_release_gate_report,
        "policy": {
            "no_website_source_changes": True,
            "no_git_add": True,
            "no_git_commit": True,
            "no_git_push": True,
            "no_deploy": True,
            "mode_aware_required_state": True,
        },
    }

    out = REPORT_DIR / f"policy-lock-audit-{stamp()}.json"
    save_json(out, report)

    state_final = load_json(STATE, default={})
    state_final["last_policy_lock_audit"] = {
        "generated_at": report["generated_at"],
        "path": str(out),
        "result": result,
        "current_mode": mode,
        "failures": failures,
        "policy_version": policy.get("version"),
    }
    save_json(STATE, state_final)

    print("policy_lock_audit =", result)
    print("policy_lock_report =", out)
    print("current_mode =", mode)
    print("failure_count =", len(failures))
    print("release_gate_report =", latest_release_gate_report)
    print("source_changes_allowed = false")
    print("git_commit_allowed = false")
    print("git_push_allowed = false")
    print("deploy_allowed = false")

    if failures:
        print()
        print("failures:")
        for x in failures:
            print(" ", x)

    if result != "ok":
        raise SystemExit(2)

if __name__ == "__main__":
    main()
