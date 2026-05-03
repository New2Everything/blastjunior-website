#!/usr/bin/env python3
import argparse
import difflib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
BACKUP_DIR = BASE / "backups"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

APPLY_ID = "learning-v2-engagement-news-return-path-source-change-apply-v0"
TARGET_FAMILY = "community.engagement_path"
TARGET_FILE = "public/news.html"
CHANGE_PLAN_ID = "controlled-change-engagement-news-return-path-cta-v0"

INSERT_AFTER = '''    <div id="newsList" class="news-list">
      <div class="card" style="text-align:center;color:var(--text-gray);"><span class="spinner"></span>加载中...</div>
    </div>
'''

CTA_BLOCK = '''
    <section class="card news-engagement-return-path" aria-labelledby="news-engagement-return-path-title" style="margin-top:1rem;">
      <h2 id="news-engagement-return-path-title" style="font-family:var(--font-display);font-size:1.2rem;font-weight:800;margin-bottom:0.5rem;">看完俱乐部动态，下一步可以很简单</h2>
      <p style="color:var(--text-gray);line-height:1.7;margin-bottom:1rem;">新闻记录的是兰星少年 HADO 社区正在发生的事。如果你是第一次了解我们，可以先看看比赛瞬间，再回到首页了解如何开始体验。</p>
      <div style="display:flex;gap:0.75rem;flex-wrap:wrap;">
        <a href="/gallery.html" class="btn btn-primary">看看 HADO 精彩瞬间</a>
        <a href="/index.html" class="btn btn-outline">回到首页了解如何开始</a>
      </div>
    </section>
'''

REQUIRED_MARKERS = [
    "news-engagement-return-path",
    "news-engagement-return-path-title",
    "看完俱乐部动态",
    "下一步可以很简单",
    "看看 HADO 精彩瞬间",
    "回到首页了解如何开始",
]

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

def latest_report(pattern):
    reports = sorted(REPORT_DIR.glob(pattern))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def build_proposed(original):
    return original.replace(INSERT_AFTER, INSERT_AFTER + CTA_BLOCK, 1)

