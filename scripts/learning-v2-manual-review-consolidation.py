#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-manual-review-consolidation-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def classify_manual_review_item(item):
    target = str(item.get("target_family") or "")
    review_count = item.get("review_recommended_count")
    signal_count = item.get("signal_present_count")

    if not isinstance(review_count, int):
        review_count = 1
    if not isinstance(signal_count, int):
        signal_count = 0

    if review_count >= 3:
        return "high", 3, "review_recommended_count>=3"
    if "homepage_primary_cta" in target and review_count >= 2:
        return "high", 3, "homepage_primary_cta_with_multiple_review_gaps"
    if "make-the-first-successful-action-obvious" in target and review_count >= 2 and signal_count == 0:
        return "high", 3, "first_success_action_has_gaps_and_no_signal"

    if review_count >= 2:
        return "medium", 2, "review_recommended_count>=2"
    if "mobile_first" in target and review_count >= 1:
        return "medium", 2, "mobile_first_gap_requires_visual_or_device_review"

    return "low", 1, "low_review_debt"

def load_json(path, default=None):
    if default is None:
        default = {}
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_load_error": str(e), "_path": str(path)}
    return default

def summarize_item(item):
    target = item.get("target_family")
    reason = item.get("reason") or ""
    review_count = item.get("review_recommended_count")
    signal_count = item.get("signal_present_count")

    if "homepage_primary_cta" in str(target):
        category = "homepage_action_priority"
        suggested_review = "人工判断首页第一行动入口是否足够明确；暂不自动改源码。"
    elif "make-the-first-successful-action-obvious" in str(target):
        category = "first_success_action"
        suggested_review = "人工判断新用户第一次成功行动路径是否需要设计方案。"
    elif "mobile_first" in str(target):
        category = "mobile_navigation_density"
        suggested_review = "人工判断移动端导航密度是否真的影响使用；需要结合真实页面截图或测试。"
    elif "community.onboarding_experience" in str(target):
        category = "community_onboarding"
        suggested_review = "这是较早的 controlled source change plan，需人工决定是否进入 source_change_gate。"
    else:
        category = "general_research_gap"
        suggested_review = "人工复核该 gap 是否仍有业务价值，再决定是否转为 source-change proposal。"

    severity, score, score_reason = classify_manual_review_item(item)

    return {
        "item_id": item.get("item_id"),
        "target_family": target,
        "category": category,
        "severity": severity,
        "score": score,
        "score_reason": score_reason,
        "status": item.get("status"),
        "reason": reason,
        "review_recommended_count": review_count,
        "signal_present_count": signal_count,
        "resolver_report": item.get("resolver_report"),
        "probe_report": item.get("probe_report"),
        "plan_report": item.get("plan_report"),
        "proposal_report": item.get("proposal_report"),
        "suggested_review": suggested_review,
        "recommended_next_step": item.get("recommended_next_step"),
        "source_change_allowed_now": False,
        "business_source_written": False,
        "website_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 only writes reports/snapshots.")
    args = ap.parse_args()

    state = load_json(BASE / "state.json", {})
    items = state.get("manual_review_items") or []

    summaries = [summarize_item(x) for x in items]
    by_category = Counter(x["category"] for x in summaries)
    by_severity = Counter(x["severity"] for x in summaries)
    review_debt_score = sum(int(x.get("score") or 0) for x in summaries)
    review_debt_threshold = 8

    if not summaries:
        decision = "no_manual_review_items"
        recommended_next_action = "return_to_next_cycle_controller"
    else:
        decision = "manual_review_queue_ready_for_human_triage"
        recommended_next_action = "human_review_manual_items_then_decide_source_change_gate_or_archive"

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "decision": decision,
        "recommended_next_action": recommended_next_action,
        "manual_review_count": len(summaries),
        "by_category": dict(by_category),
        "by_severity": dict(by_severity),
        "review_debt_score": review_debt_score,
        "review_debt_threshold": review_debt_threshold,
        "manual_review_items": summaries,
        "human_review_policy": {
            "do_not_auto_edit_website": True,
            "do_not_open_source_change_gate": True,
            "do_not_commit": True,
            "do_not_push": True,
            "do_not_deploy": True,
            "allowed_now": [
                "read reports",
                "summarize gaps",
                "choose archive / keep pending / approve proposal planning"
            ],
        },
        "business_source_written": False,
        "website_source_written": False,
        "state_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }

    ts = stamp()
    json_path = REPORT_DIR / f"learning-v2-manual-review-consolidation-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-manual-review-consolidation-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Manual Review Consolidation Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- decision: `{decision}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- manual_review_count: `{len(summaries)}`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Category Counts")
    md.append("")
    for k, v in by_category.items():
        md.append(f"- {k}: `{v}`")
    md.append("")
    md.append("## Severity Counts")
    md.append("")
    for k, v in by_severity.items():
        md.append(f"- {k}: `{v}`")
    md.append("")
    md.append("## Review Debt")
    md.append("")
    md.append(f"- review_debt_score: `{review_debt_score}`")
    md.append(f"- review_debt_threshold: `{review_debt_threshold}`")
    md.append("")
    md.append("## Manual Review Items")
    md.append("")
    for x in summaries:
        md.append(f"### {x['target_family']}")
        md.append("")
        md.append(f"- item_id: `{x['item_id']}`")
        md.append(f"- category: `{x['category']}`")
        md.append(f"- severity: `{x['severity']}`")
        md.append(f"- score: `{x.get('score')}`")
        md.append(f"- score_reason: `{x.get('score_reason')}`")
        md.append(f"- review_recommended_count: `{x['review_recommended_count']}`")
        md.append(f"- signal_present_count: `{x['signal_present_count']}`")
        md.append(f"- reason: {x['reason']}")
        md.append(f"- suggested_review: {x['suggested_review']}")
        md.append(f"- recommended_next_step: {x['recommended_next_step']}")
        md.append(f"- probe_report: `{x.get('probe_report')}`")
        md.append(f"- resolver_report: `{x.get('resolver_report')}`")
        md.append("")
    md.append("## Safety")
    md.append("")
    md.append("- business_source_written: `false`")
    md.append("- website_source_written: `false`")
    md.append("- state_written: `false`")
    md.append("- git_commit: `false`")
    md.append("- git_push: `false`")
    md.append("- deploy: `false`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("manual_review_consolidation = ok")
    print("mode = dry_run")
    print("decision =", decision)
    print("recommended_next_action =", recommended_next_action)
    print("manual_review_count =", len(summaries))
    print("by_category =", json.dumps(dict(by_category), ensure_ascii=False))
    print("by_severity =", json.dumps(dict(by_severity), ensure_ascii=False))
    print("review_debt_score =", review_debt_score)
    print("review_debt_threshold =", review_debt_threshold)
    print("report_json =", json_path)
    print("report_md =", md_path)
    print("business_source_written = false")
    print("website_source_written = false")
    print("state_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    raise SystemExit(main())
