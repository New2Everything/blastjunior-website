#!/usr/bin/env python3
import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
MODE_POLICY = BASE / "mode-policy.json"
EXPERIMENTS = BASE / "experiments.jsonl"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

DANGEROUS_WRITE_CHAIN_STAGES = {
    "apply_ready",
    "apply_planned",
    "applied",
}

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

def append_experiment(obj):
    with EXPERIMENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def run_child(script, *extra_args):
    cmd = ["/usr/bin/env", "python3", str(WORKSPACE / script), *extra_args]
    return subprocess.run(cmd, check=True)

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

def latest_simplicity_demotables():
    if not EXPERIMENTS.exists():
        return []
    demotables = []
    for line in EXPERIMENTS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("topic") != "simplicity":
            continue
        if e.get("stage") == "audit" and e.get("demotable_texts"):
            demotables = e.get("demotable_texts", [])
        if e.get("stage") == "audit_auto" and e.get("metrics", {}).get("demotable_texts"):
            demotables = e["metrics"]["demotable_texts"]
    return demotables

def choose_lightest_target(items):
    if not items:
        return None, "no demotable items found"
    priority = ["更多 >", "blastjunior.com", "📸 画廊", "📊 积分榜", "👥 成员", "发送"]
    for p in priority:
        if p in items:
            if p == "更多 >":
                return p, "次级入口，且不直接承担品牌识别或互动主功能，适合作为第一个最小简洁化调整对象。"
            if p == "blastjunior.com":
                return p, "页脚/弱导航性质更强，适合优先降权。"
            if p in ("📸 画廊", "📊 积分榜", "👥 成员"):
                return p, "信息型入口，可作为次一级简洁化候选。"
            if p == "发送":
                return p, "存在互动价值，通常不应第一刀处理，仅在没有更轻对象时考虑。"
    return items[0], "按候选列表顺序选择第一个可降权对象。"

