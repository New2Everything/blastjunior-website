#!/usr/bin/env python3
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

GUARD_ID = "learning-v2-staging-guard-v0"

FORBIDDEN_PREFIXES = (
    "public/",
    "components/",
    "learning-v2/reports/",
    "learning-v2/snapshots/",
    "learning-v2/backups/",
    "learning-v2/cache/",
    "worker/",
    "artifacts/",
    "harness/",
    "blxst/",
)

FORBIDDEN_EXACT = {
    "learning-v2/state.json",
    "learning-v2/experiments.jsonl",
    "learning-v2/outcomes.jsonl",
    "scripts/hourly-optimization.sh",
    "scripts/auto-optimization.sh",
}

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
        check=False,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def staged_name_status():
    rc, out, err = run(["git", "diff", "--cached", "--name-status"])
    if rc != 0:
        raise RuntimeError(f"git diff --cached failed: {err}")
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append({"status": parts[0], "path": parts[-1], "raw": line})
    return rows

def is_forbidden(path):
    return path in FORBIDDEN_EXACT or any(path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)

def main():
    state = load_json(STATE, default={})
    info = state.get("last_commit_plan") or {}
    plan_path = Path(info.get("json", ""))
    plan = load_json(plan_path, default={}) if plan_path.exists() else {}

    scope = plan.get("selected_future_commit_scope") or {}
    force_add = scope.get("force_add_selected_files") or []
    normal_add = scope.get("normal_add_selected_files") or []
    allowed = set(force_add) | set(normal_add)

    decision = plan.get("decision") or {}
    failures = []
    warnings = []

    if not plan_path.exists():
        failures.append(f"missing_commit_plan:{plan_path}")

    if plan.get("dry_run_only") is not True:
        failures.append(f"commit_plan_not_dry_run_only:{plan.get('dry_run_only')}")

    if decision.get("commit_now") is not False:
        failures.append(f"commit_now_not_false:{decision.get('commit_now')}")

    if decision.get("push_now") is not False:
        failures.append(f"push_now_not_false:{decision.get('push_now')}")

    if decision.get("deploy_now") is not False:
        failures.append(f"deploy_now_not_false:{decision.get('deploy_now')}")

    if not allowed:
        failures.append("allowed_staging_whitelist_empty")

    staged = staged_name_status()
    staged_paths = [x["path"] for x in staged]

    staged_not_in_whitelist = [p for p in staged_paths if p not in allowed]
    staged_forbidden = [p for p in staged_paths if is_forbidden(p)]

    if staged_not_in_whitelist:
        failures.append("staged_paths_not_in_commit_plan_whitelist")

    if staged_forbidden:
        failures.append("forbidden_paths_are_staged")

    allowed_forbidden_overlap = sorted([p for p in allowed if is_forbidden(p)])
    if allowed_forbidden_overlap:
        failures.append("commit_plan_whitelist_contains_forbidden_paths")

    if len(force_add) != info.get("force_add_selected_count"):
        warnings.append(f"force_add_count_mismatch:state={info.get('force_add_selected_count')} plan={len(force_add)}")

    if len(normal_add) != info.get("normal_add_selected_count"):
        warnings.append(f"normal_add_count_mismatch:state={info.get('normal_add_selected_count')} plan={len(normal_add)}")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "guard_id": GUARD_ID,
        "result": result,
        "mode": "staging_guard_only",
        "commit_plan_json": str(plan_path),
        "allowed_force_add_count": len(force_add),
        "allowed_normal_add_count": len(normal_add),
        "allowed_total_count": len(allowed),
        "staged_count": len(staged),
        "staged_paths": staged,
        "staged_not_in_whitelist": staged_not_in_whitelist,
        "staged_forbidden": staged_forbidden,
        "allowed_forbidden_overlap": allowed_forbidden_overlap,
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "git_add": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "guard_only": True,
            "business_source_staging_allowed": False,
        },
        "recommended_next_step": (
            "index_is_clean_or_whitelisted; guarded git add may be prepared but do not commit/push/deploy"
            if result == "ok"
            else "unstage forbidden paths or fix commit plan before any git add/commit"
        ),
    }

    out_json = REPORT_DIR / f"learning-v2-staging-guard-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-staging-guard-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Staging Guard")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- mode: `{payload['mode']}`")
    lines.append(f"- commit_plan_json: `{plan_path}`")
    lines.append(f"- allowed_force_add_count: `{len(force_add)}`")
    lines.append(f"- allowed_normal_add_count: `{len(normal_add)}`")
    lines.append(f"- allowed_total_count: `{len(allowed)}`")
    lines.append(f"- staged_count: `{len(staged)}`")
    lines.append("- git_add: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Staged paths")
    if staged:
        for item in staged:
            lines.append(f"- `{item['status']}` `{item['path']}`")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Failures")
    if failures:
        for f in failures:
            lines.append(f"- {f}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Warnings")
    if warnings:
        for w in warnings:
            lines.append(f"- {w}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Recommended next step")
    lines.append(payload["recommended_next_step"])
    lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("staging_guard =", result)
    print("mode = staging_guard_only")
    print("commit_plan_json =", plan_path)
    print("allowed_force_add_count =", len(force_add))
    print("allowed_normal_add_count =", len(normal_add))
    print("allowed_total_count =", len(allowed))
    print("staged_count =", len(staged))
    print("git_add = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("recommended_next_step =", payload["recommended_next_step"])
    print("report_json =", out_json)
    print("report_md =", out_md)

    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