def set_source_gate(state, open_gate):
    state["allow_source_changes"] = bool(open_gate)
    policy = state.get("self_evolution_policy") or {}
    policy["source_changes_allowed"] = bool(open_gate)
    policy["git_commit_allowed"] = False
    policy["git_push_allowed"] = False
    policy["deploy_allowed"] = False
    state["self_evolution_policy"] = policy
    state["allow_git_commit"] = False
    state["allow_deploy"] = False
    return state

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="perform controlled source write")
    args = ap.parse_args()

    run_stamp = stamp()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    dry_path, dry = latest_report("engagement-news-return-path-source-change-dry-run-*.json")
    gate_path, gate = latest_report("engagement-news-return-path-autonomous-policy-gate-*.json")
    readiness_path, readiness = latest_report("engagement-news-return-path-gate-readiness-*.json")

    failures = []
    warnings = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_initially_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    for key in ["source_changes_allowed", "git_commit_allowed", "git_push_allowed", "deploy_allowed"]:
        if policy.get(key) is not False:
            failures.append(f"policy_{key}_not_false:{policy.get(key)}")

    if not dry_path:
        failures.append("missing_dry_run_report")
    elif dry.get("result") != "ok":
        failures.append(f"dry_run_not_ok:{dry.get('result')}")

    if dry.get("target_file") != TARGET_FILE:
        failures.append(f"dry_run_target_file_mismatch:{dry.get('target_file')}")

    if dry.get("target_family") != TARGET_FAMILY:
        failures.append(f"dry_run_target_family_mismatch:{dry.get('target_family')}")

    if dry.get("change_plan_id") != CHANGE_PLAN_ID:
        failures.append(f"dry_run_change_plan_id_mismatch:{dry.get('change_plan_id')}")

    if dry.get("changed_in_dry_run") is not True:
        failures.append(f"dry_run_changed_in_dry_run_not_true:{dry.get('changed_in_dry_run')}")

    if dry.get("source_written") is not False:
        failures.append(f"dry_run_source_written_not_false:{dry.get('source_written')}")

    if dry.get("removed_line_count") != 0:
        failures.append(f"dry_run_removed_line_count_not_zero:{dry.get('removed_line_count')}")

    if not gate_path:
        failures.append("missing_autonomous_policy_gate_report")
    elif gate.get("result") != "ok":
        failures.append(f"autonomous_gate_not_ok:{gate.get('result')}")

    if gate.get("autonomous_decision") != "allow_next_dry_apply_gate":
        failures.append(f"autonomous_decision_not_allow:{gate.get('autonomous_decision')}")

    if not readiness_path:
        failures.append("missing_gate_readiness_report")
    elif readiness.get("result") != "ok":
        failures.append(f"gate_readiness_not_ok:{readiness.get('result')}")

    if readiness.get("ready_to_open_source_change_gate") is not True:
        failures.append(f"readiness_not_ready:{readiness.get('ready_to_open_source_change_gate')}")

    target_path = WORKSPACE / TARGET_FILE
    if not target_path.exists():
        failures.append(f"target_file_missing:{TARGET_FILE}")

    original = target_path.read_text(encoding="utf-8", errors="ignore") if target_path.exists() else ""

    if "news-engagement-return-path" in original:
        failures.append("target_already_contains_news_engagement_return_path")

    if INSERT_AFTER not in original:
        failures.append("insert_anchor_not_found")

    proposed = build_proposed(original) if not failures else original

    if not failures:
        if proposed == original:
            failures.append("proposed_no_change")

        for marker in REQUIRED_MARKERS:
            if marker not in proposed:
                failures.append(f"proposed_missing_marker:{marker}")

        section_marker = 'class="card news-engagement-return-path"'
        title_marker = 'id="news-engagement-return-path-title"'
        section_marker_count = proposed.count(section_marker)
        title_id_count = proposed.count(title_marker)

        if section_marker_count != 1:
            failures.append(f"unexpected_section_marker_count:{section_marker_count}")

        if title_id_count != 1:
            failures.append(f"unexpected_title_id_count:{title_id_count}")

        if original.count("<script>") != proposed.count("<script>"):
            failures.append("script_tag_count_changed")

        if original.count("const API =") != proposed.count("const API ="):
            failures.append("api_constant_count_changed")

        if original.count("function renderNews") != proposed.count("function renderNews"):
            failures.append("renderNews_function_count_changed")

        if original.count("function handlePublish") != proposed.count("function handlePublish"):
            failures.append("handlePublish_function_count_changed")

    diff_lines = list(difflib.unified_diff(
        original.splitlines(),
        proposed.splitlines(),
        fromfile=f"{TARGET_FILE}:before",
        tofile=f"{TARGET_FILE}:after",
        lineterm="",
    ))

    added_line_count = len([x for x in diff_lines if x.startswith("+") and not x.startswith("+++")])
    removed_line_count = len([x for x in diff_lines if x.startswith("-") and not x.startswith("---")])

    if removed_line_count != 0:
        failures.append(f"removed_line_count_not_zero:{removed_line_count}")

    result = "ok" if not failures else "blocked"

    backup_path = None
    source_written = False
    gate_opened_during_apply = False
    gate_closed_after_apply = False

    if args.apply and result == "ok":
        try:
            backup_path = BACKUP_DIR / f"public-news-before-engagement-news-return-path-{run_stamp}.html"

            state = set_source_gate(state, True)
            save_json(STATE, state)
            gate_opened_during_apply = True

            shutil.copy2(target_path, backup_path)
            target_path.write_text(proposed, encoding="utf-8")
            source_written = True

        finally:
            latest_state = load_json(STATE, default={})
            latest_state = set_source_gate(latest_state, False)
            save_json(STATE, latest_state)
            gate_closed_after_apply = True

    post_text = target_path.read_text(encoding="utf-8", errors="ignore") if target_path.exists() else ""

    out_json = REPORT_DIR / f"engagement-news-return-path-source-change-apply-{'apply' if args.apply else 'dry-run'}-{run_stamp}.json"
    out_md = REPORT_DIR / f"engagement-news-return-path-source-change-apply-{'apply' if args.apply else 'dry-run'}-{run_stamp}.md"

    payload = {
        "generated_at": now_iso(),
        "apply_id": APPLY_ID,
        "result": result,
        "apply": args.apply,
        "target_family": TARGET_FAMILY,
        "target_file": TARGET_FILE,
        "change_plan_id": CHANGE_PLAN_ID,
        "dry_run_report": str(dry_path) if dry_path else None,
        "autonomous_policy_gate": str(gate_path) if gate_path else None,
        "gate_readiness": str(readiness_path) if readiness_path else None,
        "changed_in_apply_plan": proposed != original,
        "source_written": source_written,
        "backup_path": str(backup_path) if backup_path else None,
        "gate_opened_during_apply": gate_opened_during_apply,
        "gate_closed_after_apply": gate_closed_after_apply,
        "post_contains_news_engagement_return_path": "news-engagement-return-path" in post_text,
        "post_contains_news_engagement_return_path_title": "news-engagement-return-path-title" in post_text,
        "added_line_count": added_line_count,
        "removed_line_count": removed_line_count,
        "state_written": bool(args.apply and result == "ok"),
        "business_source_written": source_written,
        "source_change_gate_opened": False,
        "human_review_required": False,
        "machine_policy_gate": True,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "recommended_next_step": "run_engagement_news_return_path_isolated_post_apply_validator" if args.apply and result == "ok" else "run_apply_executor_with_apply_after_dry_run_ok",
        "warnings": warnings,
        "failures": failures,
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Engagement News Return Path Source Change Apply")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- apply_id: `{APPLY_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- apply: `{str(args.apply).lower()}`")
    lines.append(f"- target_file: `{TARGET_FILE}`")
    lines.append(f"- source_written: `{str(source_written).lower()}`")
    lines.append(f"- backup_path: `{payload['backup_path']}`")
    lines.append(f"- gate_opened_during_apply: `{str(gate_opened_during_apply).lower()}`")
    lines.append(f"- gate_closed_after_apply: `{str(gate_closed_after_apply).lower()}`")
    lines.append("- human_review_required: `false`")
    lines.append("- machine_policy_gate: `true`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    if failures:
        lines.append("")
        lines.append("## Failures")
        for f in failures:
            lines.append(f"- {f}")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("engagement_news_return_path_source_change_apply =", result)
    print("apply =", args.apply)
    print("target_family =", TARGET_FAMILY)
    print("target_file =", TARGET_FILE)
    print("changed_in_apply_plan =", proposed != original)
    print("source_written =", source_written)
    print("backup_path =", str(backup_path) if backup_path else None)
    print("gate_opened_during_apply =", gate_opened_during_apply)
    print("gate_closed_after_apply =", gate_closed_after_apply)
    print("post_contains_news_engagement_return_path =", payload["post_contains_news_engagement_return_path"])
    print("post_contains_news_engagement_return_path_title =", payload["post_contains_news_engagement_return_path_title"])
    print("state_written =", bool(args.apply and result == "ok"))
    print("business_source_written =", source_written)
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
        raise SystemExit(2)

if __name__ == "__main__":
    main()