def predict_branch(topic, stage, allow_source_changes, target_family=None):
    if topic is None or stage is None:
        return {
            "executor": "topic_selector",
            "child_script": "scripts/learning-v2-topic-selector.py",
            "source_write_risk": False,
            "would_write_state": True,
            "would_write_reports": True,
            "would_write_experiments": False,
            "blocked_reason": None,
        }

    if stage in DANGEROUS_WRITE_CHAIN_STAGES and allow_source_changes is False:
        return {
            "executor": f"blocked_write_chain_stage:{stage}",
            "child_script": None,
            "source_write_risk": True,
            "would_write_state": False,
            "would_write_reports": False,
            "would_write_experiments": False,
            "blocked_reason": f"stage_{stage}_requires_source_change_chain_but_source_changes_are_blocked",
        }

    if topic == "accessibility-basics" and stage == "accessibility_nav_proposal_ready":
        if target_family != "accessibility.navigation_semantics":
            return {
                "executor": "blocked_accessibility_nav_proposal_target_family_mismatch",
                "child_script": None,
                "source_write_risk": False,
                "would_write_state": False,
                "would_write_reports": False,
                "would_write_experiments": False,
                "blocked_reason": f"accessibility_nav_proposal_ready_requires_target_family_accessibility.navigation_semantics_got:{target_family}",
            }

        return {
            "executor": "accessibility_nav_proposal_finalizer",
            "child_script": "scripts/learning-v2-accessibility-nav-proposal-finalizer.py",
            "source_write_risk": False,
            "would_write_state": True,
            "would_write_reports": True,
            "would_write_experiments": False,
            "blocked_reason": None,
        }

    if topic == "accessibility-basics" and stage == "accessibility_nav_review_ready":
        if target_family != "accessibility.navigation_semantics":
            return {
                "executor": "blocked_accessibility_nav_review_target_family_mismatch",
                "child_script": None,
                "source_write_risk": False,
                "would_write_state": False,
                "would_write_reports": False,
                "would_write_experiments": False,
                "blocked_reason": f"accessibility_nav_review_ready_requires_target_family_accessibility.navigation_semantics_got:{target_family}",
            }

        return {
            "executor": "accessibility_nav_review_executor",
            "child_script": "scripts/learning-v2-accessibility-nav-review-executor.py",
            "source_write_risk": False,
            "would_write_state": True,
            "would_write_reports": True,
            "would_write_experiments": False,
            "blocked_reason": None,
        }

    if topic == "accessibility-basics" and stage == "accessibility_nav_button_proposal_ready":
        if target_family != "accessibility.navigation_button_semantics":
            return {
                "executor": "blocked_accessibility_nav_button_proposal_target_family_mismatch",
                "child_script": None,
                "source_write_risk": False,
                "would_write_state": False,
                "would_write_reports": False,
                "would_write_experiments": False,
                "blocked_reason": f"accessibility_nav_button_proposal_ready_requires_target_family_accessibility.navigation_button_semantics_got:{target_family}",
            }

        return {
            "executor": "accessibility_nav_button_proposal_finalizer",
            "child_script": "scripts/learning-v2-accessibility-nav-button-proposal-finalizer.py",
            "source_write_risk": False,
            "would_write_state": True,
            "would_write_reports": True,
            "would_write_experiments": False,
            "blocked_reason": None,
        }

    if topic == "accessibility-basics" and stage == "accessibility_nav_button_review_ready":
        if target_family != "accessibility.navigation_button_semantics":
            return {
                "executor": "blocked_accessibility_nav_button_review_target_family_mismatch",
                "child_script": None,
                "source_write_risk": False,
                "would_write_state": False,
                "would_write_reports": False,
                "would_write_experiments": False,
                "blocked_reason": f"accessibility_nav_button_review_ready_requires_target_family_accessibility.navigation_button_semantics_got:{target_family}",
            }

        return {
            "executor": "accessibility_nav_button_review_executor",
            "child_script": "scripts/learning-v2-accessibility-nav-button-review-executor.py",
            "source_write_risk": False,
            "would_write_state": True,
            "would_write_reports": True,
            "would_write_experiments": False,
            "blocked_reason": None,
        }

    if topic == "accessibility-basics" and stage == "accessibility_nav_button_probe":
        if target_family != "accessibility.navigation_button_semantics":
            return {
                "executor": "blocked_accessibility_nav_button_probe_target_family_mismatch",
                "child_script": None,
                "source_write_risk": False,
                "would_write_state": False,
                "would_write_reports": False,
                "would_write_experiments": False,
                "blocked_reason": f"accessibility_nav_button_probe_requires_target_family_accessibility.navigation_button_semantics_got:{target_family}",
            }

        return {
            "executor": "accessibility_nav_button_semantics_probe",
            "child_script": "scripts/learning-v2-accessibility-nav-button-semantics-probe.py",
            "source_write_risk": False,
            "would_write_state": False,
            "would_write_reports": True,
            "would_write_experiments": False,
            "blocked_reason": None,
        }

    if topic == "accessibility-basics" and stage == "accessibility_nav_probe":
        if target_family != "accessibility.navigation_semantics":
            return {
                "executor": "blocked_accessibility_nav_probe_target_family_mismatch",
                "child_script": None,
                "source_write_risk": False,
                "would_write_state": False,
                "would_write_reports": False,
                "would_write_experiments": False,
                "blocked_reason": f"accessibility_nav_probe_requires_target_family_accessibility.navigation_semantics_got:{target_family}",
            }

        return {
            "executor": "accessibility_nav_semantics_probe",
            "child_script": "scripts/learning-v2-accessibility-nav-semantics-probe.py",
            "source_write_risk": False,
            "would_write_state": False,
            "would_write_reports": True,
            "would_write_experiments": False,
            "blocked_reason": None,
        }

    if topic == "simplicity" and stage == "dead_duplicate_proposal_ready":
        if target_family != "simplicity.dead_or_duplicate_entry_scan":
            return {
                "executor": "blocked_dead_duplicate_proposal_target_family_mismatch",
                "child_script": None,
                "source_write_risk": False,
                "would_write_state": False,
                "would_write_reports": False,
                "would_write_experiments": False,
                "blocked_reason": f"dead_duplicate_proposal_ready_requires_target_family_simplicity.dead_or_duplicate_entry_scan_got:{target_family}",
            }

        return {
            "executor": "dead_duplicate_proposal_finalizer",
            "child_script": "scripts/learning-v2-dead-duplicate-proposal-finalizer.py",
            "source_write_risk": False,
            "would_write_state": True,
            "would_write_reports": True,
            "would_write_experiments": False,
            "blocked_reason": None,
        }

    if topic == "simplicity" and stage == "dead_duplicate_review_ready":
        if target_family != "simplicity.dead_or_duplicate_entry_scan":
            return {
                "executor": "blocked_dead_duplicate_review_target_family_mismatch",
                "child_script": None,
                "source_write_risk": False,
                "would_write_state": False,
                "would_write_reports": False,
                "would_write_experiments": False,
                "blocked_reason": f"dead_duplicate_review_ready_requires_target_family_simplicity.dead_or_duplicate_entry_scan_got:{target_family}",
            }

        return {
            "executor": "dead_duplicate_review_executor",
            "child_script": "scripts/learning-v2-dead-duplicate-review-executor.py",
            "source_write_risk": False,
            "would_write_state": True,
            "would_write_reports": True,
            "would_write_experiments": False,
            "blocked_reason": None,
        }

    if topic == "simplicity" and stage == "dead_duplicate_probe":
        if target_family != "simplicity.dead_or_duplicate_entry_scan":
            return {
                "executor": "blocked_dead_duplicate_probe_target_family_mismatch",
                "child_script": None,
                "source_write_risk": False,
                "would_write_state": False,
                "would_write_reports": False,
                "would_write_experiments": False,
                "blocked_reason": f"dead_duplicate_probe_requires_target_family_simplicity.dead_or_duplicate_entry_scan_got:{target_family}",
            }

        return {
            "executor": "dead_duplicate_entry_probe",
            "child_script": "scripts/learning-v2-dead-duplicate-entry-probe.py",
            "source_write_risk": False,
            "would_write_state": False,
            "would_write_reports": True,
            "would_write_experiments": False,
            "blocked_reason": None,
        }

    if topic == "community-experience" and stage == "community_engagement_path_probe":
        if target_family != "community.engagement_path":
            return {
                "executor": "blocked_community_engagement_path_probe_target_family_mismatch",
                "child_script": None,
                "blocked_reason": f"community_engagement_path_probe_requires_target_family_community.engagement_path_got:{target_family}",
                "source_write_risk": False,
                "would_write_state": False,
                "would_write_reports": True,
                "would_write_experiments": False,
            }
        return {
            "executor": "community_engagement_path_probe",
            "child_script": "scripts/learning-v2-community-engagement-path-probe.py",
            "blocked_reason": None,
            "source_write_risk": False,
            "would_write_state": False,
            "would_write_reports": True,
            "would_write_experiments": False,
        }

    if topic == "community-experience" and stage == "community_onboarding_manual_review_required":
        if target_family != "community.onboarding_experience":
            return {
                "executor": "blocked_community_onboarding_manual_review_target_family_mismatch",
                "child_script": None,
                "blocked_reason": f"community_onboarding_manual_review_required_requires_target_family_community.onboarding_experience_got:{target_family}",
                "source_write_risk": False,
                "would_write_state": False,
                "would_write_reports": True,
                "would_write_experiments": False,
            }
        return {
            "executor": "community_onboarding_manual_review_parker",
            "child_script": "scripts/learning-v2-community-onboarding-manual-review-parker.py",
            "blocked_reason": None,
            "source_write_risk": False,
            "would_write_state": True,
            "would_write_reports": True,
            "would_write_experiments": False,
        }

    if topic == "community-experience" and stage == "community_onboarding_plan_ready":
        if target_family != "community.onboarding_experience":
            return {
                "executor": "blocked_community_onboarding_plan_target_family_mismatch",
                "child_script": None,
                "blocked_reason": f"community_onboarding_plan_ready_requires_target_family_community.onboarding_experience_got:{target_family}",
                "source_write_risk": False,
                "would_write_state": False,
                "would_write_reports": True,
                "would_write_experiments": False,
            }
        return {
            "executor": "community_onboarding_controlled_source_change_plan",
            "child_script": "scripts/learning-v2-community-onboarding-controlled-source-change-plan.py",
            "blocked_reason": None,
            "source_write_risk": False,
            "would_write_state": False,
            "would_write_reports": True,
            "would_write_experiments": False,
        }

    if topic == "community-experience" and stage == "community_onboarding_proposal_ready":
        if target_family != "community.onboarding_experience":
            return {
                "executor": "blocked_community_onboarding_proposal_target_family_mismatch",
                "child_script": None,
                "blocked_reason": f"community_onboarding_proposal_ready_requires_target_family_community.onboarding_experience_got:{target_family}",
                "source_write_risk": False,
                "would_write_state": False,
                "would_write_reports": True,
                "would_write_experiments": False,
            }
        return {
            "executor": "community_onboarding_proposal_planner",
            "child_script": "scripts/learning-v2-community-onboarding-proposal-planner.py",
            "blocked_reason": None,
            "source_write_risk": False,
            "would_write_state": False,
            "would_write_reports": True,
            "would_write_experiments": False,
        }

    if topic == "community-experience" and stage == "community_onboarding_probe":
        if target_family != "community.onboarding_experience":
            return {
                "executor": "blocked_community_onboarding_probe_target_family_mismatch",
                "child_script": None,
                "blocked_reason": f"community_onboarding_probe_requires_target_family_community.onboarding_experience_got:{target_family}",
                "source_write_risk": False,
                "would_write_state": False,
                "would_write_reports": True,
                "would_write_experiments": False,
            }
        return {
            "executor": "community_onboarding_experience_probe",
            "child_script": "scripts/learning-v2-community-onboarding-experience-probe.py",
            "blocked_reason": None,
            "source_write_risk": False,
            "would_write_state": False,
            "would_write_reports": True,
            "would_write_experiments": False,
        }

    child_map = {
        ("simplicity", "nav_inventory_ready"): ("nav_proposal_executor", "scripts/learning-v2-nav-proposal-executor.py"),
        ("simplicity", "nav_discover"): ("nav_discover_executor", "scripts/learning-v2-nav-discover-executor.py"),
        ("simplicity", "validate_blocked"): ("validate_blocked_resolver", "scripts/learning-v2-validate-blocked-resolver.py"),
        ("simplicity", "discover"): ("simplicity_discover_executor", "scripts/learning-v2-discover-executor.py"),
        ("simplicity", "validate"): ("validate_executor", "scripts/learning-v2-validate-executor.py"),
        ("simplicity", "post_validated"): ("outcome_recorder", "scripts/learning-v2-outcome-recorder.py"),
    }

    if stage == "track_complete":
        return {
            "executor": "track_complete_finalizer",
            "child_script": "scripts/learning-v2-track-complete-finalizer.py",
            "source_write_risk": False,
            "would_write_state": True,
            "would_write_reports": True,
            "would_write_experiments": False,
            "blocked_reason": None,
        }

    if (topic, stage) in child_map:
        executor, child_script = child_map[(topic, stage)]
        return {
            "executor": executor,
            "child_script": child_script,
            "source_write_risk": False,
            "would_write_state": True,
            "would_write_reports": True,
            "would_write_experiments": False,
            "blocked_reason": None,
        }

    if topic == "simplicity" and stage == "synthesize":
        return {
            "executor": "simplicity_audit",
            "child_script": "scripts/learning-v2-simplicity-audit.py",
            "source_write_risk": False,
            "would_write_state": True,
            "would_write_reports": True,
            "would_write_experiments": True,
            "blocked_reason": None,
        }

    if topic == "simplicity" and stage == "propose":
        return {
            "executor": "simplicity_propose",
            "child_script": None,
            "source_write_risk": False,
            "would_write_state": True,
            "would_write_reports": True,
            "would_write_experiments": True,
            "blocked_reason": None,
        }

    return {
        "executor": "none",
        "child_script": None,
        "source_write_risk": False,
        "would_write_state": False,
        "would_write_reports": False,
        "would_write_experiments": False,
        "blocked_reason": None,
    }

