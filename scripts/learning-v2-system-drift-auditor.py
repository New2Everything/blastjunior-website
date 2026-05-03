#!/usr/bin/env python3
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

BUSINESS_PREFIXES = (
    "public/",
    "components/",
    "assets/",
    "src/",
    "functions/",
    "workers/",
)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def run(cmd):
    p = subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "cmd": cmd,
        "returncode": p.returncode,
        "stdout": p.stdout.strip(),
        "stderr": p.stderr.strip(),
        "ok": p.returncode == 0,
    }

def load_json(path, default=None):
    if not path:
        return default
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def sha256_file(path):
    p = WORKSPACE / path
    if not p.exists() or not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def parse_git_status_z(raw):
    if not raw:
        return []
    parts = raw.split("\0")
    rows = []
    i = 0
    while i < len(parts):
        item = parts[i]
        if not item:
            i += 1
            continue
        code = item[:2]
        path = item[3:] if len(item) > 3 else ""
        if code.strip().startswith(("R", "C")) and i + 1 < len(parts):
            old_path = parts[i + 1]
            rows.append({"code": code, "path": path, "old_path": old_path})
            i += 2
        else:
            rows.append({"code": code, "path": path})
            i += 1
    return rows

def classify_dirty(path):
    if path.startswith(BUSINESS_PREFIXES):
        return "business_source_blocked"
    if path.startswith(("scripts/", "learning-v2/", ".git/info/exclude")):
        return "system_engineering"
    return "other_existing_dirty"

def current_learning_v2_scripts():
    return sorted(
        str(p.relative_to(WORKSPACE))
        for p in (WORKSPACE / "scripts").glob("learning-v2-*.py")
        if p.is_file()
    )

