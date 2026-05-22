#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
RESEARCH = BASE / "research"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

CONTROLLER_ID = "learning-v2-next-cycle-controller-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    if default is None:
        default = {}
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_load_error": str(e), "_path": str(path)}
    return default

def load_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows

def latest_report(pattern):
    files = sorted(REPORT_DIR.glob(pattern))
    return files[-1] if files else None


RESOLVED_MANUAL_REVIEW_STATUSES = {
    "archived_superseded",
    "proposal_planning_approved",
    "evidence_requested",
    "archived_no_action",
    "archived",
}


def is_open_manual_review_item(item):
    status = item.get("status")
    status_after = item.get("status_after_decision")
    action = item.get("human_review_decision_action")

    if status in RESOLVED_MANUAL_REVIEW_STATUSES:
        return False
    if status_after in RESOLVED_MANUAL_REVIEW_STATUSES:
        return False
    if action in {
        "archive_manual_review_item",
        "mark_proposal_planning_approved",
        "mark_evidence_requested",
    }:
        return False
    return True

def classify_manual_review_item(item):
    target = str(item.get("target_family") or "")
    review_count = item.get("review_recommended_count")
    signal_count = item.get("signal_present_count")

    if not isinstance(review_count, int):
        review_count = 1
    if not isinstance(signal_count, int):
        signal_count = 0

    # High severity: many explicit gaps, or action-critical first-success/homepage problems with low signal.
    if review_count >= 3:
        return "high", 3, "review_recommended_count>=3"
    if "homepage_primary_cta" in target and review_count >= 2:
        return "high", 3, "homepage_primary_cta_with_multiple_review_gaps"
    if "make-the-first-successful-action-obvious" in target and review_count >= 2 and signal_count == 0:
        return "high", 3, "first_success_action_has_gaps_and_no_signal"

    # Medium severity: meaningful gaps exist, but some signal is present or scope is narrower.
    if review_count >= 2:
        return "medium", 2, "review_recommended_count>=2"
    if "mobile_first" in target and review_count >= 1:
        return "medium", 2, "mobile_first_gap_requires_visual_or_device_review"

    # Low severity: one weak or old review item.
    return "low", 1, "low_review_debt"


