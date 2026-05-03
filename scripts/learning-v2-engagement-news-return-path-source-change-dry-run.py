#!/usr/bin/env python3
import difflib
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

DRY_RUN_ID = "learning-v2-engagement-news-return-path-source-change-dry-run-v0"
TARGET_FAMILY = "community.engagement_path"
TARGET_FILE = "public/news.html"
CHANGE_PLAN_ID = "controlled-change-engagement-news-return-path-cta-v0"

REQUIRED_MARKERS = [
    "news-engagement-return-path",
    "news-engagement-return-path-title",
    "看完俱乐部动态",
    "下一步可以很简单",
    "看看 HADO 精彩瞬间",
    "回到首页了解如何开始",
]

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

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def latest_plan_report():
    reports = sorted(REPORT_DIR.glob("community-engagement-path-controlled-source-change-plan-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    plan_path, plan = latest_plan_report()

    failures = []
    warnings = []

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

    if not plan_path:
        failures.append("missing_controlled_source_change_plan")

    if plan.get("result") != "ok":
        failures.append(f"controlled_plan_not_ok:{plan.get('result')}")

    if plan.get("target_family") != TARGET_FAMILY:
        failures.append(f"controlled_plan_target_family_mismatch:{plan.get('target_family')}")

    recommended = plan.get("recommended_first_change") or {}

    if recommended.get("change_plan_id") != CHANGE_PLAN_ID:
        failures.append(f"recommended_change_plan_id_mismatch:{recommended.get('change_plan_id')}")

    if recommended.get("target_file") != TARGET_FILE:
        failures.append(f"recommended_target_file_mismatch:{recommended.get('target_file')}")

    if recommended.get("risk") != "low":
        failures.append(f"recommended_risk_not_low:{recommended.get('risk')}")

    if recommended.get("source_change_allowed_now") is not False:
        failures.append(f"recommended_source_change_allowed_now_not_false:{recommended.get('source_change_allowed_now')}")

    plan_policy = plan.get("policy") or {}
    if plan_policy.get("plan_only") is not True:
        failures.append(f"plan_only_not_true:{plan_policy.get('plan_only')}")

    target_path = WORKSPACE / TARGET_FILE
    if not target_path.exists():
        failures.append(f"target_file_missing:{TARGET_FILE}")

    original = target_path.read_text(encoding="utf-8", errors="ignore") if target_path.exists() else ""

    if "news-engagement-return-path" in original:
        failures.append("target_already_contains_news_engagement_return_path")

    if INSERT_AFTER not in original:
        failures.append("insert_anchor_not_found")

    changed_in_dry_run = False
    proposed = original

    if not failures:
        proposed = original.replace(INSERT_AFTER, INSERT_AFTER + CTA_BLOCK, 1)
        changed_in_dry_run = proposed != original

        if not changed_in_dry_run:
            failures.append("dry_run_proposed_no_change")

        for marker in REQUIRED_MARKERS:
            if marker not in proposed:
                failures.append(f"proposed_missing_marker:{marker}")

        section_marker_count = proposed.count('class="card news-engagement-return-path"')
        title_id_count = proposed.count('id="news-engagement-return-path-title"')

        if section_marker_count != 1:
            failures.append(f"unexpected_section_marker_count:{section_marker_count}")

        if title_id_count != 1:
            failures.append(f"unexpected_title_id_count:{title_id_count}")

        if "<script>" not in original or "<script>" not in proposed:
            failures.append("script_tag_missing_unexpectedly")

        if original.count("<script>") != proposed.count("<script>"):
            failures.append("script_tag_count_changed")

        if original.count("const API =") != proposed.count("const API ="):
            failures.append("api_constant_count_changed")

        if original.count("function renderNews") != proposed.count("function renderNews"):
            failures.append("renderNews_function_count_changed")

        if original.count("function handlePublish") != proposed.count("function handlePublish"):
            failures.append("handlePublish_function_count_changed")

    result = "ok" if not failures else "blocked"

    diff_lines = list(difflib.unified_diff(
        original.splitlines(),
        proposed.splitlines(),
        fromfile=f"{TARGET_FILE}:before",
        tofile=f"{TARGET_FILE}:after-dry-run",
        lineterm="",
    ))

    added_line_count = len([x for x in diff_lines if x.startswith("+") and not x.startswith("+++")])
    removed_line_count = len([x for x in diff_lines if x.startswith("-") and not x.startswith("---")])

    out_json = REPORT_DIR / f"engagement-news-return-path-source-change-dry-run-{stamp()}.json"
    out_md = REPORT_DIR / f"engagement-news-return-path-source-change-dry-run-{stamp()}.md"
    out_diff = REPORT_DIR / f"engagement-news-return-path-source-change-dry-run-{stamp()}.diff"

    payload = {
        "generated_at": now_iso(),
        "dry_run_id": DRY_RUN_ID,
        "result": result,
        "target_family": TARGET_FAMILY,
        "target_file": TARGET_FILE,
        "change_plan_id": CHANGE_PLAN_ID,
        "controlled_source_change_plan": str(plan_path) if plan_path else None,
        "changed_in_dry_run": changed_in_dry_run,
        "source_written": False,
        "state_written": False,
        "business_source_written": False,
        "source_change_gate_opened": False,
        "human_review_required": False,
        "machine_policy_gate": True,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "insert_anchor_found": INSERT_AFTER in original,
        "required_markers": REQUIRED_MARKERS,
        "proposed_contains_required_markers": all(m in proposed for m in REQUIRED_MARKERS),
        "diff_line_count": len(diff_lines),
        "added_line_count": added_line_count,
        "removed_line_count": removed_line_count,
        "diff_path": str(out_diff),
        "recommended_next_step": "run_autonomous_machine_policy_gate_for_engagement_news_return_path" if result == "ok" else "fix_engagement_news_return_path_dry_run_blockers",
        "warnings": warnings,
        "failures": failures,
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_diff.write_text("\n".join(diff_lines) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Engagement News Return Path Source Change Dry Run")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- dry_run_id: `{DRY_RUN_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- target_file: `{TARGET_FILE}`")
    lines.append(f"- changed_in_dry_run: `{str(changed_in_dry_run).lower()}`")
    lines.append("- source_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- human_review_required: `false`")
    lines.append("- machine_policy_gate: `true`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append(f"- added_line_count: `{added_line_count}`")
    lines.append(f"- removed_line_count: `{removed_line_count}`")
    lines.append(f"- diff_path: `{out_diff}`")
    if failures:
        lines.append("")
        lines.append("## Failures")
        for f in failures:
            lines.append(f"- {f}")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("engagement_news_return_path_source_change_dry_run =", result)
    print("target_family =", TARGET_FAMILY)
    print("target_file =", TARGET_FILE)
    print("changed_in_dry_run =", changed_in_dry_run)
    print("source_written = False")
    print("state_written = False")
    print("business_source_written = False")
    print("source_change_gate_opened = False")
    print("human_review_required = False")
    print("machine_policy_gate = True")
    print("git_commit = False")
    print("git_push = False")
    print("deploy = False")
    print("insert_anchor_found =", INSERT_AFTER in original)
    print("proposed_contains_required_markers =", payload["proposed_contains_required_markers"])
    print("diff_line_count =", len(diff_lines))
    print("added_line_count =", added_line_count)
    print("removed_line_count =", removed_line_count)
    print("recommended_next_step =", payload["recommended_next_step"])
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("diff_path =", out_diff)
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
