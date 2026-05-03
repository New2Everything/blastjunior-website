#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
SNAPSHOT_DIR = BASE / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

BUSINESS_PREFIXES = (
    "public/",
    "components/",
    "assets/",
    "src/",
    "functions/",
    "workers/",
)

ALLOWED_FORCE_ADD_PREFIX = "scripts/learning-v2-"
ALLOWED_FORCE_ADD_SUFFIX = ".py"

ALLOWED_NORMAL_ADD_FILES = {
    "learning-v2/RUNBOOK.md",
}

ALLOWED_EXCLUDED_RUNTIME_FILES = {
    "learning-v2/state.json",
    "learning-v2/experiments.jsonl",
}

ALLOWED_MANUAL_REVIEW_FILES = {
    "scripts/hourly-optimization.sh",
    "scripts/auto-optimization.sh",
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def is_business_path(path):
    return path.startswith(BUSINESS_PREFIXES)

def main():
    state = load_json(STATE, default={})
    plan_info = state.get("last_commit_plan") or {}
    plan_json = plan_info.get("json")

    errors = []
    warnings = []

    if not plan_json:
        errors.append("missing last_commit_plan.json in state")
        plan = {}
    else:
        plan = load_json(plan_json, default={})
        if not plan:
            errors.append(f"commit plan not found or unreadable: {plan_json}")

    decision = plan.get("decision", {})
    scope = plan.get("selected_future_commit_scope", {})

    force_add = scope.get("force_add_selected_files", [])
    normal_add = scope.get("normal_add_selected_files", [])
    excluded = scope.get("excluded_runtime_files", [])
    manual_review = scope.get("manual_review_only_files", [])

    all_selected = force_add + normal_add

    if plan.get("dry_run_only") is not True:
        errors.append("plan.dry_run_only is not true")

    if decision.get("commit_now") is not False:
        errors.append("decision.commit_now is not false")

    if decision.get("push_now") is not False:
        errors.append("decision.push_now is not false")

    if decision.get("deploy_now") is not False:
        errors.append("decision.deploy_now is not false")

    for path in all_selected:
        if is_business_path(path):
            errors.append(f"business source path selected for future commit: {path}")

    for path in force_add:
        if not (path.startswith(ALLOWED_FORCE_ADD_PREFIX) and path.endswith(ALLOWED_FORCE_ADD_SUFFIX)):
            errors.append(f"force_add file outside scripts/learning-v2-*.py: {path}")

    for path in normal_add:
        if path not in ALLOWED_NORMAL_ADD_FILES:
            errors.append(f"normal_add file not allowed by v0.1 policy: {path}")

    for path in excluded:
        if path not in ALLOWED_EXCLUDED_RUNTIME_FILES:
            warnings.append(f"excluded runtime file not in known allowlist: {path}")

    for path in manual_review:
        if path not in ALLOWED_MANUAL_REVIEW_FILES:
            warnings.append(f"manual review file not in known allowlist: {path}")

    gate_summary = plan.get("gate_summary", {})

    if gate_summary.get("ok_for_system_build") is not True:
        errors.append("gate_summary.ok_for_system_build is not true")

    if gate_summary.get("ok_for_commit") is not False:
        errors.append("gate_summary.ok_for_commit is not false")

    if gate_summary.get("ok_for_deploy") is not False:
        errors.append("gate_summary.ok_for_deploy is not false")

    if gate_summary.get("business_freeze_stable") is not True:
        errors.append("gate_summary.business_freeze_stable is not true")

    future_commands = plan.get("future_commands_for_manual_approval_only", {})
    forbidden_now = future_commands.get("forbidden_now", [])

    if "git push" not in forbidden_now:
        warnings.append("forbidden_now does not explicitly include git push")

    if not any("deploy" in x.lower() for x in forbidden_now):
        warnings.append("forbidden_now does not explicitly include deploy")

    audit = {
        "generated_at": now_iso(),
        "auditor": "learning-v2-commit-plan-auditor",
        "plan_json": plan_json,
        "result": "ok" if not errors else "blocked",
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "force_add_count": len(force_add),
            "normal_add_count": len(normal_add),
            "excluded_count": len(excluded),
            "manual_review_count": len(manual_review),
            "business_paths_selected_count": len([x for x in all_selected if is_business_path(x)]),
            "dry_run_only": plan.get("dry_run_only"),
            "commit_now": decision.get("commit_now"),
            "push_now": decision.get("push_now"),
            "deploy_now": decision.get("deploy_now"),
        },
        "scope": scope,
    }

    out = SNAPSHOT_DIR / f"learning-v2-commit-plan-audit-{stamp()}.json"
    save_json(out, audit)

    state["last_commit_plan_audit"] = {
        "generated_at": audit["generated_at"],
        "path": str(out),
        "result": audit["result"],
        "summary": audit["summary"],
        "errors": errors,
        "warnings": warnings,
    }
    save_json(STATE, state)

    print("commit_plan_audit =", audit["result"])
    print("audit_report =", out)
    print("force_add_count =", len(force_add))
    print("normal_add_count =", len(normal_add))
    print("excluded_count =", len(excluded))
    print("manual_review_count =", len(manual_review))
    print("business_paths_selected_count =", audit["summary"]["business_paths_selected_count"])
    print("dry_run_only =", plan.get("dry_run_only"))
    print("commit_now =", decision.get("commit_now"))
    print("push_now =", decision.get("push_now"))
    print("deploy_now =", decision.get("deploy_now"))

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
        raise SystemExit(2)

if __name__ == "__main__":
    main()
