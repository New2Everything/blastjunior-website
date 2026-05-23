#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FAMILY = "simplicity.dead_or_duplicate_entry_scan"

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

def latest_probe_report():
    reports = sorted(REPORT_DIR.glob("dead-duplicate-entry-probe-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def candidate_priority(item):
    reason = item.get("reason", "")
    file = item.get("file", "")
    line = item.get("line") or 0

    score = 0

    if "dead_or_leftover_style_selector" in reason:
        score += 90

    if "join_cta_repeated" in reason:
        score += 70

    if "gallery_entry_already_deprioritized" in reason:
        score += 50

    if "generic_chat_send_button" in reason:
        score -= 30

    if file == "public/styles.css":
        score += 20

    if file == "components/nav.html":
        score += 10

    return score * 10000 - int(line)

def build_review_items(probe):
    weak = probe.get("weak_candidates") or []
    items = []

    for x in weak:
        item = dict(x)
        item["priority_score"] = candidate_priority(item)

        reason = item.get("reason", "")

        if "dead_or_leftover_style_selector" in reason:
            item["proposal_type"] = "style_leftover_review"
            item["proposal_summary"] = "Review whether .section-more is now unused or only serves removed/commented-out links."
            item["apply_allowed_now"] = False

        elif "join_cta_repeated" in reason:
            item["proposal_type"] = "duplicate_cta_review"
            item["proposal_summary"] = "Review join CTA duplication across nav link and primary button before any source action."
            item["apply_allowed_now"] = False

        elif "gallery_entry_already_deprioritized" in reason:
            item["proposal_type"] = "auto_applied_comment_audit"
            item["proposal_summary"] = "Keep as evidence of prior auto-applied change; no new source action."
            item["apply_allowed_now"] = False

        elif "generic_chat_send_button" in reason:
            item["proposal_type"] = "protected_interaction_observation"
            item["proposal_summary"] = "Chat send button is interactive and should not be simplified automatically."
            item["apply_allowed_now"] = False

        else:
            item["proposal_type"] = "autonomous_policy_review"
            item["proposal_summary"] = "Manual review only."
            item["apply_allowed_now"] = False

        items.append(item)

    items.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
    return items

def write_report(state, probe_path, probe, items, apply):
    suffix = "apply" if apply else "dry-run"
    out = REPORT_DIR / f"dead-duplicate-review-executor-{suffix}-{stamp()}.md"

    duplicate_labels = probe.get("duplicate_labels") or {}
    auto_applied_comments = probe.get("auto_applied_comments") or []
    weak_candidates = probe.get("weak_candidates") or []

    lines = []
    lines.append("# Dead / Duplicate Review Executor")
    lines.append("")
    lines.append(f"- generated_at: `{now_iso()}`")
    lines.append(f"- mode: `{'apply' if apply else 'dry-run'}`")
    lines.append(f"- topic: `{state.get('current_topic')}`")
    lines.append(f"- stage_before: `{state.get('current_stage')}`")
    lines.append(f"- target_family: `{state.get('current_target_family')}`")
    lines.append(f"- latest_probe: `{probe_path}`")
    lines.append("- source_changed: `false`")
    lines.append(f"- state_written: `{'true' if apply else 'false'}`")
    lines.append("")
    lines.append("## Evidence summary")
    lines.append("")
    lines.append(f"- duplicate_label_count: `{len(duplicate_labels)}`")
    lines.append(f"- auto_applied_comment_count: `{len(auto_applied_comments)}`")
    lines.append(f"- weak_candidate_count: `{len(weak_candidates)}`")
    lines.append("")
    lines.append("## Proposal-only candidates")
    lines.append("")
    if not items:
        lines.append("No candidate found.")
        lines.append("")
    else:
        for idx, item in enumerate(items, 1):
            lines.append(f"### {idx}. `{item.get('proposal_type')}`")
            lines.append("")
            lines.append(f"- location: `{item.get('file')}:{item.get('line')}`")
            lines.append(f"- reason: `{item.get('reason')}`")
            lines.append(f"- priority_score: `{item.get('priority_score')}`")
            lines.append(f"- apply_allowed_now: `{str(item.get('apply_allowed_now')).lower()}`")
            lines.append(f"- proposal: {item.get('proposal_summary')}")
            lines.append("")
            lines.append("```")
            lines.append(item.get("text") or "")
            lines.append("```")
            lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append("This executor is proposal-only. It must not modify website source in learning_observe_only.")
    lines.append("If applied, it only advances state to `dead_duplicate_proposal_ready`.")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write proposal-ready state only")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    probe_path, probe = latest_probe_report()

    print("dead_duplicate_review_executor =", "apply" if args.apply else "dry_run")
    print("current_topic =", state.get("current_topic"))
    print("current_stage =", state.get("current_stage"))
    print("current_target_family =", state.get("current_target_family"))

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("current_topic") != "simplicity":
        failures.append(f"current_topic_not_simplicity:{state.get('current_topic')}")

    if state.get("current_stage") != "dead_duplicate_review_ready":
        failures.append(f"current_stage_not_dead_duplicate_review_ready:{state.get('current_stage')}")

    if state.get("current_target_family") != TARGET_FAMILY:
        failures.append(f"target_family_mismatch:{state.get('current_target_family')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if not probe_path:
        failures.append("missing_dead_duplicate_probe_report")

    if probe.get("target_family") != TARGET_FAMILY:
        failures.append(f"probe_target_family_mismatch:{probe.get('target_family')}")

    items = build_review_items(probe)
    report_path = write_report(state, probe_path, probe, items, args.apply)

    if failures:
        print("dead_duplicate_review_executor_result = blocked")
        print("review_report =", report_path)
        for x in failures:
            print("failure =", x)
        print("state_written = false")
        print("business_source_written = false")
        print("git_commit = false")
        print("git_push = false")
        print("deploy = false")
        raise SystemExit(2)

    print("dead_duplicate_review_executor_result =", "proposal_ready" if args.apply else "would_proposal_ready")
    print("latest_probe =", probe_path)
    print("review_report =", report_path)
    print("proposal_candidate_count =", len(items))
    print("would_set_stage = dead_duplicate_proposal_ready")
    print("source_changed = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if items:
        top = items[0]
        print("top_candidate =", f"{top.get('file')}:{top.get('line')}")
        print("top_candidate_type =", top.get("proposal_type"))
        print("top_candidate_apply_allowed_now =", str(top.get("apply_allowed_now")).lower())

    if not args.apply:
        print("state_written = false")
        print("state_updated = false")
        return 0

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "dead_duplicate_review_executor",
        "stage_before": "dead_duplicate_review_ready",
        "stage_after": "dead_duplicate_proposal_ready",
        "target_family": TARGET_FAMILY,
        "probe_report": str(probe_path),
        "review_report": str(report_path),
        "proposal_candidate_count": len(items),
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    })

    state["last_dead_duplicate_review"] = {
        "at": now_iso(),
        "result": "dead_duplicate_proposal_ready",
        "target_family": TARGET_FAMILY,
        "probe_report": str(probe_path),
        "review_report": str(report_path),
        "proposal_candidate_count": len(items),
        "top_candidate": items[0] if items else None,
        "source_changed": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }

    state["current_stage"] = "dead_duplicate_proposal_ready"
    state["next_action"] = (
        "Review proposal-only candidates. No website source change is allowed in learning_observe_only."
    )
    state["updated_at"] = now_iso()

    save_json(STATE, state)

    print("state_written = true")
    print("state_updated = true")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
