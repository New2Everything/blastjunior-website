#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
EXPERIMENTS = BASE / "experiments.jsonl"
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

def main():
    state = load_json(STATE, default={})
    topic = state.get("current_topic")
    stage = state.get("current_stage")
    policy = state.get("self_evolution_policy") or {}

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    integrity = state.get("last_system_integrity") or {}
    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    predicted_executor = "none"
    predicted_state_updates = {}
    predicted_files = []
    source_write_risk = False

    if topic == "simplicity" and stage == "propose":
        demotables = latest_simplicity_demotables()
        target, reason = choose_lightest_target(demotables)

        predicted_executor = "simplicity_propose"
        predicted_state_updates = {
            "current_stage": "validate",
            "last_success_at": "<runtime timestamp>",
            "last_summary": f"已自动选定“{target}”作为 simplicity 第一轮最小调整对象。下一步只做源码定位，不直接改站。",
            "next_action": f"检查首页源码中“{target}”出现的位置、次数和所在区块，确认最小调整点",
            "carry_over_issue": "homepage_too_many_visible_entries",
        }
        predicted_files = [
            "learning-v2/reports/<timestamp>-simplicity-proposal-auto.md",
            "learning-v2/experiments.jsonl",
            "learning-v2/state.json",
        ]

        report_extra = {
            "demotables": demotables,
            "selected_target": target,
            "reason": reason,
        }

    elif topic == "simplicity" and stage == "discover":
        predicted_executor = "simplicity_discover_executor"
        predicted_files = [
            "learning-v2/reports/*",
            "learning-v2/state.json",
        ]
        report_extra = {}

    elif topic == "simplicity" and stage in ("apply_ready", "apply_planned", "applied"):
        predicted_executor = f"blocked_write_chain_stage:{stage}"
        source_write_risk = True
        failures.append(f"dangerous_stage_for_observe_only:{stage}")
        report_extra = {}

    else:
        report_extra = {}

    result = "ok" if not failures else "blocked"

    report = {
        "generated_at": now_iso(),
        "probe": "learning-v2-dispatch-probe",
        "result": result,
        "current_topic": topic,
        "current_stage": stage,
        "predicted_executor": predicted_executor,
        "predicted_state_updates": predicted_state_updates,
        "predicted_files": predicted_files,
        "source_write_risk": source_write_risk,
        "failures": failures,
        "extra": report_extra,
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "probe_only": True,
        },
    }

    out = REPORT_DIR / f"dispatch-probe-{stamp()}.json"
    save_json(out, report)

    print("dispatch_probe =", result)
    print("probe_report =", out)
    print("current_topic =", topic)
    print("current_stage =", stage)
    print("predicted_executor =", predicted_executor)
    print("source_write_risk =", str(source_write_risk).lower())
    print("would_write_state =", bool(predicted_state_updates))
    print("would_write_business_source = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if report_extra:
        for k, v in report_extra.items():
            print(f"{k} =", repr(v))

    if failures:
        print()
        print("failures:")
        for x in failures:
            print(" ", x)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