def compute_review_debt(manual_review_items):
    items = []
    total_score = 0

    for item in manual_review_items:
        severity, score, reason = classify_manual_review_item(item)
        total_score += score
        items.append({
            "item_id": item.get("item_id"),
            "target_family": item.get("target_family"),
            "severity": severity,
            "score": score,
            "score_reason": reason,
            "review_recommended_count": item.get("review_recommended_count"),
            "signal_present_count": item.get("signal_present_count"),
            "status": item.get("status"),
            "reason": item.get("reason"),
        })

    return {
        "review_debt_score": total_score,
        "review_debt_threshold": 8,
        "review_debt_items": items,
        "review_debt_by_severity": {
            "high": sum(1 for x in items if x["severity"] == "high"),
            "medium": sum(1 for x in items if x["severity"] == "medium"),
            "low": sum(1 for x in items if x["severity"] == "low"),
        },
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; controller is dry-run only in v0.")
    args = ap.parse_args()

    state = load_json(BASE / "state.json", {})
    candidates = load_jsonl(RESEARCH / "target-family-candidates.jsonl")
    triage = load_jsonl(RESEARCH / "web-source-candidate-relevance-triage.jsonl")
    sources = load_jsonl(RESEARCH / "sources.jsonl")
    digests = load_jsonl(RESEARCH / "digests.jsonl")
    patterns = load_jsonl(RESEARCH / "design-patterns.jsonl")
    queue = load_jsonl(RESEARCH / "web-source-discovery-queue.jsonl")

    latest_auto_path = latest_report("autonomous-target-discovery-*.json")
    latest_auto = load_json(latest_auto_path, {}) if latest_auto_path else {}

    latest_source_discovery_path = latest_report("research-web-candidate-discovery-v1-*.json")
    latest_source_discovery = load_json(latest_source_discovery_path, {}) if latest_source_discovery_path else {}

    latest_manual_consolidation_path = latest_report("learning-v2-manual-review-consolidation-dry-run-*.json")
    latest_manual_consolidation = load_json(latest_manual_consolidation_path, {}) if latest_manual_consolidation_path else {}

    latest_proposal_planning_path = latest_report("learning-v2-proposal-planning-dry-run-*.json")
    latest_proposal_planning = load_json(latest_proposal_planning_path, {}) if latest_proposal_planning_path else {}

    latest_consolidated_review_path = latest_report("learning-v2-consolidated-source-change-review-packet-dry-run-*.json")
    latest_consolidated_review = load_json(latest_consolidated_review_path, {}) if latest_consolidated_review_path else {}

    latest_autonomous_review_policy_path = latest_report("learning-v2-autonomous-review-policy-dry-run-*.json")
    latest_autonomous_review_policy = load_json(latest_autonomous_review_policy_path, {}) if latest_autonomous_review_policy_path else {}

    latest_source_change_plan_path = latest_report("learning-v2-source-change-plan-dry-run-*.json")
    latest_source_change_plan = load_json(latest_source_change_plan_path, {}) if latest_source_change_plan_path else {}

    latest_source_change_plan_auditor_path = latest_report("learning-v2-source-change-plan-auditor-dry-run-*.json")
    latest_source_change_plan_auditor = load_json(latest_source_change_plan_auditor_path, {}) if latest_source_change_plan_auditor_path else {}

    latest_source_change_gate_readiness_path = latest_report("learning-v2-source-change-gate-readiness-dry-run-*.json")
    latest_source_change_gate_readiness = load_json(latest_source_change_gate_readiness_path, {}) if latest_source_change_gate_readiness_path else {}

    latest_file_level_patch_preview_path = latest_report("learning-v2-file-level-patch-preview-dry-run-*.json")
    latest_file_level_patch_preview = load_json(latest_file_level_patch_preview_path, {}) if latest_file_level_patch_preview_path else {}

    latest_patch_preview_auditor_path = latest_report("learning-v2-patch-preview-auditor-dry-run-*.json")
    latest_patch_preview_auditor = load_json(latest_patch_preview_auditor_path, {}) if latest_patch_preview_auditor_path else {}

    latest_source_change_gate_open_policy_path = latest_report("learning-v2-source-change-gate-open-policy-dry-run-*.json")
    latest_source_change_gate_open_policy = load_json(latest_source_change_gate_open_policy_path, {}) if latest_source_change_gate_open_policy_path else {}

    latest_pre_change_evidence_snapshot_path = latest_report("learning-v2-pre-change-evidence-snapshot-dry-run-*.json")
    latest_pre_change_evidence_snapshot = load_json(latest_pre_change_evidence_snapshot_path, {}) if latest_pre_change_evidence_snapshot_path else {}

    latest_pre_change_evidence_auditor_path = latest_report("learning-v2-pre-change-evidence-auditor-dry-run-*.json")
    latest_pre_change_evidence_auditor = load_json(latest_pre_change_evidence_auditor_path, {}) if latest_pre_change_evidence_auditor_path else {}

    latest_required_gate_evidence_modules_path = latest_report("learning-v2-required-gate-evidence-modules-dry-run-*.json")
    latest_required_gate_evidence_modules = load_json(latest_required_gate_evidence_modules_path, {}) if latest_required_gate_evidence_modules_path else {}

    latest_required_gate_evidence_modules_auditor_path = latest_report("learning-v2-required-gate-evidence-modules-auditor-dry-run-*.json")
    latest_required_gate_evidence_modules_auditor = load_json(latest_required_gate_evidence_modules_auditor_path, {}) if latest_required_gate_evidence_modules_auditor_path else {}

    latest_final_source_change_gate_auditor_path = latest_report("learning-v2-final-source-change-gate-auditor-dry-run-*.json")
    latest_final_source_change_gate_auditor = load_json(latest_final_source_change_gate_auditor_path, {}) if latest_final_source_change_gate_auditor_path else {}

    latest_source_change_gate_open_request_path = latest_report("learning-v2-source-change-gate-open-request-dry-run-*.json")
    latest_source_change_gate_open_request = load_json(latest_source_change_gate_open_request_path, {}) if latest_source_change_gate_open_request_path else {}

    latest_source_change_gate_open_request_auditor_path = latest_report("learning-v2-source-change-gate-open-request-auditor-dry-run-*.json")
    latest_source_change_gate_open_request_auditor = load_json(latest_source_change_gate_open_request_auditor_path, {}) if latest_source_change_gate_open_request_auditor_path else {}

    latest_source_change_gate_opener_path = latest_report("learning-v2-source-change-gate-opener-dry-run-*.json")
    latest_source_change_gate_opener = load_json(latest_source_change_gate_opener_path, {}) if latest_source_change_gate_opener_path else {}

    latest_source_change_gate_opener_auditor_path = latest_report("learning-v2-source-change-gate-opener-auditor-dry-run-*.json")
    latest_source_change_gate_opener_auditor = load_json(latest_source_change_gate_opener_auditor_path, {}) if latest_source_change_gate_opener_auditor_path else {}

    latest_controlled_source_change_apply_path = latest_report("learning-v2-controlled-source-change-apply-dry-run-*.json")
    latest_controlled_source_change_apply = load_json(latest_controlled_source_change_apply_path, {}) if latest_controlled_source_change_apply_path else {}

    latest_controlled_source_change_apply_auditor_path = latest_report("learning-v2-controlled-source-change-apply-auditor-dry-run-*.json")
    latest_controlled_source_change_apply_auditor = load_json(latest_controlled_source_change_apply_auditor_path, {}) if latest_controlled_source_change_apply_auditor_path else {}

    latest_controlled_source_change_real_write_request_path = latest_report("learning-v2-controlled-source-change-real-write-request-dry-run-*.json")
    latest_controlled_source_change_real_write_request = load_json(latest_controlled_source_change_real_write_request_path, {}) if latest_controlled_source_change_real_write_request_path else {}

    latest_controlled_source_change_real_write_request_auditor_path = latest_report("learning-v2-controlled-source-change-real-write-request-auditor-dry-run-*.json")
    latest_controlled_source_change_real_write_request_auditor = load_json(latest_controlled_source_change_real_write_request_auditor_path, {}) if latest_controlled_source_change_real_write_request_auditor_path else {}

    latest_deployment_route_contract_path = latest_report("learning-v2-deployment-route-contract-dry-run-*.json")
    latest_deployment_route_contract = load_json(latest_deployment_route_contract_path, {}) if latest_deployment_route_contract_path else {}

    latest_deployment_route_contract_auditor_path = latest_report("learning-v2-deployment-route-contract-auditor-dry-run-*.json")
    latest_deployment_route_contract_auditor = load_json(latest_deployment_route_contract_auditor_path, {}) if latest_deployment_route_contract_auditor_path else {}

    latest_controlled_source_change_real_write_executor_path = latest_report("learning-v2-controlled-source-change-real-write-executor-dry-run-*.json")
    latest_controlled_source_change_real_write_executor = load_json(latest_controlled_source_change_real_write_executor_path, {}) if latest_controlled_source_change_real_write_executor_path else {}

    latest_controlled_source_change_real_write_executor_auditor_path = latest_report("learning-v2-controlled-source-change-real-write-executor-auditor-dry-run-*.json")
    latest_controlled_source_change_real_write_executor_auditor = load_json(latest_controlled_source_change_real_write_executor_auditor_path, {}) if latest_controlled_source_change_real_write_executor_auditor_path else {}

    latest_controlled_source_change_real_write_apply_request_path = latest_report("learning-v2-controlled-source-change-real-write-apply-request-dry-run-*.json")
    latest_controlled_source_change_real_write_apply_request = load_json(latest_controlled_source_change_real_write_apply_request_path, {}) if latest_controlled_source_change_real_write_apply_request_path else {}

    latest_controlled_source_change_real_write_apply_request_auditor_path = latest_report("learning-v2-controlled-source-change-real-write-apply-request-auditor-dry-run-*.json")
    latest_controlled_source_change_real_write_apply_request_auditor = load_json(latest_controlled_source_change_real_write_apply_request_auditor_path, {}) if latest_controlled_source_change_real_write_apply_request_auditor_path else {}

    latest_controlled_source_change_real_write_apply_executor_path = latest_report("learning-v2-controlled-source-change-real-write-apply-executor-dry-run-*.json")
    latest_controlled_source_change_real_write_apply_executor = load_json(latest_controlled_source_change_real_write_apply_executor_path, {}) if latest_controlled_source_change_real_write_apply_executor_path else {}

    latest_controlled_source_change_real_write_apply_executor_auditor_path = latest_report("learning-v2-controlled-source-change-real-write-apply-executor-auditor-dry-run-*.json")
    latest_controlled_source_change_real_write_apply_executor_auditor = load_json(latest_controlled_source_change_real_write_apply_executor_auditor_path, {}) if latest_controlled_source_change_real_write_apply_executor_auditor_path else {}

    latest_controlled_source_change_actual_source_write_gate_request_path = latest_report("learning-v2-controlled-source-change-actual-source-write-gate-request-dry-run-*.json")
    latest_controlled_source_change_actual_source_write_gate_request = load_json(latest_controlled_source_change_actual_source_write_gate_request_path, {}) if latest_controlled_source_change_actual_source_write_gate_request_path else {}

    latest_controlled_source_change_actual_source_write_gate_request_auditor_path = latest_report("learning-v2-controlled-source-change-actual-source-write-gate-request-auditor-dry-run-*.json")
    latest_controlled_source_change_actual_source_write_gate_request_auditor = load_json(latest_controlled_source_change_actual_source_write_gate_request_auditor_path, {}) if latest_controlled_source_change_actual_source_write_gate_request_auditor_path else {}

    latest_controlled_source_change_actual_source_write_gate_opener_path = latest_report("learning-v2-controlled-source-change-actual-source-write-gate-opener-dry-run-*.json")
    latest_controlled_source_change_actual_source_write_gate_opener = load_json(latest_controlled_source_change_actual_source_write_gate_opener_path, {}) if latest_controlled_source_change_actual_source_write_gate_opener_path else {}

    latest_controlled_source_change_actual_source_write_gate_opener_auditor_path = latest_report("learning-v2-controlled-source-change-actual-source-write-gate-opener-auditor-dry-run-*.json")
    latest_controlled_source_change_actual_source_write_gate_opener_auditor = load_json(latest_controlled_source_change_actual_source_write_gate_opener_auditor_path, {}) if latest_controlled_source_change_actual_source_write_gate_opener_auditor_path else {}

    latest_controlled_source_change_actual_write_executor_path = latest_report("learning-v2-controlled-source-change-actual-write-executor-dry-run-*.json")
    latest_controlled_source_change_actual_write_executor = load_json(latest_controlled_source_change_actual_write_executor_path, {}) if latest_controlled_source_change_actual_write_executor_path else {}

    latest_controlled_source_change_actual_write_executor_auditor_path = latest_report("learning-v2-controlled-source-change-actual-write-executor-auditor-dry-run-*.json")
    latest_controlled_source_change_actual_write_executor_auditor = load_json(latest_controlled_source_change_actual_write_executor_auditor_path, {}) if latest_controlled_source_change_actual_write_executor_auditor_path else {}

    latest_controlled_source_change_post_write_validation_path = latest_report("learning-v2-controlled-source-change-post-write-validation-dry-run-*.json")
    latest_controlled_source_change_post_write_validation = load_json(latest_controlled_source_change_post_write_validation_path, {}) if latest_controlled_source_change_post_write_validation_path else {}

    latest_controlled_source_change_git_diff_audit_path = latest_report("learning-v2-controlled-source-change-git-diff-audit-dry-run-*.json")
    latest_controlled_source_change_git_diff_audit = load_json(latest_controlled_source_change_git_diff_audit_path, {}) if latest_controlled_source_change_git_diff_audit_path else {}

    latest_visual_evidence_capture_validation_path = latest_report("learning-v2-visual-evidence-capture-validation-dry-run-*.json")
    latest_visual_evidence_capture_validation = load_json(latest_visual_evidence_capture_validation_path, {}) if latest_visual_evidence_capture_validation_path else {}

    latest_browser_visual_capture_path = latest_report("learning-v2-browser-visual-capture-dry-run-*.json")
    latest_browser_visual_capture = load_json(latest_browser_visual_capture_path, {}) if latest_browser_visual_capture_path else {}

    latest_browser_visual_capture_auditor_path = latest_report("learning-v2-browser-visual-capture-auditor-dry-run-*.json")
    latest_browser_visual_capture_auditor = load_json(latest_browser_visual_capture_auditor_path, {}) if latest_browser_visual_capture_auditor_path else {}

    current_topic = state.get("current_topic")
    current_stage = state.get("current_stage")
    current_target_family = state.get("current_target_family")
    manual_review_items = state.get("manual_review_items") or []
    open_manual_review_items = [x for x in manual_review_items if is_open_manual_review_item(x)]
    resolved_manual_review_items = [x for x in manual_review_items if not is_open_manual_review_item(x)]

    approved_proposal_planning_targets = state.get("approved_proposal_planning_targets") or []
    evidence_requested_targets = state.get("evidence_requested_targets") or []
    archived_manual_review_targets = state.get("archived_manual_review_targets") or []

    disabled_target_families = state.get("disabled_target_families") or []

    review_debt = compute_review_debt(open_manual_review_items)
    review_debt_score = review_debt["review_debt_score"]
    review_debt_threshold = review_debt["review_debt_threshold"]

    auto_status = latest_auto.get("discovery_status")
    selected_candidate = latest_auto.get("selected_candidate")
    top_blocked_candidate = latest_auto.get("top_blocked_candidate") or {}

    last_fresh_candidate_count = int(latest_source_discovery.get("fresh_candidate_count") or 0)
    last_pending_task_count = int(latest_source_discovery.get("pending_task_count") or 0)

    triage_counts = Counter(r.get("decision") for r in triage)
    candidate_counts_by_topic = Counter(r.get("topic") for r in candidates)

    allowed_actions = []
    blocked_actions = []
    reasons = []
    recommended_next_action = None
    controller_decision = None
    requires_human_review = False

    if current_topic or current_stage or current_target_family:
        controller_decision = "continue_active_lifecycle"
        recommended_next_action = "run_dispatch_or_current_stage_resolver"
        reasons.append("state has an active lifecycle; do not start new discovery or new candidate selection")
        allowed_actions.append("continue current lifecycle only")
        blocked_actions.extend(["source_discovery", "new_candidate_activation", "website_source_change", "deploy"])

    elif auto_status == "ready_candidate_found" and selected_candidate:
        controller_decision = "run_ready_candidate"
        recommended_next_action = "activate_selected_candidate_then_dispatch"
        reasons.append("autonomous discovery found a ready candidate with existing probe")
        allowed_actions.extend(["selected_candidate_activator_dry_run", "selected_candidate_activator_apply", "dispatch_dry_run", "dispatch_apply"])
        blocked_actions.extend(["source_discovery", "website_source_change", "deploy"])

    elif auto_status == "missing_probe_for_best_candidate" and top_blocked_candidate:
        controller_decision = "scaffold_missing_probe"
        recommended_next_action = "create_observe_only_probe_scaffold_for_best_candidate"
        reasons.append("best candidate exists but its observe-only probe script is missing")
        allowed_actions.append("research_derived_probe_scaffold_generator_apply")
        blocked_actions.extend(["source_discovery", "website_source_change", "deploy"])

    elif approved_proposal_planning_targets:
        latest_plan_approved_count = latest_proposal_planning.get("approved_target_count")
        latest_plan_proposal_count = latest_proposal_planning.get("proposal_count")

        if (
            latest_controlled_source_change_git_diff_audit_path
            and latest_controlled_source_change_git_diff_audit.get("audit_status") == "controlled_source_change_git_diff_audit_ready_for_git_commit_gate_dry_run"
            and latest_controlled_source_change_git_diff_audit.get("git_commit_gate_dry_run_allowed") is True
            and latest_controlled_source_change_git_diff_audit.get("git_commit_allowed") is False
            and latest_controlled_source_change_git_diff_audit.get("actual_source_written") is False
        ):
            controller_decision = "controlled_source_change_git_commit_gate_dry_run_required"
            recommended_next_action = "run_controlled_source_change_git_commit_gate_dry_run"
            requires_human_review = False
            reasons.append(
                "git diff audit dry-run passed; run git commit gate dry-run only"
            )
            allowed_actions.append("controlled_source_change_git_commit_gate_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_post_write_validation_path
            and latest_controlled_source_change_post_write_validation.get("validation_status") == "controlled_source_change_post_write_validation_ready_for_git_diff_audit_dry_run"
            and latest_controlled_source_change_post_write_validation.get("git_diff_audit_dry_run_allowed") is True
            and latest_controlled_source_change_post_write_validation.get("actual_source_written") is False
        ):
            controller_decision = "controlled_source_change_git_diff_audit_dry_run_required"
            recommended_next_action = "run_controlled_source_change_git_diff_audit_dry_run"
            requires_human_review = False
            reasons.append(
                "post-write validation dry-run passed; run git diff audit dry-run only"
            )
            allowed_actions.append("controlled_source_change_git_diff_audit_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_actual_write_executor_auditor_path
            and latest_controlled_source_change_actual_write_executor_auditor.get("audit_status") == "controlled_source_change_actual_write_executor_ready_for_post_write_validation_dry_run"
            and latest_controlled_source_change_actual_write_executor_auditor.get("post_write_validation_dry_run_allowed") is True
            and latest_controlled_source_change_actual_write_executor_auditor.get("actual_source_write_allowed") is False
            and latest_controlled_source_change_actual_write_executor_auditor.get("actual_source_written") is False
        ):
            controller_decision = "controlled_source_change_post_write_validation_dry_run_required"
            recommended_next_action = "run_controlled_source_change_post_write_validation_dry_run"
            requires_human_review = False
            reasons.append(
                "actual write executor audit passed; run post-write validation dry-run only"
            )
            allowed_actions.append("controlled_source_change_post_write_validation_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_actual_write_executor_path
            and latest_controlled_source_change_actual_write_executor.get("executor_status") == "controlled_source_change_actual_write_executor_dry_run_ready_for_audit"
            and latest_controlled_source_change_actual_write_executor.get("actual_write_executor_audit_allowed") is True
            and latest_controlled_source_change_actual_write_executor.get("actual_source_write_allowed") is False
            and latest_controlled_source_change_actual_write_executor.get("actual_source_written") is False
        ):
            controller_decision = "controlled_source_change_actual_write_executor_audit_required"
            recommended_next_action = "run_controlled_source_change_actual_write_executor_auditor_dry_run"
            requires_human_review = False
            reasons.append(
                "actual write executor dry-run is ready; audit before any actual source write can be enabled"
            )
            allowed_actions.append("controlled_source_change_actual_write_executor_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_actual_source_write_gate_opener_auditor_path
            and latest_controlled_source_change_actual_source_write_gate_opener_auditor.get("audit_status") == "controlled_source_change_actual_source_write_gate_opener_ready_for_actual_write_executor_dry_run"
            and latest_controlled_source_change_actual_source_write_gate_opener_auditor.get("actual_write_executor_dry_run_allowed") is True
            and latest_controlled_source_change_actual_source_write_gate_opener_auditor.get("actual_source_write_allowed") is False
            and latest_controlled_source_change_actual_source_write_gate_opener_auditor.get("actual_source_write_gate_opened") is False
        ):
            controller_decision = "controlled_source_change_actual_write_executor_dry_run_required"
            recommended_next_action = "run_controlled_source_change_actual_write_executor_dry_run"
            requires_human_review = False
            reasons.append(
                "actual source-write gate opener audit passed; run actual write executor dry-run only"
            )
            allowed_actions.append("controlled_source_change_actual_write_executor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_actual_source_write_gate_opener_path
            and latest_controlled_source_change_actual_source_write_gate_opener.get("opener_status") == "controlled_source_change_actual_source_write_gate_opener_dry_run_ready_for_audit"
            and latest_controlled_source_change_actual_source_write_gate_opener.get("gate_opener_audit_allowed") is True
            and latest_controlled_source_change_actual_source_write_gate_opener.get("actual_source_write_allowed") is False
            and latest_controlled_source_change_actual_source_write_gate_opener.get("actual_source_write_gate_opened") is False
        ):
            controller_decision = "controlled_source_change_actual_source_write_gate_opener_audit_required"
            recommended_next_action = "run_controlled_source_change_actual_source_write_gate_opener_auditor_dry_run"
            requires_human_review = False
            reasons.append(
                "actual source-write gate opener dry-run is ready; audit before any real gate opening may be enabled"
            )
            allowed_actions.append("controlled_source_change_actual_source_write_gate_opener_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_actual_source_write_gate_request_auditor_path
            and latest_controlled_source_change_actual_source_write_gate_request_auditor.get("audit_status") == "controlled_source_change_actual_source_write_gate_request_ready_for_gate_opener_dry_run"
            and latest_controlled_source_change_actual_source_write_gate_request_auditor.get("gate_opener_dry_run_allowed") is True
            and latest_controlled_source_change_actual_source_write_gate_request_auditor.get("actual_source_write_allowed") is False
            and latest_controlled_source_change_actual_source_write_gate_request_auditor.get("actual_source_write_gate_opened") is False
        ):
            controller_decision = "controlled_source_change_actual_source_write_gate_opener_dry_run_required"
            recommended_next_action = "run_controlled_source_change_actual_source_write_gate_opener_dry_run"
            requires_human_review = False
            reasons.append(
                "actual source-write gate request audit passed; run gate opener dry-run only"
            )
            allowed_actions.append("controlled_source_change_actual_source_write_gate_opener_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_actual_source_write_gate_request_path
            and latest_controlled_source_change_actual_source_write_gate_request.get("request_status") == "controlled_source_change_actual_source_write_gate_request_ready_for_audit"
            and latest_controlled_source_change_actual_source_write_gate_request.get("gate_request_audit_allowed") is True
            and latest_controlled_source_change_actual_source_write_gate_request.get("actual_source_write_allowed") is False
        ):
            controller_decision = "controlled_source_change_actual_source_write_gate_request_audit_required"
            recommended_next_action = "run_controlled_source_change_actual_source_write_gate_request_auditor_dry_run"
            requires_human_review = False
            reasons.append(
                "actual source-write gate request dry-run is ready; audit before any gate opener may run"
            )
            allowed_actions.append("controlled_source_change_actual_source_write_gate_request_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_real_write_apply_executor_auditor_path
            and latest_controlled_source_change_real_write_apply_executor_auditor.get("audit_status") == "controlled_source_change_real_write_apply_executor_ready_for_actual_source_write_gate_request_dry_run"
            and latest_controlled_source_change_real_write_apply_executor_auditor.get("actual_source_write_gate_request_allowed") is True
            and latest_controlled_source_change_real_write_apply_executor_auditor.get("actual_source_write_allowed") is False
        ):
            controller_decision = "controlled_source_change_actual_source_write_gate_request_required"
            recommended_next_action = "run_controlled_source_change_actual_source_write_gate_request_dry_run"
            requires_human_review = False
            reasons.append(
                "controlled real-write apply executor audit passed; prepare actual source-write gate request dry-run"
            )
            allowed_actions.append("controlled_source_change_actual_source_write_gate_request_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_real_write_apply_executor_path
            and latest_controlled_source_change_real_write_apply_executor.get("executor_status") == "controlled_source_change_real_write_apply_executor_dry_run_ready_for_audit"
            and latest_controlled_source_change_real_write_apply_executor.get("apply_executor_audit_allowed") is True
            and latest_controlled_source_change_real_write_apply_executor.get("actual_source_write_allowed") is False
        ):
            controller_decision = "controlled_source_change_real_write_apply_executor_audit_required"
            recommended_next_action = "run_controlled_source_change_real_write_apply_executor_auditor_dry_run"
            requires_human_review = False
            reasons.append(
                "controlled real-write apply executor dry-run is ready; audit before any actual source write can be enabled"
            )
            allowed_actions.append("controlled_source_change_real_write_apply_executor_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_real_write_apply_request_auditor_path
            and latest_controlled_source_change_real_write_apply_request_auditor.get("audit_status") == "controlled_source_change_real_write_apply_request_ready_for_apply_executor_dry_run"
            and latest_controlled_source_change_real_write_apply_request_auditor.get("apply_executor_dry_run_allowed") is True
            and latest_controlled_source_change_real_write_apply_request_auditor.get("actual_source_write_allowed") is False
        ):
            controller_decision = "controlled_source_change_real_write_apply_executor_dry_run_required"
            recommended_next_action = "run_controlled_source_change_real_write_apply_executor_dry_run"
            requires_human_review = False
            reasons.append(
                "controlled real-write apply request audit passed; run apply executor dry-run only"
            )
            allowed_actions.append("controlled_source_change_real_write_apply_executor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_real_write_apply_request_path
            and latest_controlled_source_change_real_write_apply_request.get("request_status") == "controlled_source_change_real_write_apply_request_ready_for_audit"
            and latest_controlled_source_change_real_write_apply_request.get("apply_request_audit_allowed") is True
            and latest_controlled_source_change_real_write_apply_request.get("actual_source_write_allowed") is False
        ):
            controller_decision = "controlled_source_change_real_write_apply_request_audit_required"
            recommended_next_action = "run_controlled_source_change_real_write_apply_request_auditor_dry_run"
            requires_human_review = False
            reasons.append(
                "controlled real-write apply request dry-run is ready; audit it before any source write executor can run"
            )
            allowed_actions.append("controlled_source_change_real_write_apply_request_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_real_write_executor_auditor_path
            and latest_controlled_source_change_real_write_executor_auditor.get("audit_status") == "controlled_source_change_real_write_executor_ready_for_apply_request_dry_run"
            and latest_controlled_source_change_real_write_executor_auditor.get("apply_request_dry_run_allowed") is True
            and latest_controlled_source_change_real_write_executor_auditor.get("actual_source_write_allowed") is False
        ):
            controller_decision = "controlled_source_change_real_write_apply_request_required"
            recommended_next_action = "run_controlled_source_change_real_write_apply_request_dry_run"
            requires_human_review = False
            reasons.append(
                "controlled real-write executor audit passed; prepare apply request dry-run, but do not write source"
            )
            allowed_actions.append("controlled_source_change_real_write_apply_request_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_real_write_executor_path
            and latest_controlled_source_change_real_write_executor.get("executor_status") == "controlled_source_change_real_write_executor_dry_run_ready_for_audit"
            and latest_controlled_source_change_real_write_executor.get("executor_audit_allowed") is True
            and latest_controlled_source_change_real_write_executor.get("deploy_allowed") is False
        ):
            controller_decision = "controlled_source_change_real_write_executor_audit_required"
            recommended_next_action = "run_controlled_source_change_real_write_executor_auditor_dry_run"
            requires_human_review = False
            reasons.append(
                "controlled real-write executor dry-run is ready; audit executor before any real source write can be enabled"
            )
            allowed_actions.append("controlled_source_change_real_write_executor_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_deployment_route_contract_auditor_path
            and latest_deployment_route_contract_auditor.get("audit_status") == "deployment_route_contract_ready_for_real_write_executor_dry_run"
            and latest_deployment_route_contract_auditor.get("real_write_executor_dry_run_allowed") is True
            and latest_deployment_route_contract_auditor.get("deploy_allowed") is False
        ):
            controller_decision = "controlled_source_change_real_write_executor_dry_run_required_after_deployment_route_audit"
            recommended_next_action = "run_controlled_source_change_real_write_executor_dry_run"
            requires_human_review = False
            reasons.append(
                "deployment route contract audit passed; continue to controlled real-write executor dry-run"
            )
            allowed_actions.append("controlled_source_change_real_write_executor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_deployment_route_contract_path
            and latest_deployment_route_contract.get("contract_status") == "deployment_route_contract_ready_for_audit"
            and latest_deployment_route_contract.get("contract_audit_allowed") is True
            and latest_deployment_route_contract.get("deploy_allowed") is False
        ):
            controller_decision = "deployment_route_contract_audit_required"
            recommended_next_action = "run_deployment_route_contract_auditor_dry_run"
            requires_human_review = False
            reasons.append(
                "deployment route contract is ready; audit GitHub-main-to-Cloudflare-Pages route before any real-write executor"
            )
            allowed_actions.append("deployment_route_contract_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_real_write_request_auditor_path
            and latest_controlled_source_change_real_write_request_auditor.get("audit_status") == "controlled_source_change_real_write_request_ready_for_executor_dry_run"
            and latest_controlled_source_change_real_write_request_auditor.get("executor_dry_run_allowed") is True
            and not latest_deployment_route_contract_path
        ):
            controller_decision = "deployment_route_contract_required_before_real_write_executor"
            recommended_next_action = "run_deployment_route_contract_dry_run"
            requires_human_review = False
            reasons.append(
                "real-write executor is blocked until GitHub-main-to-Cloudflare-Pages deployment route contract exists"
            )
            allowed_actions.append("deployment_route_contract_dry_run")
            blocked_actions.extend([
                "controlled_source_change_real_write_executor_dry_run",
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_real_write_request_auditor_path
            and latest_controlled_source_change_real_write_request_auditor.get("audit_status") == "controlled_source_change_real_write_request_ready_for_executor_dry_run"
            and latest_controlled_source_change_real_write_request_auditor.get("executor_dry_run_allowed") is True
            and latest_controlled_source_change_real_write_request_auditor.get("source_change_gate_allowed") is False
        ):
            controller_decision = "controlled_source_change_real_write_executor_dry_run_required"
            recommended_next_action = "run_controlled_source_change_real_write_executor_dry_run"
            requires_human_review = False
            reasons.append(
                "controlled real-write request audit passed; run real-write executor dry-run only"
            )
            allowed_actions.append("controlled_source_change_real_write_executor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_real_write_request_path
            and latest_controlled_source_change_real_write_request.get("request_status") == "controlled_source_change_real_write_request_ready_for_audit"
            and latest_controlled_source_change_real_write_request.get("request_audit_allowed") is True
            and latest_controlled_source_change_real_write_request.get("source_change_gate_allowed") is False
        ):
            controller_decision = "controlled_source_change_real_write_request_audit_required"
            recommended_next_action = "run_controlled_source_change_real_write_request_auditor_dry_run"
            requires_human_review = False
            reasons.append(
                "controlled real-write request dry-run is ready; audit it before any source write executor may run"
            )
            allowed_actions.append("controlled_source_change_real_write_request_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_apply_auditor_path
            and latest_controlled_source_change_apply_auditor.get("audit_status") == "controlled_source_change_apply_ready_for_real_write_request_dry_run"
            and latest_controlled_source_change_apply_auditor.get("real_write_request_dry_run_allowed") is True
            and latest_controlled_source_change_apply_auditor.get("source_change_gate_allowed") is False
        ):
            controller_decision = "controlled_source_change_real_write_request_required"
            recommended_next_action = "run_controlled_source_change_real_write_request_dry_run"
            requires_human_review = False
            reasons.append(
                "controlled source-change apply audit passed; prepare real-write request dry-run, but do not write source"
            )
            allowed_actions.append("controlled_source_change_real_write_request_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_controlled_source_change_apply_path
            and latest_controlled_source_change_apply.get("apply_status") == "controlled_source_change_apply_dry_run_ready_for_audit"
            and latest_controlled_source_change_apply.get("apply_audit_allowed") is True
            and latest_controlled_source_change_apply.get("source_change_gate_allowed") is False
        ):
            controller_decision = "controlled_source_change_apply_audit_required"
            recommended_next_action = "run_controlled_source_change_apply_auditor_dry_run"
            requires_human_review = False
            reasons.append(
                "controlled source-change apply dry-run is ready; audit apply plan before any real source write"
            )
            allowed_actions.append("controlled_source_change_apply_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_source_change_gate_opener_auditor_path
            and latest_source_change_gate_opener_auditor.get("audit_status") == "source_change_gate_opener_ready_for_controlled_apply_dry_run"
            and latest_source_change_gate_opener_auditor.get("controlled_apply_dry_run_allowed") is True
            and latest_source_change_gate_opener_auditor.get("source_change_gate_allowed") is False
        ):
            controller_decision = "controlled_source_change_apply_dry_run_required"
            recommended_next_action = "run_controlled_source_change_apply_dry_run"
            requires_human_review = False
            reasons.append(
                "source-change gate opener audit passed; run controlled source-change apply dry-run only"
            )
            allowed_actions.append("controlled_source_change_apply_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "git_commit",
                "git_push",
                "deploy",
            ])
        elif (
            latest_source_change_gate_opener_path
            and latest_source_change_gate_opener.get("opener_status") == "source_change_gate_opener_dry_run_ready_for_audit"
            and latest_source_change_gate_opener.get("opener_audit_allowed") is True
            and latest_source_change_gate_opener.get("source_change_gate_allowed") is False
        ):
            controller_decision = "source_change_gate_opener_audit_required"
            recommended_next_action = "run_source_change_gate_opener_auditor_dry_run"
            requires_human_review = False
            reasons.append(
                "source-change gate opener dry-run is ready; audit opener before any controlled source-change apply path"
            )
            allowed_actions.append("source_change_gate_opener_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_source_change_gate_open_request_auditor_path
            and latest_source_change_gate_open_request_auditor.get("audit_status") == "source_change_gate_open_request_ready_for_gate_opener_dry_run"
            and latest_source_change_gate_open_request_auditor.get("gate_opener_dry_run_allowed") is True
            and latest_source_change_gate_open_request_auditor.get("source_change_gate_allowed") is False
        ):
            controller_decision = "source_change_gate_opener_dry_run_required"
            recommended_next_action = "run_source_change_gate_opener_dry_run"
            requires_human_review = False
            reasons.append(
                "source-change gate open request audit passed; run gate opener dry-run, but do not write source yet"
            )
            allowed_actions.append("source_change_gate_opener_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_source_change_gate_open_request_path
            and latest_source_change_gate_open_request.get("request_status") == "source_change_gate_open_request_ready_for_audit"
            and latest_source_change_gate_open_request.get("request_audit_allowed") is True
            and latest_source_change_gate_open_request.get("source_change_gate_allowed") is False
        ):
            controller_decision = "source_change_gate_open_request_audit_required"
            recommended_next_action = "run_source_change_gate_open_request_auditor_dry_run"
            requires_human_review = False
            reasons.append(
                "source-change gate open request packet is ready; audit the request before any gate may open"
            )
            allowed_actions.append("source_change_gate_open_request_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_final_source_change_gate_auditor_path
            and latest_final_source_change_gate_auditor.get("audit_status") == "gate_open_candidate_ready_but_not_opened"
            and latest_final_source_change_gate_auditor.get("gate_open_allowed") is False
            and latest_final_source_change_gate_auditor.get("source_change_gate_allowed") is False
        ):
            controller_decision = "source_change_gate_open_request_required"
            recommended_next_action = "run_source_change_gate_open_request_dry_run"
            requires_human_review = False
            reasons.append(
                "final gate auditor recheck passed with visual evidence; prepare gate-open request dry-run, but do not open gate yet"
            )
            allowed_actions.append("source_change_gate_open_request_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_browser_visual_capture_auditor_path
            and latest_browser_visual_capture_auditor.get("audit_status") == "browser_visual_capture_ready_for_final_gate_recheck"
            and latest_browser_visual_capture_auditor.get("final_gate_recheck_allowed") is True
            and latest_browser_visual_capture_auditor.get("source_change_gate_allowed") is False
        ):
            controller_decision = "final_gate_recheck_required_after_visual_evidence"
            recommended_next_action = "rerun_final_source_change_gate_auditor_with_visual_evidence"
            requires_human_review = False
            reasons.append(
                "browser visual evidence audit passed; final source-change gate auditor should recheck with visual evidence confirmed"
            )
            allowed_actions.append("final_source_change_gate_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_browser_visual_capture_path
            and latest_browser_visual_capture.get("capture_status") == "browser_visual_capture_ready_for_audit"
            and latest_browser_visual_capture.get("visual_evidence_audit_allowed") is True
            and latest_browser_visual_capture.get("source_change_gate_allowed") is False
        ):
            controller_decision = "browser_visual_capture_audit_required"
            recommended_next_action = "run_browser_visual_capture_auditor_before_gate"
            requires_human_review = False
            reasons.append(
                "browser visual capture produced required artifacts; audit visual evidence before gate"
            )
            allowed_actions.append("browser_visual_capture_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_browser_visual_capture_path
            and latest_browser_visual_capture.get("capture_status") in ["blocked", "browser_visual_capture_incomplete"]
            and latest_browser_visual_capture.get("source_change_gate_allowed") is False
        ):
            controller_decision = "browser_visual_capture_blocked_before_source_change_gate"
            recommended_next_action = "fix_browser_visual_capture_before_gate"
            requires_human_review = False
            reasons.append(
                "browser visual capture did not complete all required evidence; gate remains closed"
            )
            allowed_actions.append("browser_visual_capture_module_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_visual_evidence_capture_validation_path
            and latest_visual_evidence_capture_validation.get("validation_status") == "browser_visual_capture_module_required"
            and latest_visual_evidence_capture_validation.get("source_change_gate_allowed") is False
        ):
            controller_decision = "browser_visual_capture_module_required_before_source_change_gate"
            recommended_next_action = "build_browser_visual_capture_module_dry_run"
            requires_human_review = False
            reasons.append(
                "visual evidence tooling is available, but browser capture/validation evidence is still pending; gate remains closed"
            )
            allowed_actions.append("browser_visual_capture_module_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_visual_evidence_capture_validation_path
            and latest_visual_evidence_capture_validation.get("validation_status") == "visual_evidence_capture_tooling_required"
            and latest_visual_evidence_capture_validation.get("source_change_gate_allowed") is False
        ):
            controller_decision = "visual_capture_tooling_required_before_source_change_gate"
            recommended_next_action = "install_or_enable_browser_visual_capture_tooling"
            requires_human_review = False
            reasons.append(
                "visual evidence dry-run found browser capture tooling is unavailable; gate remains closed"
            )
            allowed_actions.append("browser_visual_capture_tooling_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_final_source_change_gate_auditor_path
            and latest_final_source_change_gate_auditor.get("audit_status") == "gate_blocked_pending_visual_evidence"
            and latest_final_source_change_gate_auditor.get("source_change_gate_allowed") is False
        ):
            controller_decision = "visual_evidence_required_before_source_change_gate"
            recommended_next_action = "build_visual_evidence_capture_or_validation_dry_run"
            requires_human_review = False
            reasons.append(
                "final gate auditor blocked gate because visual/mobile evidence is still pending"
            )
            allowed_actions.append("visual_evidence_capture_or_validation_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_required_gate_evidence_modules_auditor_path
            and latest_required_gate_evidence_modules_auditor.get("audit_status") == "required_gate_evidence_modules_ready_for_final_gate_auditor"
            and latest_required_gate_evidence_modules_auditor.get("final_gate_auditor_allowed") is True
            and latest_required_gate_evidence_modules_auditor.get("source_change_gate_allowed") is False
        ):
            controller_decision = "final_source_change_gate_auditor_required"
            recommended_next_action = "run_final_source_change_gate_auditor_dry_run"
            requires_human_review = False
            reasons.append(
                "required gate evidence modules auditor passed; final gate auditor may run, but gate remains closed"
            )
            allowed_actions.append("final_source_change_gate_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_required_gate_evidence_modules_path
            and latest_required_gate_evidence_modules.get("modules_status") == "required_gate_evidence_modules_ready_for_audit"
            and latest_required_gate_evidence_modules.get("evidence_modules_audit_allowed") is True
            and latest_required_gate_evidence_modules.get("source_change_gate_allowed") is False
        ):
            controller_decision = "required_gate_evidence_modules_audit_required"
            recommended_next_action = "run_required_gate_evidence_modules_auditor_before_gate"
            requires_human_review = False
            reasons.append(
                "required gate evidence modules exist; audit modules before any source_change_gate can open"
            )
            allowed_actions.append("required_gate_evidence_modules_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_pre_change_evidence_auditor_path
            and latest_pre_change_evidence_auditor.get("audit_status") == "pre_change_evidence_ready_for_required_evidence_modules"
            and latest_pre_change_evidence_auditor.get("required_evidence_modules_allowed") is True
            and latest_pre_change_evidence_auditor.get("source_change_gate_allowed") is False
        ):
            controller_decision = "required_gate_evidence_modules_ready"
            recommended_next_action = "build_required_gate_evidence_modules_dry_run"
            requires_human_review = False
            reasons.append(
                "pre-change evidence auditor passed; required visual/rollback/post-validation evidence modules must be built before gate"
            )
            allowed_actions.append("required_gate_evidence_modules_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_pre_change_evidence_snapshot_path
            and latest_pre_change_evidence_snapshot.get("snapshot_status") == "pre_change_evidence_snapshot_ready_for_audit"
            and latest_pre_change_evidence_snapshot.get("evidence_audit_allowed") is True
            and latest_pre_change_evidence_snapshot.get("source_change_gate_allowed") is False
        ):
            controller_decision = "pre_change_evidence_audit_required"
            recommended_next_action = "run_pre_change_evidence_auditor_before_gate"
            requires_human_review = False
            reasons.append(
                "pre-change evidence snapshot exists; audit evidence before any source_change_gate can open"
            )
            allowed_actions.append("pre_change_evidence_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_source_change_gate_open_policy_path
            and latest_source_change_gate_open_policy.get("policy_decision") == "require_pre_change_evidence_before_gate"
            and latest_source_change_gate_open_policy.get("source_change_gate_allowed") is False
        ):
            controller_decision = "pre_change_evidence_required_before_gate"
            recommended_next_action = "build_pre_change_evidence_snapshot_dry_run"
            requires_human_review = False
            reasons.append(
                "gate open policy requires pre-change evidence before any source_change_gate can open"
            )
            allowed_actions.append("pre_change_evidence_snapshot_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_patch_preview_auditor_path
            and latest_patch_preview_auditor.get("audit_status") == "patch_preview_ready_for_gate_policy_review"
            and latest_patch_preview_auditor.get("gate_policy_review_allowed") is True
            and latest_patch_preview_auditor.get("source_change_gate_allowed") is False
        ):
            controller_decision = "source_change_gate_policy_required"
            recommended_next_action = "run_source_change_gate_open_policy_dry_run"
            requires_human_review = False
            reasons.append(
                "patch preview auditor passed for gate policy review only; source gate and website edits remain blocked"
            )
            allowed_actions.append("source_change_gate_policy_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_file_level_patch_preview_path
            and latest_file_level_patch_preview.get("preview_status") == "patch_preview_ready_for_audit"
            and latest_file_level_patch_preview.get("patch_preview_audit_allowed") is True
            and latest_file_level_patch_preview.get("source_change_gate_allowed") is False
        ):
            controller_decision = "patch_preview_audit_required"
            recommended_next_action = "run_patch_preview_auditor_before_any_source_change_gate"
            requires_human_review = False
            reasons.append(
                "file-level patch preview exists and includes rollback/post-validation; audit it before any gate or website write"
            )
            allowed_actions.append("patch_preview_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_source_change_gate_readiness_path
            and latest_source_change_gate_readiness.get("readiness_status") == "patch_preview_required_before_gate"
            and latest_source_change_gate_readiness.get("source_change_gate_allowed") is False
        ):
            controller_decision = "patch_preview_required_before_gate"
            recommended_next_action = "build_file_level_patch_preview_and_rollback_dry_run"
            requires_human_review = False
            reasons.append(
                "gate readiness found patch preview and rollback are required before any source_change_gate can open"
            )
            allowed_actions.append("patch_preview_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_source_change_plan_auditor_path
            and latest_source_change_plan_auditor.get("audit_status") == "plan_ready_for_gate_review"
            and latest_source_change_plan_auditor.get("gate_review_allowed") is True
            and latest_source_change_plan_auditor.get("source_change_gate_allowed") is False
        ):
            controller_decision = "source_change_gate_review_ready"
            recommended_next_action = "build_source_change_gate_readiness_dry_run"
            requires_human_review = False
            reasons.append(
                "source-change plan auditor passed for gate review only; source gate and website edits remain blocked"
            )
            allowed_actions.append("source_change_gate_readiness_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_source_change_plan_path
            and latest_source_change_plan.get("decision") == "source_change_plan_dry_run_ready"
            and latest_source_change_plan.get("source_change_gate_allowed") is False
        ):
            controller_decision = "source_change_plan_audit_required"
            recommended_next_action = "run_source_change_plan_auditor_before_any_gate_or_website_write"
            requires_human_review = False
            reasons.append(
                "source-change plan dry-run exists; audit it before any gate review or website write"
            )
            allowed_actions.append("source_change_plan_auditor_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_autonomous_review_policy_path
            and latest_autonomous_review_policy.get("source_change_plan_dry_run_allowed") is True
            and latest_autonomous_review_policy.get("source_change_gate_allowed") is False
        ):
            controller_decision = "source_change_plan_dry_run_ready"
            recommended_next_action = "build_source_change_plan_dry_run_for_consolidated_packet"
            requires_human_review = False
            reasons.append(
                "autonomous review policy approved source-change plan dry-run only; source gate and website edits remain blocked"
            )
            allowed_actions.append("source_change_plan_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_consolidated_review_path
            and latest_consolidated_review.get("record_count") == len(approved_proposal_planning_targets)
            and latest_consolidated_review.get("decision") == "consolidated_source_change_review_packet_ready"
        ):
            controller_decision = "autonomous_review_policy_required"
            recommended_next_action = "run_autonomous_review_policy_before_source_change_plan"
            requires_human_review = False
            reasons.append(
                "consolidated source-change review packet exists; run autonomous policy before any source-change plan"
            )
            allowed_actions.append("autonomous_review_policy_dry_run")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        elif (
            latest_proposal_planning_path
            and latest_plan_approved_count == len(approved_proposal_planning_targets)
            and latest_plan_proposal_count == len(approved_proposal_planning_targets)
        ):
            controller_decision = "proposal_review_required"
            recommended_next_action = "human_review_proposal_plans_before_source_change_gate"
            requires_human_review = True
            reasons.append(
                "matching proposal planning packet already exists; human review is required before source_change_gate"
            )
            allowed_actions.append("human_review_proposal_plans")
            blocked_actions.extend([
                "source_discovery",
                "new_candidate_generation",
                "source_change_gate",
                "website_source_change",
                "deploy",
            ])
        else:
            controller_decision = "proposal_planning_ready"
            recommended_next_action = "build_proposal_planning_dry_run_for_approved_targets"
            requires_human_review = False
            reasons.append(
                "human review decisions approved proposal planning targets; source change remains blocked until proposal review"
            )
            allowed_actions.append("proposal_planning_dry_run")
            blocked_actions.extend(["source_discovery", "new_candidate_generation", "website_source_change", "deploy"])

    elif evidence_requested_targets and not approved_proposal_planning_targets:
        controller_decision = "evidence_collection_required"
        recommended_next_action = "collect_requested_evidence_before_more_discovery"
        requires_human_review = True
        reasons.append("manual review requested additional evidence before proposal planning or source discovery")
        allowed_actions.append("collect_requested_evidence")
        blocked_actions.extend(["source_discovery", "new_candidate_generation", "website_source_change", "deploy"])

    elif (
        auto_status == "candidates_exist_but_not_actionable"
        and int(latest_auto.get("ready_candidate_count") or 0) == 0
        and review_debt_score >= review_debt_threshold
    ):
        latest_consolidation_count = latest_manual_consolidation.get("manual_review_count")
        latest_consolidation_score = latest_manual_consolidation.get("review_debt_score")

        if (
            latest_manual_consolidation_path
            and latest_consolidation_count == len(manual_review_items)
            and latest_consolidation_score == review_debt_score
        ):
            controller_decision = "human_review_required_after_consolidation"
            recommended_next_action = "human_review_manual_items_then_decide_source_change_gate_or_archive"
            requires_human_review = True
            reasons.append(
                "review debt score remains above threshold and a matching consolidation report already exists; "
                f"review_debt_score={review_debt_score}, threshold={review_debt_threshold}"
            )
            allowed_actions.append("human_review_manual_items")
            blocked_actions.extend(["source_discovery", "new_candidate_generation", "website_source_change", "deploy"])
        else:
            controller_decision = "manual_review_consolidation_required"
            recommended_next_action = "build_manual_review_consolidation_report_before_more_discovery"
            requires_human_review = True
            reasons.append(
                "review debt score reached threshold while candidate pool has no ready candidate; "
                f"review_debt_score={review_debt_score}, threshold={review_debt_threshold}"
            )
            allowed_actions.append("manual_review_consolidation_dry_run")
            blocked_actions.extend(["source_discovery", "new_candidate_generation", "website_source_change", "deploy"])

    elif auto_status == "candidates_exist_but_not_actionable":
        controller_decision = "candidate_pool_exhausted_or_disabled"
        recommended_next_action = "stop_or_refresh_research_queue_after_human_review"
        reasons.append("candidate pool exists but all actionable items are disabled, completed, or require manual review")
        allowed_actions.append("research_queue_redesign_dry_run")
        blocked_actions.extend(["blind_source_discovery", "website_source_change", "deploy"])

    elif last_pending_task_count > 0 and last_fresh_candidate_count > 0 and len(manual_review_items) < 5:
        controller_decision = "bounded_source_discovery_allowed"
        recommended_next_action = "run_one_bounded_source_discovery_cycle_with_triage_gate"
        reasons.append("source queue still has pending tasks and the last discovery produced fresh candidates")
        allowed_actions.append("one_bounded_source_discovery_cycle")
        blocked_actions.extend(["unbounded_source_discovery_loop", "website_source_change", "deploy"])

    else:
        controller_decision = "pause_for_human_direction"
        recommended_next_action = "pause_and_request_human_review"
        requires_human_review = True
        reasons.append("no active lifecycle, no ready candidate, and no strong reason to continue discovery")
        allowed_actions.append("human_review")
        blocked_actions.extend(["source_discovery", "new_candidate_generation", "website_source_change", "deploy"])

    payload = {
        "generated_at": now_iso(),
        "controller_id": CONTROLLER_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "controller_decision": controller_decision,
        "recommended_next_action": recommended_next_action,
        "requires_human_review": requires_human_review,
        "reasons": reasons,
        "allowed_actions": allowed_actions,
        "blocked_actions": blocked_actions,
        "current_state": {
            "current_topic": current_topic,
            "current_stage": current_stage,
            "current_target_family": current_target_family,
            "next_action": state.get("next_action"),
            "allow_source_changes": state.get("allow_source_changes"),
            "allow_git_commit": state.get("allow_git_commit"),
            "allow_deploy": state.get("allow_deploy"),
        },
        "latest_autonomous_discovery": {
            "path": str(latest_auto_path) if latest_auto_path else None,
            "discovery_status": auto_status,
            "ready_candidate_count": latest_auto.get("ready_candidate_count"),
            "blocked_candidate_count": latest_auto.get("blocked_candidate_count"),
            "selected_candidate_target_family": (selected_candidate or {}).get("target_family") if isinstance(selected_candidate, dict) else None,
            "top_blocked_target_family": top_blocked_candidate.get("target_family"),
            "top_blocked_blockers": top_blocked_candidate.get("blockers"),
        },
        "latest_source_discovery": {
            "path": str(latest_source_discovery_path) if latest_source_discovery_path else None,
            "pending_task_count": last_pending_task_count,
            "fresh_candidate_count": last_fresh_candidate_count,
            "duplicate_candidate_count": latest_source_discovery.get("duplicate_candidate_count"),
        },
        "latest_manual_review_consolidation": {
            "path": str(latest_manual_consolidation_path) if latest_manual_consolidation_path else None,
            "manual_review_count": latest_manual_consolidation.get("manual_review_count"),
            "review_debt_score": latest_manual_consolidation.get("review_debt_score"),
            "decision": latest_manual_consolidation.get("decision"),
        },
        "latest_proposal_planning": {
            "path": str(latest_proposal_planning_path) if latest_proposal_planning_path else None,
            "approved_target_count": latest_proposal_planning.get("approved_target_count"),
            "proposal_count": latest_proposal_planning.get("proposal_count"),
            "decision": latest_proposal_planning.get("decision"),
        },
        "latest_consolidated_review": {
            "path": str(latest_consolidated_review_path) if latest_consolidated_review_path else None,
            "record_count": latest_consolidated_review.get("record_count"),
            "decision": latest_consolidated_review.get("decision"),
            "risk_level": (latest_consolidated_review.get("risk_assessment") or {}).get("risk_level"),
        },
        "latest_autonomous_review_policy": {
            "path": str(latest_autonomous_review_policy_path) if latest_autonomous_review_policy_path else None,
            "policy_decision": latest_autonomous_review_policy.get("policy_decision"),
            "source_change_plan_dry_run_allowed": latest_autonomous_review_policy.get("source_change_plan_dry_run_allowed"),
            "source_change_gate_allowed": latest_autonomous_review_policy.get("source_change_gate_allowed"),
        },
        "latest_source_change_plan": {
            "path": str(latest_source_change_plan_path) if latest_source_change_plan_path else None,
            "decision": latest_source_change_plan.get("decision"),
            "candidate_file_count": latest_source_change_plan.get("candidate_file_count"),
            "missing_file_count": latest_source_change_plan.get("missing_file_count"),
            "source_change_gate_allowed": latest_source_change_plan.get("source_change_gate_allowed"),
        },
        "latest_source_change_plan_auditor": {
            "path": str(latest_source_change_plan_auditor_path) if latest_source_change_plan_auditor_path else None,
            "audit_status": latest_source_change_plan_auditor.get("audit_status"),
            "gate_review_allowed": latest_source_change_plan_auditor.get("gate_review_allowed"),
            "source_change_gate_allowed": latest_source_change_plan_auditor.get("source_change_gate_allowed"),
        },
        "latest_source_change_gate_readiness": {
            "path": str(latest_source_change_gate_readiness_path) if latest_source_change_gate_readiness_path else None,
            "readiness_status": latest_source_change_gate_readiness.get("readiness_status"),
            "recommended_next_action": latest_source_change_gate_readiness.get("recommended_next_action"),
            "gate_open_readiness": latest_source_change_gate_readiness.get("gate_open_readiness"),
            "source_change_gate_allowed": latest_source_change_gate_readiness.get("source_change_gate_allowed"),
        },
        "latest_file_level_patch_preview": {
            "path": str(latest_file_level_patch_preview_path) if latest_file_level_patch_preview_path else None,
            "preview_status": latest_file_level_patch_preview.get("preview_status"),
            "patch_preview_count": latest_file_level_patch_preview.get("patch_preview_count"),
            "patch_preview_audit_allowed": latest_file_level_patch_preview.get("patch_preview_audit_allowed"),
            "source_change_gate_allowed": latest_file_level_patch_preview.get("source_change_gate_allowed"),
        },
        "latest_patch_preview_auditor": {
            "path": str(latest_patch_preview_auditor_path) if latest_patch_preview_auditor_path else None,
            "audit_status": latest_patch_preview_auditor.get("audit_status"),
            "gate_policy_review_allowed": latest_patch_preview_auditor.get("gate_policy_review_allowed"),
            "source_change_gate_allowed": latest_patch_preview_auditor.get("source_change_gate_allowed"),
        },
        "latest_source_change_gate_open_policy": {
            "path": str(latest_source_change_gate_open_policy_path) if latest_source_change_gate_open_policy_path else None,
            "policy_decision": latest_source_change_gate_open_policy.get("policy_decision"),
            "pre_change_evidence_required": latest_source_change_gate_open_policy.get("pre_change_evidence_required"),
            "gate_open_policy_allowed": latest_source_change_gate_open_policy.get("gate_open_policy_allowed"),
            "source_change_gate_allowed": latest_source_change_gate_open_policy.get("source_change_gate_allowed"),
        },
        "latest_pre_change_evidence_snapshot": {
            "path": str(latest_pre_change_evidence_snapshot_path) if latest_pre_change_evidence_snapshot_path else None,
            "snapshot_status": latest_pre_change_evidence_snapshot.get("snapshot_status"),
            "candidate_file_count": latest_pre_change_evidence_snapshot.get("candidate_file_count"),
            "evidence_audit_allowed": latest_pre_change_evidence_snapshot.get("evidence_audit_allowed"),
            "source_change_gate_allowed": latest_pre_change_evidence_snapshot.get("source_change_gate_allowed"),
        },
        "latest_pre_change_evidence_auditor": {
            "path": str(latest_pre_change_evidence_auditor_path) if latest_pre_change_evidence_auditor_path else None,
            "audit_status": latest_pre_change_evidence_auditor.get("audit_status"),
            "required_evidence_modules_allowed": latest_pre_change_evidence_auditor.get("required_evidence_modules_allowed"),
            "source_change_gate_allowed": latest_pre_change_evidence_auditor.get("source_change_gate_allowed"),
        },
        "latest_required_gate_evidence_modules": {
            "path": str(latest_required_gate_evidence_modules_path) if latest_required_gate_evidence_modules_path else None,
            "modules_status": latest_required_gate_evidence_modules.get("modules_status"),
            "built_module_count": latest_required_gate_evidence_modules.get("built_module_count"),
            "evidence_modules_audit_allowed": latest_required_gate_evidence_modules.get("evidence_modules_audit_allowed"),
            "source_change_gate_allowed": latest_required_gate_evidence_modules.get("source_change_gate_allowed"),
        },
        "latest_required_gate_evidence_modules_auditor": {
            "path": str(latest_required_gate_evidence_modules_auditor_path) if latest_required_gate_evidence_modules_auditor_path else None,
            "audit_status": latest_required_gate_evidence_modules_auditor.get("audit_status"),
            "final_gate_auditor_allowed": latest_required_gate_evidence_modules_auditor.get("final_gate_auditor_allowed"),
            "source_change_gate_allowed": latest_required_gate_evidence_modules_auditor.get("source_change_gate_allowed"),
        },
        "latest_final_source_change_gate_auditor": {
            "path": str(latest_final_source_change_gate_auditor_path) if latest_final_source_change_gate_auditor_path else None,
            "audit_status": latest_final_source_change_gate_auditor.get("audit_status"),
            "visual_evidence_confirmed": latest_final_source_change_gate_auditor.get("visual_evidence_confirmed"),
            "visual_evidence_required": latest_final_source_change_gate_auditor.get("visual_evidence_required"),
            "gate_open_allowed": latest_final_source_change_gate_auditor.get("gate_open_allowed"),
            "source_change_gate_allowed": latest_final_source_change_gate_auditor.get("source_change_gate_allowed"),
        },
        "latest_source_change_gate_open_request": {
            "path": str(latest_source_change_gate_open_request_path) if latest_source_change_gate_open_request_path else None,
            "request_status": latest_source_change_gate_open_request.get("request_status"),
            "request_audit_allowed": latest_source_change_gate_open_request.get("request_audit_allowed"),
            "source_change_gate_allowed": latest_source_change_gate_open_request.get("source_change_gate_allowed"),
        },
        "latest_source_change_gate_open_request_auditor": {
            "path": str(latest_source_change_gate_open_request_auditor_path) if latest_source_change_gate_open_request_auditor_path else None,
            "audit_status": latest_source_change_gate_open_request_auditor.get("audit_status"),
            "gate_opener_dry_run_allowed": latest_source_change_gate_open_request_auditor.get("gate_opener_dry_run_allowed"),
            "source_change_gate_allowed": latest_source_change_gate_open_request_auditor.get("source_change_gate_allowed"),
        },
        "latest_source_change_gate_opener": {
            "path": str(latest_source_change_gate_opener_path) if latest_source_change_gate_opener_path else None,
            "opener_status": latest_source_change_gate_opener.get("opener_status"),
            "opener_audit_allowed": latest_source_change_gate_opener.get("opener_audit_allowed"),
            "source_change_gate_allowed": latest_source_change_gate_opener.get("source_change_gate_allowed"),
        },
        "latest_source_change_gate_opener_auditor": {
            "path": str(latest_source_change_gate_opener_auditor_path) if latest_source_change_gate_opener_auditor_path else None,
            "audit_status": latest_source_change_gate_opener_auditor.get("audit_status"),
            "controlled_apply_dry_run_allowed": latest_source_change_gate_opener_auditor.get("controlled_apply_dry_run_allowed"),
            "source_change_gate_allowed": latest_source_change_gate_opener_auditor.get("source_change_gate_allowed"),
        },
        "latest_controlled_source_change_apply": {
            "path": str(latest_controlled_source_change_apply_path) if latest_controlled_source_change_apply_path else None,
            "apply_status": latest_controlled_source_change_apply.get("apply_status"),
            "apply_audit_allowed": latest_controlled_source_change_apply.get("apply_audit_allowed"),
            "source_change_gate_allowed": latest_controlled_source_change_apply.get("source_change_gate_allowed"),
        },
        "latest_controlled_source_change_apply_auditor": {
            "path": str(latest_controlled_source_change_apply_auditor_path) if latest_controlled_source_change_apply_auditor_path else None,
            "audit_status": latest_controlled_source_change_apply_auditor.get("audit_status"),
            "real_write_request_dry_run_allowed": latest_controlled_source_change_apply_auditor.get("real_write_request_dry_run_allowed"),
            "source_change_gate_allowed": latest_controlled_source_change_apply_auditor.get("source_change_gate_allowed"),
        },
        "latest_controlled_source_change_real_write_request": {
            "path": str(latest_controlled_source_change_real_write_request_path) if latest_controlled_source_change_real_write_request_path else None,
            "request_status": latest_controlled_source_change_real_write_request.get("request_status"),
            "request_audit_allowed": latest_controlled_source_change_real_write_request.get("request_audit_allowed"),
            "source_change_gate_allowed": latest_controlled_source_change_real_write_request.get("source_change_gate_allowed"),
        },
        "latest_controlled_source_change_real_write_request_auditor": {
            "path": str(latest_controlled_source_change_real_write_request_auditor_path) if latest_controlled_source_change_real_write_request_auditor_path else None,
            "audit_status": latest_controlled_source_change_real_write_request_auditor.get("audit_status"),
            "executor_dry_run_allowed": latest_controlled_source_change_real_write_request_auditor.get("executor_dry_run_allowed"),
            "source_change_gate_allowed": latest_controlled_source_change_real_write_request_auditor.get("source_change_gate_allowed"),
        },
        "latest_deployment_route_contract": {
            "path": str(latest_deployment_route_contract_path) if latest_deployment_route_contract_path else None,
            "contract_status": latest_deployment_route_contract.get("contract_status"),
            "contract_audit_allowed": latest_deployment_route_contract.get("contract_audit_allowed"),
            "deploy_allowed": latest_deployment_route_contract.get("deploy_allowed"),
        },
        "latest_deployment_route_contract_auditor": {
            "path": str(latest_deployment_route_contract_auditor_path) if latest_deployment_route_contract_auditor_path else None,
            "audit_status": latest_deployment_route_contract_auditor.get("audit_status"),
            "real_write_executor_dry_run_allowed": latest_deployment_route_contract_auditor.get("real_write_executor_dry_run_allowed"),
            "deploy_allowed": latest_deployment_route_contract_auditor.get("deploy_allowed"),
        },
        "latest_controlled_source_change_real_write_executor": {
            "path": str(latest_controlled_source_change_real_write_executor_path) if latest_controlled_source_change_real_write_executor_path else None,
            "executor_status": latest_controlled_source_change_real_write_executor.get("executor_status"),
            "executor_audit_allowed": latest_controlled_source_change_real_write_executor.get("executor_audit_allowed"),
            "deploy_allowed": latest_controlled_source_change_real_write_executor.get("deploy_allowed"),
        },
        "latest_controlled_source_change_real_write_executor_auditor": {
            "path": str(latest_controlled_source_change_real_write_executor_auditor_path) if latest_controlled_source_change_real_write_executor_auditor_path else None,
            "audit_status": latest_controlled_source_change_real_write_executor_auditor.get("audit_status"),
            "apply_request_dry_run_allowed": latest_controlled_source_change_real_write_executor_auditor.get("apply_request_dry_run_allowed"),
            "actual_source_write_allowed": latest_controlled_source_change_real_write_executor_auditor.get("actual_source_write_allowed"),
        },
        "latest_controlled_source_change_real_write_apply_request": {
            "path": str(latest_controlled_source_change_real_write_apply_request_path) if latest_controlled_source_change_real_write_apply_request_path else None,
            "request_status": latest_controlled_source_change_real_write_apply_request.get("request_status"),
            "apply_request_audit_allowed": latest_controlled_source_change_real_write_apply_request.get("apply_request_audit_allowed"),
            "actual_source_write_allowed": latest_controlled_source_change_real_write_apply_request.get("actual_source_write_allowed"),
        },
        "latest_controlled_source_change_real_write_apply_request_auditor": {
            "path": str(latest_controlled_source_change_real_write_apply_request_auditor_path) if latest_controlled_source_change_real_write_apply_request_auditor_path else None,
            "audit_status": latest_controlled_source_change_real_write_apply_request_auditor.get("audit_status"),
            "apply_executor_dry_run_allowed": latest_controlled_source_change_real_write_apply_request_auditor.get("apply_executor_dry_run_allowed"),
            "actual_source_write_allowed": latest_controlled_source_change_real_write_apply_request_auditor.get("actual_source_write_allowed"),
        },
        "latest_controlled_source_change_real_write_apply_executor": {
            "path": str(latest_controlled_source_change_real_write_apply_executor_path) if latest_controlled_source_change_real_write_apply_executor_path else None,
            "executor_status": latest_controlled_source_change_real_write_apply_executor.get("executor_status"),
            "apply_executor_audit_allowed": latest_controlled_source_change_real_write_apply_executor.get("apply_executor_audit_allowed"),
            "actual_source_write_allowed": latest_controlled_source_change_real_write_apply_executor.get("actual_source_write_allowed"),
        },
        "latest_controlled_source_change_real_write_apply_executor_auditor": {
            "path": str(latest_controlled_source_change_real_write_apply_executor_auditor_path) if latest_controlled_source_change_real_write_apply_executor_auditor_path else None,
            "audit_status": latest_controlled_source_change_real_write_apply_executor_auditor.get("audit_status"),
            "actual_source_write_gate_request_allowed": latest_controlled_source_change_real_write_apply_executor_auditor.get("actual_source_write_gate_request_allowed"),
            "actual_source_write_allowed": latest_controlled_source_change_real_write_apply_executor_auditor.get("actual_source_write_allowed"),
        },
        "latest_controlled_source_change_actual_source_write_gate_request": {
            "path": str(latest_controlled_source_change_actual_source_write_gate_request_path) if latest_controlled_source_change_actual_source_write_gate_request_path else None,
            "request_status": latest_controlled_source_change_actual_source_write_gate_request.get("request_status"),
            "gate_request_audit_allowed": latest_controlled_source_change_actual_source_write_gate_request.get("gate_request_audit_allowed"),
            "actual_source_write_allowed": latest_controlled_source_change_actual_source_write_gate_request.get("actual_source_write_allowed"),
        },
        "latest_controlled_source_change_actual_source_write_gate_request_auditor": {
            "path": str(latest_controlled_source_change_actual_source_write_gate_request_auditor_path) if latest_controlled_source_change_actual_source_write_gate_request_auditor_path else None,
            "audit_status": latest_controlled_source_change_actual_source_write_gate_request_auditor.get("audit_status"),
            "gate_opener_dry_run_allowed": latest_controlled_source_change_actual_source_write_gate_request_auditor.get("gate_opener_dry_run_allowed"),
            "actual_source_write_allowed": latest_controlled_source_change_actual_source_write_gate_request_auditor.get("actual_source_write_allowed"),
            "actual_source_write_gate_opened": latest_controlled_source_change_actual_source_write_gate_request_auditor.get("actual_source_write_gate_opened"),
        },
        "latest_controlled_source_change_actual_source_write_gate_opener": {
            "path": str(latest_controlled_source_change_actual_source_write_gate_opener_path) if latest_controlled_source_change_actual_source_write_gate_opener_path else None,
            "opener_status": latest_controlled_source_change_actual_source_write_gate_opener.get("opener_status"),
            "gate_opener_audit_allowed": latest_controlled_source_change_actual_source_write_gate_opener.get("gate_opener_audit_allowed"),
            "actual_source_write_allowed": latest_controlled_source_change_actual_source_write_gate_opener.get("actual_source_write_allowed"),
            "actual_source_write_gate_opened": latest_controlled_source_change_actual_source_write_gate_opener.get("actual_source_write_gate_opened"),
        },
        "latest_controlled_source_change_actual_source_write_gate_opener_auditor": {
            "path": str(latest_controlled_source_change_actual_source_write_gate_opener_auditor_path) if latest_controlled_source_change_actual_source_write_gate_opener_auditor_path else None,
            "audit_status": latest_controlled_source_change_actual_source_write_gate_opener_auditor.get("audit_status"),
            "actual_write_executor_dry_run_allowed": latest_controlled_source_change_actual_source_write_gate_opener_auditor.get("actual_write_executor_dry_run_allowed"),
            "actual_source_write_allowed": latest_controlled_source_change_actual_source_write_gate_opener_auditor.get("actual_source_write_allowed"),
            "actual_source_write_gate_opened": latest_controlled_source_change_actual_source_write_gate_opener_auditor.get("actual_source_write_gate_opened"),
        },
        "latest_controlled_source_change_actual_write_executor": {
            "path": str(latest_controlled_source_change_actual_write_executor_path) if latest_controlled_source_change_actual_write_executor_path else None,
            "executor_status": latest_controlled_source_change_actual_write_executor.get("executor_status"),
            "actual_write_executor_audit_allowed": latest_controlled_source_change_actual_write_executor.get("actual_write_executor_audit_allowed"),
            "actual_source_write_allowed": latest_controlled_source_change_actual_write_executor.get("actual_source_write_allowed"),
            "actual_source_written": latest_controlled_source_change_actual_write_executor.get("actual_source_written"),
        },
        "latest_controlled_source_change_actual_write_executor_auditor": {
            "path": str(latest_controlled_source_change_actual_write_executor_auditor_path) if latest_controlled_source_change_actual_write_executor_auditor_path else None,
            "audit_status": latest_controlled_source_change_actual_write_executor_auditor.get("audit_status"),
            "post_write_validation_dry_run_allowed": latest_controlled_source_change_actual_write_executor_auditor.get("post_write_validation_dry_run_allowed"),
            "actual_source_write_allowed": latest_controlled_source_change_actual_write_executor_auditor.get("actual_source_write_allowed"),
            "actual_source_written": latest_controlled_source_change_actual_write_executor_auditor.get("actual_source_written"),
        },
        "latest_controlled_source_change_post_write_validation": {
            "path": str(latest_controlled_source_change_post_write_validation_path) if latest_controlled_source_change_post_write_validation_path else None,
            "validation_status": latest_controlled_source_change_post_write_validation.get("validation_status"),
            "git_diff_audit_dry_run_allowed": latest_controlled_source_change_post_write_validation.get("git_diff_audit_dry_run_allowed"),
            "actual_source_written": latest_controlled_source_change_post_write_validation.get("actual_source_written"),
        },
        "latest_controlled_source_change_git_diff_audit": {
            "path": str(latest_controlled_source_change_git_diff_audit_path) if latest_controlled_source_change_git_diff_audit_path else None,
            "audit_status": latest_controlled_source_change_git_diff_audit.get("audit_status"),
            "git_commit_gate_dry_run_allowed": latest_controlled_source_change_git_diff_audit.get("git_commit_gate_dry_run_allowed"),
            "git_commit_allowed": latest_controlled_source_change_git_diff_audit.get("git_commit_allowed"),
            "actual_source_written": latest_controlled_source_change_git_diff_audit.get("actual_source_written"),
        },
        "latest_visual_evidence_capture_validation": {
            "path": str(latest_visual_evidence_capture_validation_path) if latest_visual_evidence_capture_validation_path else None,
            "validation_status": latest_visual_evidence_capture_validation.get("validation_status"),
            "visual_tooling_available": latest_visual_evidence_capture_validation.get("visual_tooling_available"),
            "visual_evidence_audit_allowed": latest_visual_evidence_capture_validation.get("visual_evidence_audit_allowed"),
            "source_change_gate_allowed": latest_visual_evidence_capture_validation.get("source_change_gate_allowed"),
        },
        "latest_browser_visual_capture": {
            "path": str(latest_browser_visual_capture_path) if latest_browser_visual_capture_path else None,
            "capture_status": latest_browser_visual_capture.get("capture_status"),
            "captured_count": latest_browser_visual_capture.get("captured_count"),
            "mobile_validated_count": latest_browser_visual_capture.get("mobile_validated_count"),
            "visual_evidence_audit_allowed": latest_browser_visual_capture.get("visual_evidence_audit_allowed"),
            "source_change_gate_allowed": latest_browser_visual_capture.get("source_change_gate_allowed"),
        },
        "latest_browser_visual_capture_auditor": {
            "path": str(latest_browser_visual_capture_auditor_path) if latest_browser_visual_capture_auditor_path else None,
            "audit_status": latest_browser_visual_capture_auditor.get("audit_status"),
            "visual_evidence_confirmed": latest_browser_visual_capture_auditor.get("visual_evidence_confirmed"),
            "final_gate_recheck_allowed": latest_browser_visual_capture_auditor.get("final_gate_recheck_allowed"),
            "source_change_gate_allowed": latest_browser_visual_capture_auditor.get("source_change_gate_allowed"),
        },
        "counts": {
            "manual_review_count": len(manual_review_items),
            "open_manual_review_count": len(open_manual_review_items),
            "resolved_manual_review_count": len(resolved_manual_review_items),
            "approved_proposal_planning_target_count": len(approved_proposal_planning_targets),
            "evidence_requested_target_count": len(evidence_requested_targets),
            "archived_manual_review_target_count": len(archived_manual_review_targets),
            "disabled_target_family_count": len(disabled_target_families),
            "target_family_candidate_count": len(candidates),
            "source_count": len(sources),
            "digest_count": len(digests),
            "pattern_count": len(patterns),
            "discovery_queue_count": len(queue),
            "triage_count": len(triage),
        },
        "review_debt": review_debt,
        "triage_counts": dict(triage_counts),
        "candidate_counts_by_topic": dict(candidate_counts_by_topic),
        "manual_review_items_preview": [
            {
                "item_id": x.get("item_id"),
                "target_family": x.get("target_family"),
                "status": x.get("status"),
                "status_after_decision": x.get("status_after_decision"),
                "human_review_decision_action": x.get("human_review_decision_action"),
                "reason": x.get("reason"),
                "review_recommended_count": x.get("review_recommended_count"),
                "signal_present_count": x.get("signal_present_count"),
            }
            for x in manual_review_items[-10:]
        ],
        "approved_proposal_planning_targets": approved_proposal_planning_targets,
        "evidence_requested_targets": evidence_requested_targets,
        "archived_manual_review_targets": archived_manual_review_targets,
        "safety": {
            "business_source_written": False,
            "website_source_written": False,
            "state_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
    }

    ts = stamp()
    json_path = REPORT_DIR / f"learning-v2-next-cycle-controller-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-next-cycle-controller-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Next Cycle Controller Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- controller_decision: `{controller_decision}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- requires_human_review: `{str(requires_human_review).lower()}`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Reasons")
    md.append("")
    for r in reasons:
        md.append(f"- {r}")
    md.append("")
    md.append("## Allowed Actions")
    md.append("")
    for a in allowed_actions:
        md.append(f"- {a}")
    md.append("")
    md.append("## Blocked Actions")
    md.append("")
    for b in blocked_actions:
        md.append(f"- {b}")
    md.append("")
    md.append("## Current State")
    md.append("")
    for k, v in payload["current_state"].items():
        md.append(f"- {k}: `{v}`")
    md.append("")
    md.append("## Counts")
    md.append("")
    for k, v in payload["counts"].items():
        md.append(f"- {k}: `{v}`")
    md.append("")
    md.append("## Review Debt Score")
    md.append("")
    md.append(f"- review_debt_score: `{review_debt_score}`")
    md.append(f"- review_debt_threshold: `{review_debt_threshold}`")
    for k, v in review_debt["review_debt_by_severity"].items():
        md.append(f"- {k}: `{v}`")
    md.append("")
    md.append("## Latest Autonomous Discovery")
    md.append("")
    for k, v in payload["latest_autonomous_discovery"].items():
        md.append(f"- {k}: `{v}`")
    md.append("")
    md.append("## Manual Review Preview")
    md.append("")
    for item in payload["manual_review_items_preview"]:
        md.append(f"- `{item.get('target_family')}` | review={item.get('review_recommended_count')} | signal={item.get('signal_present_count')} | {item.get('reason')}")
    md.append("")
    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("next_cycle_controller = ok")
    print("mode = dry_run")
    print("controller_decision =", controller_decision)
    print("recommended_next_action =", recommended_next_action)
    print("requires_human_review =", str(requires_human_review).lower())
    print("manual_review_count =", len(manual_review_items))
    print("open_manual_review_count =", len(open_manual_review_items))
    print("resolved_manual_review_count =", len(resolved_manual_review_items))
    print("approved_proposal_planning_target_count =", len(approved_proposal_planning_targets))
    print("evidence_requested_target_count =", len(evidence_requested_targets))
    print("review_debt_score =", review_debt_score)
    print("review_debt_threshold =", review_debt_threshold)
    print("review_debt_by_severity =", json.dumps(review_debt["review_debt_by_severity"], ensure_ascii=False))
    print("target_family_candidate_count =", len(candidates))
    print("triage_counts =", json.dumps(dict(triage_counts), ensure_ascii=False))
    print("latest_autonomous_discovery_status =", auto_status)
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
