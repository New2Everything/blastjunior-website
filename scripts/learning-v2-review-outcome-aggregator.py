#!/usr/bin/env python3
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

AGGREGATOR_ID = "learning-v2-review-outcome-aggregator-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"__load_error__": str(e), "__path__": str(path)}

def recent_review_outcomes(limit=20):
    files = sorted(
        REPORT_DIR.glob("learning-v2-review-outcome-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    rows = []
    for p in files:
        if p.name.startswith("learning-v2-review-outcome-aggregator-"):
            continue
        d = load_json(p)
        d["_path"] = str(p)
        rows.append(d)
        if len(rows) >= limit:
            break
    return rows

def main():
    failures = []
    warnings = []

    rows = recent_review_outcomes(limit=20)

    if not rows:
        failures.append("missing_review_outcome_records")

    valid_rows = []
    for d in rows:
        if d.get("__load_error__"):
            warnings.append(f"review_outcome_load_error:{d.get('_path')}:{d.get('__load_error__')}")
            continue
        if d.get("result") != "ok":
            warnings.append(f"review_outcome_not_ok:{d.get('_path')}:{d.get('result')}")
            continue

        policy = d.get("policy") or {}
        for key in [
            "website_files_changed",
            "git_commit",
            "git_push",
            "deploy",
            "implementation_gate_opened",
            "source_change_gate_opened",
        ]:
            if policy.get(key) is not False:
                failures.append(f"outcome_policy_{key}_not_false:{policy.get(key)}:{d.get('_path')}")

        valid_rows.append(d)

    target_values = sorted(set(d.get("target_family") for d in valid_rows if d.get("target_family")))
    proposal_values = sorted(set(d.get("proposal_id") for d in valid_rows if d.get("proposal_id")))

    target_family = target_values[0] if len(target_values) == 1 else None
    proposal_id = proposal_values[0] if len(proposal_values) == 1 else None

    if len(target_values) > 1:
        failures.append(f"mixed_target_family_values:{target_values}")
    if len(proposal_values) > 1:
        failures.append(f"mixed_proposal_id_values:{proposal_values}")

    decision_counts = Counter(d.get("decision") for d in valid_rows)
    source_counts = Counter(d.get("source") for d in valid_rows)

    accept_count = decision_counts.get("accept", 0)
    reject_count = decision_counts.get("reject", 0)
    revise_count = decision_counts.get("revise", 0)
    pending_count = decision_counts.get("pending", 0)

    non_simulation_accept_count = sum(
        1 for d in valid_rows
        if d.get("decision") == "accept" and d.get("source") in {"human", "auto", "policy"}
    )

    if not valid_rows:
        stable_outcome = "pending"
        confidence = "none"
        next_safe_action = "await_more_review_signal"
    elif reject_count > 0:
        stable_outcome = "reject"
        confidence = "blocking_signal_present"
        next_safe_action = "close_or_rework_design_proposal"
    elif revise_count > 0:
        stable_outcome = "revise"
        confidence = "revision_signal_present"
        next_safe_action = "prepare_design_revision_plan"
    elif non_simulation_accept_count > 0 and accept_count >= 1:
        stable_outcome = "accept"
        confidence = "non_simulation_accept_signal_present"
        next_safe_action = "prepare_implementation_readiness_gate_without_opening_source_change"
    else:
        stable_outcome = "pending"
        confidence = "insufficient_signal"
        next_safe_action = "await_more_review_signal"

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "aggregator_id": AGGREGATOR_ID,
        "result": result,
        "target_family": target_family,
        "proposal_id": proposal_id,
        "records_considered": len(rows),
        "valid_record_count": len(valid_rows),
        "decision_counts": dict(decision_counts),
        "source_counts": dict(source_counts),
        "stable_outcome": stable_outcome,
        "confidence": confidence,
        "next_safe_action": next_safe_action,
        "recent_reports": [d.get("_path") for d in valid_rows],
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "dry_run_only": True,
            "website_files_changed": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
            "implementation_gate_opened": False,
            "source_change_gate_opened": False,
            "deploy_gate_opened": False
        },
    }

    out_json = REPORT_DIR / f"learning-v2-review-outcome-aggregator-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-review-outcome-aggregator-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Review Outcome Aggregator",
        "",
        f"- result: `{result}`",
        f"- target_family: `{target_family}`",
        f"- proposal_id: `{proposal_id}`",
        f"- records_considered: `{len(rows)}`",
        f"- valid_record_count: `{len(valid_rows)}`",
        f"- decision_counts: `{dict(decision_counts)}`",
        f"- source_counts: `{dict(source_counts)}`",
        f"- stable_outcome: `{stable_outcome}`",
        f"- confidence: `{confidence}`",
        f"- next_safe_action: `{next_safe_action}`",
        f"- implementation_gate_opened: `False`",
        f"- source_change_gate_opened: `False`",
        f"- deploy: `False`",
        "",
        "## Failures",
    ]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    lines += ["", "## Warnings"]
    lines += [f"- {x}" for x in warnings] if warnings else ["- none"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("review_outcome_aggregator =", result)
    print("target_family =", target_family)
    print("proposal_id =", proposal_id)
    print("records_considered =", len(rows))
    print("valid_record_count =", len(valid_rows))
    print("decision_counts =", dict(decision_counts))
    print("source_counts =", dict(source_counts))
    print("stable_outcome =", stable_outcome)
    print("confidence =", confidence)
    print("next_safe_action =", next_safe_action)
    print("implementation_gate_opened = false")
    print("source_change_gate_opened = false")
    print("failure_count =", len(failures))
    print("warning_count =", len(warnings))
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("website_files_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if failures:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
