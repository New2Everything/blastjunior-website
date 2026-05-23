#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-visual-evidence-capture-validation-v0"

TARGETS = [
    {
        "name": "homepage_desktop",
        "path": "public/index.html",
        "viewport": "desktop",
        "required": True,
    },
    {
        "name": "homepage_mobile",
        "path": "public/index.html",
        "viewport": "mobile",
        "required": True,
    },
    {
        "name": "nav_mobile",
        "path": "components/nav.html",
        "viewport": "mobile",
        "required": True,
    },
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def latest_report(pattern):
    files = sorted(REPORT_DIR.glob(pattern))
    return files[-1] if files else None

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

def run_cmd(args):
    p = subprocess.run(
        args,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return {
        "args": args,
        "returncode": p.returncode,
        "output": p.stdout.strip(),
    }

def command_exists(name):
    return shutil.which(name) is not None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is report-only and never changes website source.")
    args = ap.parse_args()

    final_gate_path = latest_report("learning-v2-final-source-change-gate-auditor-dry-run-*.json")
    if not final_gate_path:
        raise SystemExit("no final source-change gate auditor report found")

    final_gate = load_json(final_gate_path, {})

    visual_evidence_already_completed = (
        final_gate.get("audit_status") == "gate_open_candidate_ready_but_not_opened"
        and int(final_gate.get("visual_evidence_task_count") or 0) > 0
        and int(final_gate.get("visual_evidence_completion_count") or 0) > 0
        and not (final_gate.get("pending_required_evidence") or [])
        and final_gate.get("source_change_gate_allowed") is False
        and final_gate.get("source_change_gate_opened") is False
    )

    hard_blocks = []
    warnings = []

    if not visual_evidence_already_completed:
        if final_gate.get("audit_status") != "gate_blocked_pending_visual_evidence":
            hard_blocks.append("final_gate_auditor_not_waiting_for_visual_evidence")
        if final_gate.get("visual_evidence_required") is not True:
            hard_blocks.append("visual_evidence_not_required_by_final_gate")
        if final_gate.get("source_change_gate_allowed") is not False:
            hard_blocks.append("final_gate_allows_source_change_gate_too_early")
        if final_gate.get("gate_open_allowed") is not False:
            hard_blocks.append("final_gate_open_allowed_too_early")

    tooling = {
        "node": command_exists("node"),
        "npm": command_exists("npm"),
        "npx": command_exists("npx"),
        "python3": command_exists("python3"),
    }

    # We do not install anything here. We only detect whether screenshot tooling is likely available.
    playwright_check = None
    if tooling["npx"]:
        playwright_check = run_cmd(["npx", "playwright", "--version"])
    else:
        playwright_check = {
            "args": ["npx", "playwright", "--version"],
            "returncode": 127,
            "output": "npx not found",
        }

    visual_tooling_available = (
        tooling["node"]
        and tooling["npx"]
        and playwright_check.get("returncode") == 0
    )

    target_results = []
    for t in TARGETS:
        p = WORKSPACE / t["path"]
        target_results.append({
            "name": t["name"],
            "path": t["path"],
            "viewport": t["viewport"],
            "required": t["required"],
            "source_exists": p.exists(),
            "actual_visual_captured": False,
            "actual_mobile_validated": False,
            "capture_method": None,
            "capture_artifact": None,
            "validation_notes": [
                "dry-run only",
                "no website source write",
                "no source_change_gate open",
            ],
        })
        if not p.exists():
            hard_blocks.append(f"{t['path']}:target_source_missing")

    pending_visual_evidence = []
    for r in target_results:
        if r["required"] and not r["actual_visual_captured"]:
            pending_visual_evidence.append(f"{r['name']}:visual_capture_pending")
        if r["viewport"] == "mobile" and not r["actual_mobile_validated"]:
            pending_visual_evidence.append(f"{r['name']}:mobile_validation_pending")

    if visual_evidence_already_completed:
        pending_visual_evidence = []

    if not visual_tooling_available and not visual_evidence_already_completed:
        warnings.append("visual_capture_tooling_not_available_or_not_confirmed")
        warnings.append("playwright_or_equivalent_browser_capture_needed_before_gate")

    if visual_evidence_already_completed:
        validation_status = "visual_evidence_already_completed"
        recommended_next_action = "continue_final_gate_or_next_controller_step"
        visual_evidence_audit_allowed = False
    elif hard_blocks:
        validation_status = "blocked"
        recommended_next_action = "fix_visual_evidence_inputs_before_gate"
        visual_evidence_audit_allowed = False
    elif pending_visual_evidence:
        if visual_tooling_available:
            validation_status = "browser_visual_capture_module_required"
            recommended_next_action = "build_browser_visual_capture_module_dry_run"
        else:
            validation_status = "visual_evidence_capture_tooling_required"
            recommended_next_action = "install_or_enable_browser_visual_capture_tooling"
        visual_evidence_audit_allowed = False
    else:
        validation_status = "visual_evidence_ready_for_audit"
        recommended_next_action = "run_visual_evidence_auditor_before_source_change_gate"
        visual_evidence_audit_allowed = True

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "final_gate_auditor_source": str(final_gate_path),
        "visual_evidence_already_completed": visual_evidence_already_completed,
        "completed_visual_task_ids": final_gate.get("completed_visual_task_ids") or [],
        "completed_visual_target_families": final_gate.get("completed_visual_target_families") or [],
        "validation_status": validation_status,
        "recommended_next_action": recommended_next_action,
        "tooling": tooling,
        "playwright_check": playwright_check,
        "visual_tooling_available": visual_tooling_available,
        "target_count": len(target_results),
        "target_results": target_results,
        "pending_visual_evidence": sorted(set(pending_visual_evidence)),
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "visual_evidence_audit_allowed": visual_evidence_audit_allowed,
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
    json_path = REPORT_DIR / f"learning-v2-visual-evidence-capture-validation-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-visual-evidence-capture-validation-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Visual Evidence Capture / Validation Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- validation_status: `{validation_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- visual_tooling_available: `{str(visual_tooling_available).lower()}`")
    md.append(f"- visual_evidence_audit_allowed: `{str(visual_evidence_audit_allowed).lower()}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- source_change_gate_opened: `false`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Targets")
    md.append("")
    for r in target_results:
        md.append(f"### {r['name']}")
        md.append(f"- path: `{r['path']}`")
        md.append(f"- viewport: `{r['viewport']}`")
        md.append(f"- source_exists: `{str(r['source_exists']).lower()}`")
        md.append(f"- actual_visual_captured: `{str(r['actual_visual_captured']).lower()}`")
        md.append(f"- actual_mobile_validated: `{str(r['actual_mobile_validated']).lower()}`")
        md.append("")
    md.append("## Pending Visual Evidence")
    md.append("")
    if payload["pending_visual_evidence"]:
        for x in payload["pending_visual_evidence"]:
            md.append(f"- {x}")
    else:
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

    print("visual_evidence_capture_validation = ok")
    print("mode = dry_run")
    print("validation_status =", validation_status)
    print("recommended_next_action =", recommended_next_action)
    print("visual_tooling_available =", str(visual_tooling_available).lower())
    print("visual_evidence_audit_allowed =", str(visual_evidence_audit_allowed).lower())
    print("target_count =", len(target_results))
    print("pending_visual_evidence =", json.dumps(payload["pending_visual_evidence"], ensure_ascii=False))
    print("hard_blocks =", json.dumps(hard_blocks, ensure_ascii=False))
    print("warnings =", json.dumps(warnings, ensure_ascii=False))
    print("source_change_gate_allowed = false")
    print("source_change_gate_opened = false")
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
