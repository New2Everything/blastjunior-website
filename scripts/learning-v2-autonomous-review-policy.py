#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
STATE = BASE / "state.json"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-autonomous-review-policy-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    if default is None:
        default = {}
    try:
        p = Path(path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_load_error": str(e), "_path": str(path)}
    return default

def latest_report(pattern):
    files = sorted(REPORT_DIR.glob(pattern))
    return files[-1] if files else None

def decide(packet):
    risk = (packet.get("risk_assessment") or {}).get("risk_level")
    recommended = packet.get("recommended_decision") or {}
    safety = packet.get("safety") or {}
    scope = packet.get("proposed_review_scope") or {}

    included_surfaces = scope.get("included_surfaces") or []
    record_count = int(packet.get("record_count") or 0)
    evidence_requested_count = int(packet.get("evidence_requested_target_count") or 0)

    hard_blocks = []
    warnings = []

    if safety.get("website_source_written") is not False:
        hard_blocks.append("packet_safety_does_not_confirm_no_website_write")
    if safety.get("source_change_gate_opened") is not False:
        hard_blocks.append("packet_safety_does_not_confirm_gate_closed")
    if safety.get("deploy") is not False:
        hard_blocks.append("packet_safety_does_not_confirm_no_deploy")
    if recommended.get("source_change_gate_allowed_now") is not False:
        hard_blocks.append("packet_allows_source_change_gate_too_early")
    if record_count <= 0:
        hard_blocks.append("no_records_in_consolidated_packet")

    if "public/index.html" in included_surfaces:
        warnings.append("homepage_surface_in_scope_requires_file_level_plan_and_rollback")
    if "components/nav.html" in included_surfaces:
        warnings.append("navigation_surface_in_scope_requires_mobile_validation")
    if evidence_requested_count > 0:
        warnings.append("some evidence-requested targets are excluded and must remain excluded from this plan")

    if hard_blocks:
        return {
            "policy_decision": "block",
            "recommended_next_action": "fix_packet_or_request_human_review",
            "reason": "Hard safety block present.",
            "hard_blocks": hard_blocks,
            "warnings": warnings,
            "source_change_plan_dry_run_allowed": False,
            "source_change_gate_allowed": False,
        }

    if risk in ("low", "medium"):
        return {
            "policy_decision": "approve_source_change_plan_dry_run_only",
            "recommended_next_action": "build_source_change_plan_dry_run_for_consolidated_packet",
            "reason": (
                "Risk is acceptable for planning only. The system may prepare a source-change plan dry-run, "
                "but source_change_gate, website edits, git commit of business source, push, and deploy remain blocked."
            ),
            "hard_blocks": hard_blocks,
            "warnings": warnings,
            "source_change_plan_dry_run_allowed": True,
            "source_change_gate_allowed": False,
        }

    return {
        "policy_decision": "request_more_evidence",
        "recommended_next_action": "collect_more_evidence_before_source_change_plan",
        "reason": "Risk is above policy threshold for autonomous plan approval.",
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "source_change_plan_dry_run_allowed": False,
        "source_change_gate_allowed": False,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is report-only.")
    args = ap.parse_args()

    packet_path = latest_report("learning-v2-consolidated-source-change-review-packet-dry-run-*.json")
    if not packet_path:
        raise SystemExit("no consolidated source-change review packet found")

    packet = load_json(packet_path, {})
    policy = decide(packet)

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "consolidated_packet_source": str(packet_path),
        "packet_decision": packet.get("decision"),
        "packet_record_count": packet.get("record_count"),
        "packet_risk_level": (packet.get("risk_assessment") or {}).get("risk_level"),
        "policy_decision": policy["policy_decision"],
        "recommended_next_action": policy["recommended_next_action"],
        "decision_reason": policy["reason"],
        "hard_blocks": policy["hard_blocks"],
        "warnings": policy["warnings"],
        "source_change_plan_dry_run_allowed": policy["source_change_plan_dry_run_allowed"],
        "source_change_gate_allowed": policy["source_change_gate_allowed"],
        "safety": {
            "state_written": False,
            "business_source_written": False,
            "website_source_written": False,
            "source_change_gate_opened": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
    }

    ts = stamp()
    json_path = REPORT_DIR / f"learning-v2-autonomous-review-policy-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-autonomous-review-policy-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Autonomous Review Policy Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- policy_decision: `{payload['policy_decision']}`")
    md.append(f"- recommended_next_action: `{payload['recommended_next_action']}`")
    md.append(f"- source_change_plan_dry_run_allowed: `{str(payload['source_change_plan_dry_run_allowed']).lower()}`")
    md.append(f"- source_change_gate_allowed: `{str(payload['source_change_gate_allowed']).lower()}`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Decision Reason")
    md.append("")
    md.append(payload["decision_reason"])
    md.append("")
    md.append("## Warnings")
    md.append("")
    for w in payload["warnings"]:
        md.append(f"- {w}")
    if not payload["warnings"]:
        md.append("- none")
    md.append("")
    md.append("## Hard Blocks")
    md.append("")
    for b in payload["hard_blocks"]:
        md.append(f"- {b}")
    if not payload["hard_blocks"]:
        md.append("- none")
    md.append("")
    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("autonomous_review_policy = ok")
    print("mode = dry_run")
    print("consolidated_packet_source =", packet_path)
    print("packet_risk_level =", payload["packet_risk_level"])
    print("policy_decision =", payload["policy_decision"])
    print("recommended_next_action =", payload["recommended_next_action"])
    print("source_change_plan_dry_run_allowed =", str(payload["source_change_plan_dry_run_allowed"]).lower())
    print("source_change_gate_allowed =", str(payload["source_change_gate_allowed"]).lower())
    print("hard_blocks =", json.dumps(payload["hard_blocks"], ensure_ascii=False))
    print("warnings =", json.dumps(payload["warnings"], ensure_ascii=False))
    print("state_written = false")
    print("business_source_written = false")
    print("website_source_written = false")
    print("source_change_gate_opened = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("report_json =", json_path)
    print("report_md =", md_path)

if __name__ == "__main__":
    raise SystemExit(main())
