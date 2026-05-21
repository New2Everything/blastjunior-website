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

SCRIPT_ID = "learning-v2-source-change-gate-open-policy-v0"

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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is report-only and never opens source_change_gate.")
    args = ap.parse_args()

    auditor_path = latest_report("learning-v2-patch-preview-auditor-dry-run-*.json")
    readiness_path = latest_report("learning-v2-source-change-gate-readiness-dry-run-*.json")
    preview_path = latest_report("learning-v2-file-level-patch-preview-dry-run-*.json")

    if not auditor_path:
        raise SystemExit("no patch preview auditor report found")
    if not readiness_path:
        raise SystemExit("no source-change gate readiness report found")
    if not preview_path:
        raise SystemExit("no file-level patch preview report found")

    auditor = load_json(auditor_path, {})
    readiness = load_json(readiness_path, {})
    preview = load_json(preview_path, {})

    hard_blocks = []
    warnings = []

    if auditor.get("audit_status") != "patch_preview_ready_for_gate_policy_review":
        hard_blocks.append("patch_preview_auditor_not_ready_for_gate_policy")
    if auditor.get("gate_policy_review_allowed") is not True:
        hard_blocks.append("gate_policy_review_not_allowed")
    if auditor.get("source_change_gate_allowed") is not False:
        hard_blocks.append("auditor_allows_source_change_gate_too_early")
    if auditor.get("source_change_gate_opened") is not False:
        hard_blocks.append("auditor_opened_source_change_gate")
    if auditor.get("hard_blocks"):
        hard_blocks.append("patch_preview_auditor_has_hard_blocks")

    if readiness.get("readiness_status") != "patch_preview_required_before_gate":
        warnings.append("gate_readiness_status_unexpected_or_already_changed")
    if readiness.get("source_change_gate_allowed") is not False:
        hard_blocks.append("readiness_allows_source_change_gate_too_early")
    if readiness.get("source_change_gate_opened") is not False:
        hard_blocks.append("readiness_opened_source_change_gate")

    if preview.get("preview_status") != "patch_preview_ready_for_audit":
        hard_blocks.append("patch_preview_status_not_ready")
    if preview.get("source_change_gate_allowed") is not False:
        hard_blocks.append("preview_allows_source_change_gate_too_early")
    if preview.get("source_change_gate_opened") is not False:
        hard_blocks.append("preview_opened_source_change_gate")

    safety = preview.get("safety") or {}
    if safety.get("website_source_written") is not False:
        hard_blocks.append("preview_safety_does_not_confirm_no_website_write")
    if safety.get("deploy") is not False:
        hard_blocks.append("preview_safety_does_not_confirm_no_deploy")

    patch_warnings = list(auditor.get("warnings") or [])
    warnings.extend(patch_warnings)

    patches = preview.get("patch_previews") or []
    sensitive_files = []
    medium_or_higher_files = []

    for p in patches:
        path = p.get("path")
        risk = p.get("risk")
        if path in ("public/index.html", "components/nav.html"):
            sensitive_files.append(path)
        if risk in ("medium", "medium-high", "high"):
            medium_or_higher_files.append(path)

    required_before_gate_open = []

    if sensitive_files:
        required_before_gate_open.append("pre_change_screenshot_or_snapshot_required")
        required_before_gate_open.append("mobile_validation_required_for_sensitive_surfaces")

    if medium_or_higher_files:
        required_before_gate_open.append("explicit_rollback_packet_required")
        required_before_gate_open.append("post_validation_command_plan_required")

    required_before_gate_open.append("explicit_source_change_gate_open_policy_required")

    # v0 policy is intentionally conservative:
    # it never opens the gate; it decides whether the next autonomous step is evidence/snapshot.
    if hard_blocks:
        policy_decision = "block_gate_policy"
        recommended_next_action = "fix_gate_policy_inputs_before_any_gate"
        gate_open_policy_allowed = False
        pre_change_evidence_required = False
    elif required_before_gate_open:
        policy_decision = "require_pre_change_evidence_before_gate"
        recommended_next_action = "build_pre_change_evidence_snapshot_dry_run"
        gate_open_policy_allowed = False
        pre_change_evidence_required = True
    else:
        policy_decision = "gate_open_candidate_ready_but_not_opened"
        recommended_next_action = "run_final_gate_open_auditor_dry_run"
        gate_open_policy_allowed = False
        pre_change_evidence_required = False

    by_risk = Counter(p.get("risk") for p in patches)

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "patch_preview_auditor_source": str(auditor_path),
        "gate_readiness_source": str(readiness_path),
        "patch_preview_source": str(preview_path),
        "policy_decision": policy_decision,
        "recommended_next_action": recommended_next_action,
        "patch_preview_count": len(patches),
        "by_risk": dict(by_risk),
        "sensitive_files": sorted(set(sensitive_files)),
        "medium_or_higher_files": sorted(set(medium_or_higher_files)),
        "required_before_gate_open": sorted(set(required_before_gate_open)),
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "pre_change_evidence_required": pre_change_evidence_required,
        "gate_open_policy_allowed": gate_open_policy_allowed,
        "source_change_gate_allowed": False,
        "source_change_gate_opened": False,
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
    json_path = REPORT_DIR / f"learning-v2-source-change-gate-open-policy-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-source-change-gate-open-policy-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Source-Change Gate Open Policy Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- policy_decision: `{policy_decision}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- source_change_gate_opened: `false`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Required Before Gate Open")
    md.append("")
    for x in payload["required_before_gate_open"]:
        md.append(f"- {x}")
    if not payload["required_before_gate_open"]:
        md.append("- none")
    md.append("")
    md.append("## Sensitive Files")
    md.append("")
    for x in payload["sensitive_files"]:
        md.append(f"- `{x}`")
    if not payload["sensitive_files"]:
        md.append("- none")
    md.append("")
    md.append("## Hard Blocks")
    md.append("")
    if hard_blocks:
        for x in hard_blocks:
            md.append(f"- {x}")
    else:
        md.append("- none")
    md.append("")
    md.append("## Warnings")
    md.append("")
    if warnings:
        for x in warnings:
            md.append(f"- {x}")
    else:
        md.append("- none")
    md.append("")
    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("source_change_gate_open_policy = ok")
    print("mode = dry_run")
    print("policy_decision =", policy_decision)
    print("recommended_next_action =", recommended_next_action)
    print("patch_preview_count =", len(patches))
    print("sensitive_files =", json.dumps(sorted(set(sensitive_files)), ensure_ascii=False))
    print("required_before_gate_open =", json.dumps(payload["required_before_gate_open"], ensure_ascii=False))
    print("pre_change_evidence_required =", str(pre_change_evidence_required).lower())
    print("gate_open_policy_allowed =", str(gate_open_policy_allowed).lower())
    print("source_change_gate_allowed = false")
    print("source_change_gate_opened = false")
    print("hard_blocks =", json.dumps(hard_blocks, ensure_ascii=False))
    print("warnings =", json.dumps(warnings, ensure_ascii=False))
    print("state_written = false")
    print("business_source_written = false")
    print("website_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("report_json =", json_path)
    print("report_md =", md_path)

if __name__ == "__main__":
    raise SystemExit(main())