def apply_simplicity_synthesize(state):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    res = subprocess.run(
        ["python3", str(WORKSPACE / "scripts/learning-v2-simplicity-audit.py")],
        capture_output=True,
        text=True,
        check=True
    )

    lines = [x for x in res.stdout.splitlines() if x.strip()]
    report_path = lines[0] if lines else ""
    metrics = {}
    if len(lines) >= 2:
        try:
            metrics = json.loads("\n".join(lines[1:]))
        except Exception:
            metrics = {}

    exp = {
        "recorded_at": now,
        "topic": "simplicity",
        "stage": "audit_auto",
        "report": report_path,
        "metrics": metrics,
    }
    append_experiment(exp)

    visible_count = metrics.get("visible_entry_count", "?")
    demotable_count = metrics.get("demotable_count", 0)

    state["current_stage"] = "propose"
    state["last_success_at"] = now
    state["last_summary"] = f"已完成 simplicity 自动审计：首屏主要暴露入口 {visible_count} 个，其中 {demotable_count} 个可降权对象。"
    state["next_action"] = "在可降权对象里选 1 个最轻量目标，提出最小调整方案"
    state["carry_over_issue"] = "homepage_too_many_visible_entries" if demotable_count else ""
    state["last_dispatch"] = {
        "generated_at": now_iso(),
        "executor": "simplicity_audit",
        "stage_before": "synthesize",
        "stage_after": "propose",
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }
    save_json(STATE, state)

    print("dispatch_executor = simplicity_audit")
    print("report =", report_path)
    print("metrics =", json.dumps(metrics, ensure_ascii=False))
    print("state_updated = true")

