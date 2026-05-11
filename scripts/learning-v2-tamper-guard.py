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
SNAPSHOT_DIR = BASE / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-tamper-guard-v0.2"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def sha256_file(rel):
    p = WORKSPACE / rel
    if not p.exists() or not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def run_cmd(args):
    p = subprocess.run(
        args,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "cmd": args,
        "returncode": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
        "ok": p.returncode == 0,
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

def is_website_business_path(path):
    return path.startswith((
        "public/",
        "components/",
        "assets/",
        "src/",
        "functions/",
        "workers/",
        "worker/",
        "sql/",
    ))

def main():
    generated_at = now_iso()
    ts = stamp()

    state = load_json(STATE, default={})
    baseline_info = state.get("last_system_baseline") or {}
    baseline_path = baseline_info.get("json")
    baseline = load_json(baseline_path, default=None) if baseline_path else None

    failures = []
    warnings = []

    if not baseline:
        failures.append({
            "type": "missing_system_baseline",
            "message": "No readable last_system_baseline JSON found in learning-v2/state.json",
            "path": baseline_path,
        })
        baseline_files = []
    else:
        baseline_files = baseline.get("files", [])

    protected_roles = {
        "learning_v2_script",
        "constitution",
        "target_family_registry",
        "runbook",
        "mode_policy",
        "local_git_guard",
    }

    protected_baseline_files = [
        x for x in baseline_files
        if x.get("role") in protected_roles
    ]

    baseline_by_path = {
        x.get("path"): x
        for x in protected_baseline_files
        if x.get("path")
    }

    # 1) Check protected baseline files still exist and match hashes.
    changed_protected_files = []
    missing_protected_files = []

    for rel, entry in sorted(baseline_by_path.items()):
        p = WORKSPACE / rel
        if not p.exists() or not p.is_file():
            missing_protected_files.append({
                "path": rel,
                "role": entry.get("role"),
                "expected_sha256": entry.get("sha256"),
            })
            continue
        current_sha = sha256_file(rel)
        expected_sha = entry.get("sha256")
        if current_sha != expected_sha:
            changed_protected_files.append({
                "path": rel,
                "role": entry.get("role"),
                "expected_sha256": expected_sha,
                "current_sha256": current_sha,
            })

    # 2) Check new learning-v2 scripts not yet in baseline.
    current_learning_v2_scripts = sorted(
        str(p.relative_to(WORKSPACE))
        for p in (WORKSPACE / "scripts").glob("learning-v2-*.py")
        if p.is_file()
    )

    baseline_learning_v2_scripts = sorted(
        rel for rel, entry in baseline_by_path.items()
        if entry.get("role") == "learning_v2_script"
    )

    baseline_script_set = set(baseline_learning_v2_scripts)
    current_script_set = set(current_learning_v2_scripts)

    new_learning_v2_scripts = sorted(current_script_set - baseline_script_set)
    deleted_learning_v2_scripts = sorted(baseline_script_set - current_script_set)

    if new_learning_v2_scripts:
        failures.append({
            "type": "new_learning_v2_script_not_in_baseline",
            "paths": new_learning_v2_scripts,
        })

    if deleted_learning_v2_scripts:
        failures.append({
            "type": "baseline_learning_v2_script_deleted",
            "paths": deleted_learning_v2_scripts,
        })

    if changed_protected_files:
        failures.append({
            "type": "protected_file_hash_changed",
            "files": changed_protected_files,
        })

    if missing_protected_files:
        failures.append({
            "type": "protected_file_missing",
            "files": missing_protected_files,
        })

    # 3) Check business source dirty changes through release_gate semantics.
    # Important:
    # - release_gate is the source of truth for business_source_dirty_count.
    # - Some legacy untracked paths such as sql/ or worker/ may already exist in this workspace.
    # - Those legacy paths should be warnings in tamper guard v0.2, not hard blockers,
    #   unless release_gate itself reports business_source_dirty_count > 0.
    git_status = run_cmd(["git", "status", "--porcelain=v1", "-z"])
    dirty_rows = parse_git_status_z(git_status["stdout"])

    release_gate = run_cmd(["python3", "scripts/learning-v2-release-gate.py"])
    release_gate_kv = {}
    for line in release_gate["stdout"].splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            release_gate_kv[k.strip()] = v.strip()

    try:
        release_gate_business_source_dirty_count = int(
            release_gate_kv.get("business_source_dirty_count", "0")
        )
    except Exception:
        release_gate_business_source_dirty_count = None

    business_dirty_rows = [
        row for row in dirty_rows
        if is_website_business_path(row.get("path", ""))
    ]

    if release_gate_business_source_dirty_count not in (0, None):
        failures.append({
            "type": "release_gate_business_source_dirty",
            "business_source_dirty_count": release_gate_business_source_dirty_count,
            "release_gate_stdout": release_gate["stdout"],
        })

    if business_dirty_rows:
        warnings.append({
            "type": "business_like_dirty_paths_observed_by_tamper_guard_v0_2",
            "note": "warning only; release_gate remains source of truth for blocking business source dirty state",
            "release_gate_business_source_dirty_count": release_gate_business_source_dirty_count,
            "files": business_dirty_rows,
        })

    # 4) Advisory only: important policy/docs present but not in baseline.
    advisory_paths = [
        "learning-v2/deployment-policy.json",
        "learning-v2/CONSTITUTION.md",
        "learning-v2/RUNBOOK.md",
        "learning-v2/mode-policy.json",
        "AGENTS.md",
        "MEMORY.md",
        "TOOLS.md",
    ]

    for rel in advisory_paths:
        p = WORKSPACE / rel
        if p.exists() and rel not in baseline_by_path:
            warnings.append({
                "type": "important_file_not_protected_by_baseline_v0",
                "path": rel,
                "note": "v0.1 warning only; not a blocker yet",
            })

    result = "ok" if not failures else "blocked"

    report = {
        "script_id": SCRIPT_ID,
        "generated_at": generated_at,
        "result": result,
        "baseline_json": baseline_path,
        "summary": {
            "protected_file_count": len(protected_baseline_files),
            "baseline_learning_v2_script_count": len(baseline_learning_v2_scripts),
            "current_learning_v2_script_count": len(current_learning_v2_scripts),
            "changed_protected_file_count": len(changed_protected_files),
            "missing_protected_file_count": len(missing_protected_files),
            "new_learning_v2_script_count": len(new_learning_v2_scripts),
            "deleted_learning_v2_script_count": len(deleted_learning_v2_scripts),
            "business_dirty_count": len(business_dirty_rows),
            "failure_count": len(failures),
            "warning_count": len(warnings),
        },
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "no_website_source_changes": True,
            "no_git_add": True,
            "no_git_commit": True,
            "no_git_push": True,
            "no_deploy": True,
            "tamper_guard_is_observational_only": True,
        },
    }

    report_path = REPORT_DIR / f"learning-v2-tamper-guard-{ts}.json"
    snapshot_path = SNAPSHOT_DIR / f"learning-v2-tamper-guard-{ts}.md"

    save_json(report_path, report)

    lines = []
    lines.append("# Learning V2 Tamper Guard")
    lines.append("")
    lines.append(f"- generated_at: {generated_at}")
    lines.append(f"- script_id: {SCRIPT_ID}")
    lines.append(f"- result: {result}")
    lines.append(f"- baseline_json: {baseline_path}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    for k, v in report["summary"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    if result == "ok":
        lines.append("learning-v2 protected core files match the accepted system baseline.")
    else:
        lines.append("learning-v2 protected core files do not match the accepted system baseline. Do not proceed.")
    lines.append("")
    lines.append("## Failures")
    lines.append("")
    if failures:
        for f in failures:
            lines.append(f"- {f}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Warnings")
    lines.append("")
    if warnings:
        for w in warnings:
            lines.append(f"- {w}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Policy")
    lines.append("")
    lines.append("- no website source changes")
    lines.append("- no git add")
    lines.append("- no git commit")
    lines.append("- no git push")
    lines.append("- no deploy")
    lines.append("- observational only")
    lines.append("")

    snapshot_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"learning_v2_tamper_guard = {result}")
    print(f"tamper_guard_report = {report_path}")
    print(f"tamper_guard_snapshot = {snapshot_path}")
    print(f"protected_file_count = {len(protected_baseline_files)}")
    print(f"changed_protected_file_count = {len(changed_protected_files)}")
    print(f"missing_protected_file_count = {len(missing_protected_files)}")
    print(f"new_learning_v2_script_count = {len(new_learning_v2_scripts)}")
    print(f"deleted_learning_v2_script_count = {len(deleted_learning_v2_scripts)}")
    print(f"business_dirty_count = {len(business_dirty_rows)}")
    print(f"failure_count = {len(failures)}")
    print(f"warning_count = {len(warnings)}")
    print("website_files_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
