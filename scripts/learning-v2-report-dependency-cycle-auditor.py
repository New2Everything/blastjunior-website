#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
SCRIPTS_DIR = WORKSPACE / "scripts"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

AUDITOR_ID = "learning-v2-report-dependency-cycle-auditor-v0"

FAST_STATUS = SCRIPTS_DIR / "learning-v2-fast-status.py"

KNOWN_ALLOWED_CYCLE_SCRIPTS = {
    # Existing auditors intentionally compare their own chain against fast-status.
    # They remain allowed for now, but still reported as known cycles.
    "learning-v2-source-change-guard-chain-auditor.py",
    "learning-v2-accept-transition-contract-auditor.py",
}

HIGH_RISK_NO_CYCLE_SCRIPTS = {
    # These scripts are read by fast-status, but are safe only if their default mode does not call fast-status.
    "learning-v2-accept-planning-readiness-bridge.py",
    "learning-v2-accept-transition-simulator.py",
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        return f"__READ_ERROR__:{e}"

def report_prefix_for_script(script_name):
    return script_name[:-3] + "-"

def script_calls_fast_status(text):
    markers = [
        '["python3", "scripts/learning-v2-fast-status.py"]',
        "run_fast_status()",
    ]
    return any(marker in text for marker in markers)

def script_default_skip_ok(text):
    markers = [
        'LEARNING_V2_BRIDGE_FAST_STATUS_MODE", "skip"',
        "LEARNING_V2_BRIDGE_FAST_STATUS_MODE', 'skip'",
        'LEARNING_V2_SIMULATOR_FAST_STATUS_MODE", "skip"',
        "LEARNING_V2_SIMULATOR_FAST_STATUS_MODE', 'skip'",
    ]
    return any(marker in text for marker in markers)

def fast_status_reads_report_prefix(fast_text, prefix):
    patterns = [
        prefix + "*.json",
        prefix,
    ]
    return any(p in fast_text for p in patterns)

def extract_fast_status_report_patterns(fast_text):
    patterns = []
    for m in re.finditer(r'latest_json\("([^"]+)"\)', fast_text):
        patterns.append(m.group(1))
    return patterns

def main():
    failures = []
    warnings = []
    detected_cycles = []
    allowed_cycles = []
    high_risk_checks = []

    fast_text = read_text(FAST_STATUS)
    if fast_text.startswith("__READ_ERROR__"):
        failures.append(f"fast_status_read_error:{fast_text}")
        fast_patterns = []
    else:
        fast_patterns = extract_fast_status_report_patterns(fast_text)

    for script_path in sorted(SCRIPTS_DIR.glob("learning-v2-*.py")):
        script_name = script_path.name

        if script_name in {"learning-v2-fast-status.py", "learning-v2-report-dependency-cycle-auditor.py"}:
            continue

        text = read_text(script_path)
        if text.startswith("__READ_ERROR__"):
            warnings.append(f"script_read_error:{script_name}:{text}")
            continue

        calls_fast = script_calls_fast_status(text)
        prefix = report_prefix_for_script(script_name)
        read_by_fast = fast_status_reads_report_prefix(fast_text, prefix)
        default_skip_ok = script_default_skip_ok(text)

        if calls_fast and read_by_fast:
            item = {
                "script": script_name,
                "report_prefix": prefix,
                "calls_fast_status": True,
                "read_by_fast_status": True,
                "cycle_type": "fast_status_report_cycle",
            }

            if script_name in KNOWN_ALLOWED_CYCLE_SCRIPTS:
                item["severity"] = "known_allowed"
                allowed_cycles.append(item)
            elif script_name in HIGH_RISK_NO_CYCLE_SCRIPTS and default_skip_ok:
                item["severity"] = "default_skip_safe"
                allowed_cycles.append(item)
            else:
                item["severity"] = "blocked"
                detected_cycles.append(item)
                failures.append(f"unapproved_fast_status_report_cycle:{script_name}")

        if script_name in HIGH_RISK_NO_CYCLE_SCRIPTS:
            default_skip_ok = script_default_skip_ok(text)
            reads_by_fast = read_by_fast
            high_risk = {
                "script": script_name,
                "default_skip_ok": default_skip_ok,
                "read_by_fast_status": reads_by_fast,
                "calls_fast_status_marker_present": calls_fast,
            }
            high_risk_checks.append(high_risk)

            if not default_skip_ok:
                failures.append(f"high_risk_script_default_skip_missing:{script_name}")
            if reads_by_fast and not default_skip_ok:
                failures.append(f"high_risk_script_read_by_fast_status_without_default_skip:{script_name}")

    status = "ok"
    audit_status = "no_unapproved_report_cycles"

    if detected_cycles:
        status = "blocked"
        audit_status = "unapproved_report_cycles_detected"
    elif allowed_cycles:
        audit_status = "only_known_allowed_cycles_detected"

    payload = {
        "generated_at": now_iso(),
        "auditor_id": AUDITOR_ID,
        "result": status,
        "audit_status": audit_status,
        "fast_status_script": str(FAST_STATUS),
        "fast_status_report_patterns": fast_patterns,
        "detected_cycle_count": len(detected_cycles),
        "allowed_cycle_count": len(allowed_cycles),
        "high_risk_check_count": len(high_risk_checks),
        "detected_cycles": detected_cycles,
        "allowed_cycles": allowed_cycles,
        "high_risk_checks": high_risk_checks,
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "dry_run_only": True,
            "website_files_changed": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
            "source_change_gate_opened": False,
            "deploy_gate_opened": False,
        },
    }

    out_json = REPORT_DIR / f"learning-v2-report-dependency-cycle-auditor-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-report-dependency-cycle-auditor-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Report Dependency Cycle Auditor",
        "",
        f"- result: `{status}`",
        f"- audit_status: `{audit_status}`",
        f"- detected_cycle_count: `{len(detected_cycles)}`",
        f"- allowed_cycle_count: `{len(allowed_cycles)}`",
        f"- high_risk_check_count: `{len(high_risk_checks)}`",
        "",
        "## Detected Cycles",
    ]
    lines += [f"- {x['script']} ({x['severity']})" for x in detected_cycles] if detected_cycles else ["- none"]
    lines += ["", "## Known Allowed Cycles"]
    lines += [f"- {x['script']} ({x['severity']})" for x in allowed_cycles] if allowed_cycles else ["- none"]
    lines += ["", "## High Risk Checks"]
    lines += [
        f"- {x['script']}: default_skip_ok={x['default_skip_ok']}, read_by_fast_status={x['read_by_fast_status']}, calls_fast_status_marker_present={x['calls_fast_status_marker_present']}"
        for x in high_risk_checks
    ] if high_risk_checks else ["- none"]
    lines += ["", "## Failures"]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    lines += ["", "## Warnings"]
    lines += [f"- {x}" for x in warnings] if warnings else ["- none"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("report_dependency_cycle_auditor =", status)
    print("audit_status =", audit_status)
    print("detected_cycle_count =", len(detected_cycles))
    print("allowed_cycle_count =", len(allowed_cycles))
    print("high_risk_check_count =", len(high_risk_checks))
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
