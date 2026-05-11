#!/usr/bin/env python3
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
SNAPSHOT_DIR = BASE / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

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

def file_entry(path, role):
    p = WORKSPACE / path
    return {
        "path": path,
        "role": role,
        "exists": p.exists(),
        "is_file": p.is_file(),
        "size": p.stat().st_size if p.exists() and p.is_file() else None,
        "sha256": sha256_file(path),
    }

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
    if path.startswith(("public/", "components/", "assets/", "src/", "functions/", "workers/")):
        return "business_source_blocked"
    if path.startswith(("scripts/", "learning-v2/", ".git/info/exclude")):
        return "system_engineering"
    return "other_existing_dirty"

def main():
    preflight = run(["python3", "scripts/learning-v2-system-preflight.py"])
    if not preflight["ok"]:
        print(preflight["stdout"])
        print(preflight["stderr"])
        print("system_baseline = blocked_by_preflight")
        raise SystemExit(2)

    state = load_json(STATE, default={})

    script_files = sorted(
        str(p.relative_to(WORKSPACE))
        for p in (WORKSPACE / "scripts").glob("learning-v2-*.py")
        if p.is_file()
    )

    baseline_files = []
    for path in script_files:
        baseline_files.append(file_entry(path, "learning_v2_script"))

    for path, role in [
        ("learning-v2/RUNBOOK.md", "runbook"),
        ("learning-v2/CONSTITUTION.md", "constitution"),
        ("learning-v2/target-family-registry.json", "target_family_registry"),
        ("learning-v2/mode-policy.json", "mode_policy"),
        (".git/hooks/pre-commit", "local_git_guard"),
        (".git/hooks/pre-push", "local_git_guard"),
    ]:
        baseline_files.append(file_entry(path, role))

    git_status = run(["git", "status", "--porcelain=v1", "-z"])
    dirty_rows = parse_git_status_z(git_status["stdout"])
    dirty_class_counts = {}

    for row in dirty_rows:
        cls = classify_dirty(row.get("path", ""))
        dirty_class_counts[cls] = dirty_class_counts.get(cls, 0) + 1

    last_release_gate_info = state.get("last_release_gate") or {}
    last_release_gate = load_json(last_release_gate_info.get("report"), default={}) if last_release_gate_info.get("report") else {}

    last_preflight_info = state.get("last_system_preflight") or {}
    last_commit_plan = state.get("last_commit_plan") or {}
    last_commit_plan_audit = state.get("last_commit_plan_audit") or {}
    last_guard_audit = state.get("last_local_git_guard_audit") or {}
    last_dirty_freeze = state.get("last_dirty_freeze") or {}
    last_system_manifest = state.get("last_system_manifest") or {}
    last_package_plan = state.get("last_package_plan") or {}

    gate_summary = last_release_gate.get("summary", {})
    commit_audit_summary = last_commit_plan_audit.get("summary", {})

    errors = []

    if gate_summary.get("ok_for_system_build") is not True:
        errors.append("release gate does not allow system build")

    if gate_summary.get("ok_for_commit") is not False:
        errors.append("release gate commit flag is not false")

    if gate_summary.get("ok_for_deploy") is not False:
        errors.append("release gate deploy flag is not false")

    if gate_summary.get("business_freeze_stable") is not True:
        errors.append("business freeze is not stable")

    if last_commit_plan_audit.get("result") != "ok":
        errors.append("commit plan audit is not ok")

    if commit_audit_summary.get("business_paths_selected_count") != 0:
        errors.append("commit plan selected business paths")

    if last_guard_audit.get("result") != "ok":
        errors.append("local git guard audit is not ok")

    missing_baseline_files = [x["path"] for x in baseline_files if not x["exists"] or not x["is_file"]]
    if missing_baseline_files:
        errors.append("some baseline files are missing")

    result = "ok" if not errors else "blocked"

    baseline = {
        "generated_at": now_iso(),
        "baseline": "learning-v2-system-baseline",
        "result": result,
        "errors": errors,
        "mode": "system_build_only",
        "summary": {
            "learning_v2_script_count": len(script_files),
            "baseline_file_count": len(baseline_files),
            "dirty_total_count": len(dirty_rows),
            "dirty_class_counts": dirty_class_counts,
            "business_source_dirty_count": gate_summary.get("business_source_dirty_count"),
            "business_freeze_stable": gate_summary.get("business_freeze_stable"),
            "ok_for_system_build": gate_summary.get("ok_for_system_build"),
            "ok_for_commit": gate_summary.get("ok_for_commit"),
            "ok_for_deploy": gate_summary.get("ok_for_deploy"),
            "commit_plan_audit_result": last_commit_plan_audit.get("result"),
            "business_paths_selected_count": commit_audit_summary.get("business_paths_selected_count"),
            "local_git_guard_audit_result": last_guard_audit.get("result"),
            "force_add_selected_count": last_commit_plan.get("force_add_selected_count"),
            "normal_add_selected_count": last_commit_plan.get("normal_add_selected_count"),
        },
        "files": baseline_files,
        "latest_reports": {
            "system_preflight": last_preflight_info.get("path"),
            "release_gate": last_release_gate_info.get("report"),
            "commit_plan_json": last_commit_plan.get("json"),
            "commit_plan_md": last_commit_plan.get("md"),
            "commit_plan_audit": last_commit_plan_audit.get("path"),
            "local_git_guard_audit": last_guard_audit.get("path"),
            "dirty_freeze": last_dirty_freeze.get("path"),
            "system_manifest": last_system_manifest.get("path") or last_system_manifest.get("report"),
            "package_plan": last_package_plan.get("path") or last_package_plan.get("md"),
        },
        "policy": {
            "no_website_source_changes": True,
            "no_git_add": True,
            "no_git_commit": True,
            "no_git_push": True,
            "no_deploy": True,
            "baseline_is_observational_only": True,
        },
    }

    out_json = SNAPSHOT_DIR / f"learning-v2-system-baseline-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-system-baseline-{stamp()}.md"

    save_json(out_json, baseline)

    lines = []
    lines.append("# learning-v2 system baseline")
    lines.append("")
    lines.append(f"generated_at: {baseline['generated_at']}")
    lines.append(f"result: {result}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    for k, v in baseline["summary"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Baseline files")
    lines.append("")
    for x in baseline_files:
        lines.append(f"- {x['role']}: {x['path']} sha256={x['sha256']}")
    lines.append("")
    lines.append("## Policy")
    lines.append("")
    lines.append("- no website source changes")
    lines.append("- no git add")
    lines.append("- no git commit")
    lines.append("- no git push")
    lines.append("- no deploy")
    lines.append("- baseline is observational only")
    lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    state["last_system_baseline"] = {
        "generated_at": baseline["generated_at"],
        "json": str(out_json),
        "md": str(out_md),
        "result": result,
        "summary": baseline["summary"],
        "errors": errors,
    }

    save_json(STATE, state)

    print("system_baseline =", result)
    print("baseline_json =", out_json)
    print("baseline_md =", out_md)
    print("learning_v2_script_count =", len(script_files))
    print("baseline_file_count =", len(baseline_files))
    print("dirty_total_count =", len(dirty_rows))
    print("business_source_dirty_count =", gate_summary.get("business_source_dirty_count"))
    print("business_freeze_stable =", gate_summary.get("business_freeze_stable"))
    print("ok_for_system_build =", gate_summary.get("ok_for_system_build"))
    print("ok_for_commit =", gate_summary.get("ok_for_commit"))
    print("ok_for_deploy =", gate_summary.get("ok_for_deploy"))
    print("commit_plan_audit_result =", last_commit_plan_audit.get("result"))
    print("business_paths_selected_count =", commit_audit_summary.get("business_paths_selected_count"))
    print("local_git_guard_audit_result =", last_guard_audit.get("result"))
    print("force_add_selected_count =", last_commit_plan.get("force_add_selected_count"))
    print("normal_add_selected_count =", last_commit_plan.get("normal_add_selected_count"))

    if errors:
        print()
        print("errors:")
        for e in errors:
            print(" ", e)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