def apply_simplicity_propose(state):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ts = time.strftime("%Y%m%d-%H%M%S", time.localtime())

    demotables = latest_simplicity_demotables()
    target, reason = choose_lightest_target(demotables)

    report_file = REPORT_DIR / f"{ts}-simplicity-proposal-auto.md"
    lines = []
    lines.append("# Learning V2 Simplicity Proposal Auto")
    lines.append("")
    lines.append(f"- generated_at: {now}")
    lines.append(f"- selected_target: {target}")
    lines.append(f"- reason: {reason}")
    lines.append("")
    lines.append("## Minimal Change")
    lines.append("将该对象弱化为非首屏优先入口，或移到对应区块下方/次级位置。")
    lines.append("")
    lines.append("## Verification")
    lines.append("- 首屏主要入口数量减少或首屏次级干扰减弱")
    lines.append("- 不影响战队/积分等核心区块可达性")
    report_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    exp = {
        "recorded_at": now,
        "topic": "simplicity",
        "stage": "propose_auto",
        "selected_target": target,
        "reason": reason,
        "report": str(report_file),
    }
    append_experiment(exp)

    state["current_stage"] = "validate"
    state["last_success_at"] = now
    state["last_summary"] = f"已自动选定“{target}”作为 simplicity 第一轮最小调整对象。下一步只做源码定位，不直接改站。"
    state["next_action"] = f"检查首页源码中“{target}”出现的位置、次数和所在区块，确认最小调整点"
    state["carry_over_issue"] = "homepage_too_many_visible_entries"
    state["last_dispatch"] = {
        "generated_at": now_iso(),
        "executor": "simplicity_propose",
        "stage_before": "propose",
        "stage_after": "validate",
        "selected_target": target,
        "reason": reason,
        "report": str(report_file),
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }
    save_json(STATE, state)

    print("dispatch_executor = simplicity_propose")
    print("selected_target =", target)
    print("report =", report_file)
    print("state_updated = true")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually execute the predicted safe dispatch branch")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = load_json(MODE_POLICY, default={})

    topic = state.get("current_topic")
    stage = state.get("current_stage")
    target_family = state.get("current_target_family")
    mode = current_mode(state, policy)
    mode_rule = (policy.get("modes") or {}).get(mode) or {}
    allow_source_changes = state.get("allow_source_changes")
    integrity = state.get("last_system_integrity") or {}

    failures = []

    if mode == "system_build_only":
        failures.append("system_build_only_blocks_dispatch")

    if mode != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{mode}")

    if state.get("learning_cycle_enabled") is not True:
        failures.append(f"learning_cycle_enabled_not_true:{state.get('learning_cycle_enabled')}")

    if mode_rule.get("stage_executor_allowed") is not True:
        failures.append(f"mode_rule_stage_executor_not_allowed:{mode_rule.get('stage_executor_allowed')}")

    if allow_source_changes is not False:
        failures.append(f"allow_source_changes_not_false:{allow_source_changes}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    branch = predict_branch(topic, stage, allow_source_changes, target_family=target_family)

    if branch["blocked_reason"]:
        failures.append(branch["blocked_reason"])

    if branch["source_write_risk"]:
        failures.append("source_write_risk_detected")

    result = "ok" if not failures else "blocked"

    print("dispatch =", result if args.apply else ("dry_run_ok" if result == "ok" else "dry_run_blocked"))
    print("apply =", str(args.apply).lower())
    print("current_mode =", mode)
    print("current_topic =", topic)
    print("current_stage =", stage)
    print("current_target_family =", target_family)
    print("predicted_executor =", branch["executor"])
    print("child_script =", branch["child_script"])
    print("source_write_risk =", str(branch["source_write_risk"]).lower())
    print("would_write_state =", str(branch["would_write_state"]).lower())
    print("would_write_reports =", str(branch["would_write_reports"]).lower())
    print("would_write_experiments =", str(branch["would_write_experiments"]).lower())
    print("would_write_business_source = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if failures:
        print()
        print("failures:")
        for x in failures:
            print(" ", x)
        raise SystemExit(2)

    if not args.apply:
        print("state_updated = false")
        print("state_written = false")
        return

    if topic is None or stage is None:
        run_child("scripts/learning-v2-topic-selector.py", "--apply")
        print("dispatch_executor = topic_selector")
        print("state_updated = delegated")
        return

    if topic == "simplicity" and stage == "synthesize":
        apply_simplicity_synthesize(state)
        return

    if topic == "simplicity" and stage == "propose":
        apply_simplicity_propose(state)
        return

    if branch["child_script"]:
        run_child(branch["child_script"])
        print("dispatch_executor =", branch["executor"])
        print("state_updated = delegated")
        print("business_source_written = false")
        print("git_commit = false")
        print("git_push = false")
        print("deploy = false")
        return

    print("dispatch_executor = none")
    print("state_updated = false")
    print("state_written = false")

if __name__ == "__main__":
    main()