def main():
    state = load_json(STATE, default={})

    baseline_info = state.get("last_system_baseline") or {}
    baseline_path = baseline_info.get("json")
    baseline = load_json(baseline_path, default={})

    errors = []
    warnings = []
    drifts = []

    if not baseline:
        errors.append("missing_or_unreadable_system_baseline")
        baseline = {}

    baseline_files = baseline.get("files", [])
    baseline_by_path = {
        x.get("path"): x
        for x in baseline_files
        if x.get("path")
    }

    for path, old in baseline_by_path.items():
        p = WORKSPACE / path
        current_sha = sha256_file(path)
        exists = p.exists()
        is_file = p.is_file()

        if not exists or not is_file:
            drifts.append({
                "type": "baseline_file_missing",
                "path": path,
                "old_sha256": old.get("sha256"),
                "new_sha256": current_sha,
            })
            continue

        if current_sha != old.get("sha256"):
            drifts.append({
                "type": "baseline_file_hash_changed",
                "path": path,
                "old_sha256": old.get("sha256"),
                "new_sha256": current_sha,
            })

    current_scripts = current_learning_v2_scripts()
    baseline_scripts = sorted(
        x.get("path")
        for x in baseline_files
        if x.get("role") == "learning_v2_script" and x.get("path")
    )

    new_scripts = [x for x in current_scripts if x not in baseline_scripts]
    missing_scripts = [x for x in baseline_scripts if x not in current_scripts]

    for path in new_scripts:
        drifts.append({
            "type": "new_learning_v2_script_since_baseline",
            "path": path,
            "new_sha256": sha256_file(path),
        })

    for path in missing_scripts:
        drifts.append({
            "type": "missing_learning_v2_script_since_baseline",
            "path": path,
            "old_sha256": baseline_by_path.get(path, {}).get("sha256"),
        })

    preflight = run(["python3", "scripts/learning-v2-system-preflight.py"])

    state_after_preflight = load_json(STATE, default={})

    last_preflight = state_after_preflight.get("last_system_preflight") or {}
    gate_summary = last_preflight.get("gate_summary", {})
    commit_audit_summary = last_preflight.get("commit_plan_audit_summary", {})
    guard_result = last_preflight.get("local_git_guard_audit_result")

    if not preflight["ok"]:
        errors.append("system_preflight_failed")

    if gate_summary.get("ok_for_system_build") is not True:
        errors.append("ok_for_system_build_not_true")

    if gate_summary.get("ok_for_commit") is not False:
        errors.append("ok_for_commit_not_false")

    if gate_summary.get("ok_for_deploy") is not False:
        errors.append("ok_for_deploy_not_false")

    if gate_summary.get("business_freeze_stable") is not True:
        errors.append("business_freeze_not_stable")

    if commit_audit_summary.get("business_paths_selected_count") != 0:
        errors.append("commit_plan_selected_business_paths")

    if commit_audit_summary.get("dry_run_only") is not True:
        errors.append("commit_plan_not_dry_run_only")

    if guard_result != "ok":
        errors.append("local_git_guard_audit_not_ok")

    git_status = run(["git", "status", "--porcelain=v1", "-z"])
    dirty_rows = parse_git_status_z(git_status["stdout"])
    current_dirty_class_counts = {}

    for row in dirty_rows:
        cls = classify_dirty(row.get("path", ""))
        current_dirty_class_counts[cls] = current_dirty_class_counts.get(cls, 0) + 1

    baseline_dirty_class_counts = baseline.get("summary", {}).get("dirty_class_counts", {})
    if baseline_dirty_class_counts and current_dirty_class_counts != baseline_dirty_class_counts:
        warnings.append({
            "type": "dirty_class_counts_changed",
            "baseline": baseline_dirty_class_counts,
            "current": current_dirty_class_counts,
        })

    result = "ok" if not errors and not drifts else "blocked"

    report = {
        "generated_at": now_iso(),
        "auditor": "learning-v2-system-drift-auditor",
        "result": result,
        "baseline_json": baseline_path,
        "errors": errors,
        "warnings": warnings,
        "drifts": drifts,
        "summary": {
            "baseline_file_count": len(baseline_files),
            "current_learning_v2_script_count": len(current_scripts),
            "baseline_learning_v2_script_count": len(baseline_scripts),
            "drift_count": len(drifts),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "business_freeze_stable": gate_summary.get("business_freeze_stable"),
            "ok_for_system_build": gate_summary.get("ok_for_system_build"),
            "ok_for_commit": gate_summary.get("ok_for_commit"),
            "ok_for_deploy": gate_summary.get("ok_for_deploy"),
            "business_paths_selected_count": commit_audit_summary.get("business_paths_selected_count"),
            "dry_run_only": commit_audit_summary.get("dry_run_only"),
            "local_git_guard_audit_result": guard_result,
            "current_dirty_class_counts": current_dirty_class_counts,
            "baseline_dirty_class_counts": baseline_dirty_class_counts,
        },
        "policy": {
            "observational_only": True,
            "no_website_source_changes": True,
            "no_git_add": True,
            "no_git_commit": True,
            "no_git_push": True,
            "no_deploy": True,
        },
    }

    out = REPORT_DIR / f"system-drift-audit-{stamp()}.json"
    save_json(out, report)

    state_final = load_json(STATE, default={})
    state_final["last_system_drift_audit"] = {
        "generated_at": report["generated_at"],
        "path": str(out),
        "result": result,
        "summary": report["summary"],
        "errors": errors,
        "warnings": warnings,
        "drift_count": len(drifts),
    }
    save_json(STATE, state_final)

    print("system_drift_audit =", result)
    print("drift_audit_report =", out)
    print("baseline_json =", baseline_path)
    print("baseline_file_count =", len(baseline_files))
    print("current_learning_v2_script_count =", len(current_scripts))
    print("baseline_learning_v2_script_count =", len(baseline_scripts))
    print("drift_count =", len(drifts))
    print("error_count =", len(errors))
    print("warning_count =", len(warnings))
    print("business_freeze_stable =", gate_summary.get("business_freeze_stable"))
    print("ok_for_system_build =", gate_summary.get("ok_for_system_build"))
    print("ok_for_commit =", gate_summary.get("ok_for_commit"))
    print("ok_for_deploy =", gate_summary.get("ok_for_deploy"))
    print("business_paths_selected_count =", commit_audit_summary.get("business_paths_selected_count"))
    print("dry_run_only =", commit_audit_summary.get("dry_run_only"))
    print("local_git_guard_audit_result =", guard_result)

    if drifts:
        print()
        print("drifts:")
        for d in drifts:
            print(" ", d.get("type"), d.get("path"))

    if warnings:
        print()
        print("warnings:")
        for w in warnings:
            print(" ", w)

    if errors:
        print()
        print("errors:")
        for e in errors:
            print(" ", e)

    if result != "ok":
        raise SystemExit(2)

if __name__ == "__main__":
    main()
