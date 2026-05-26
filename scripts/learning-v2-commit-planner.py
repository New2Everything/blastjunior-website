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

DRY_RUN_ONLY = True

EXCLUDE_FROM_COMMIT_PREFIXES = (
    "learning-v2/reports/",
    "learning-v2/snapshots/",
    "learning-v2/freezes/",
    "learning-v2/cache/",
)

EXCLUDE_FROM_COMMIT_FILES = (
    "learning-v2/state.json",
    "learning-v2/experiments.jsonl",
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
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def sha256(path):
    p = WORKSPACE / path
    if not p.exists() or not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def is_tracked(path):
    rc, out, err = run(["git", "ls-files", "--error-unmatch", path])
    return rc == 0

def ignore_info(path):
    # Use --no-index so ignored paths remain detectable even after they are staged
    # with git add -f. Without this, staged ignored files may be misclassified
    # as normal_add instead of force_add.
    rc, out, err = run(["git", "check-ignore", "--no-index", "-v", path])
    if rc == 0:
        return out
    return ""

def status_for_path(path):
    rc, out, err = run(["git", "status", "--porcelain=v1", "--ignored=matching", "--", path])
    return out

def should_exclude(path):
    if path in EXCLUDE_FROM_COMMIT_FILES:
        return True
    return any(path.startswith(prefix) for prefix in EXCLUDE_FROM_COMMIT_PREFIXES)

def candidate_info(path, group):
    p = WORKSPACE / path
    return {
        "path": path,
        "group": group,
        "exists": p.exists(),
        "is_file": p.is_file(),
        "tracked": is_tracked(path),
        "ignored_by_gitignore": bool(ignore_info(path)),
        "ignore_info": ignore_info(path),
        "status": status_for_path(path),
        "sha256": sha256(path),
        "excluded_from_commit": should_exclude(path),
    }

def main():
    gate_rc, gate_out, gate_err = run(["python3", "scripts/learning-v2-release-gate.py"])

    state = load_json(STATE, default={})
    gate_info = state.get("last_release_gate") or {}
    gate_report_path = gate_info.get("report")
    gate_report = load_json(gate_report_path, default={}) if gate_report_path else {}
    gate_summary = gate_report.get("summary", {})

    if gate_rc != 0:
        print(gate_out)
        print(gate_err)
        print("commit_planner = blocked_by_release_gate")
        raise SystemExit(2)

    script_candidates = sorted(
        str(p.relative_to(WORKSPACE))
        for p in (WORKSPACE / "scripts").glob("learning-v2-*.py")
        if p.is_file()
    )

    doc_candidates = []
    runbook = WORKSPACE / "learning-v2" / "RUNBOOK.md"
    if runbook.exists():
        doc_candidates.append("learning-v2/RUNBOOK.md")

    constitution = WORKSPACE / "learning-v2" / "CONSTITUTION.md"
    if constitution.exists():
        doc_candidates.append("learning-v2/CONSTITUTION.md")

    directives_policy = WORKSPACE / "learning-v2" / "directives-policy.md"
    if directives_policy.exists():
        doc_candidates.append("learning-v2/directives-policy.md")

    patterns = WORKSPACE / "learning-v2" / "patterns.jsonl"
    if patterns.exists():
        doc_candidates.append("learning-v2/patterns.jsonl")

    source_evidence_summary = WORKSPACE / "learning-v2" / "source-evidence-summary.md"
    if source_evidence_summary.exists():
        doc_candidates.append("learning-v2/source-evidence-summary.md")

    doc_candidates.append("learning-v2/mode-policy.json")

    target_family_registry = WORKSPACE / "learning-v2" / "target-family-registry.json"
    if target_family_registry.exists():
        doc_candidates.append("learning-v2/target-family-registry.json")

    config_candidates = []
    for rel in [
        "learning-v2/push-approval-state.json",
        "learning-v2/cloudflare-option-b-state.json",
    ]:
        if (WORKSPACE / rel).exists():
            config_candidates.append(rel)

    runtime_candidates = []
    for rel in [
        "learning-v2/state.json",
        "learning-v2/experiments.jsonl",
    ]:
        if (WORKSPACE / rel).exists():
            runtime_candidates.append(rel)

    review_only_candidates = []
    for rel in [
        "scripts/hourly-optimization.sh",
        "scripts/auto-optimization.sh",
    ]:
        if (WORKSPACE / rel).exists() or is_tracked(rel):
            review_only_candidates.append(rel)

    candidates = []
    for path in script_candidates:
        candidates.append(candidate_info(path, "learning_v2_script"))
    for path in doc_candidates:
        candidates.append(candidate_info(path, "learning_v2_doc"))
    for path in config_candidates:
        candidates.append(candidate_info(path, "learning_v2_config"))
    for path in runtime_candidates:
        candidates.append(candidate_info(path, "runtime_excluded"))
    for path in review_only_candidates:
        candidates.append(candidate_info(path, "manual_review_only"))

    force_add_selected = []
    normal_add_selected = []
    excluded = []
    manual_review = []

    for item in candidates:
        path = item["path"]

        if item["group"] == "manual_review_only":
            manual_review.append(item)
            continue

        if item["excluded_from_commit"] or item["group"] == "runtime_excluded":
            excluded.append(item)
            continue

        if not item["exists"] or not item["is_file"]:
            excluded.append(item)
            continue

        if item["ignored_by_gitignore"]:
            force_add_selected.append(item)
        elif item["tracked"]:
            normal_add_selected.append(item)
        else:
            normal_add_selected.append(item)

    commit_message = "Add learning-v2 system engineering guardrails"

    plan = {
        "generated_at": now_iso(),
        "planner": "learning-v2-commit-planner",
        "dry_run_only": DRY_RUN_ONLY,
        "mode": "system_build_only",
        "gate_summary": gate_summary,
        "decision": {
            "commit_now": False,
            "push_now": False,
            "deploy_now": False,
            "reason": "Current policy forbids commit/push/deploy. This planner only prepares a future selected-file plan.",
        },
        "selected_future_commit_scope": {
            "force_add_selected_files": [x["path"] for x in force_add_selected],
            "normal_add_selected_files": [x["path"] for x in normal_add_selected],
            "excluded_runtime_files": [x["path"] for x in excluded],
            "manual_review_only_files": [x["path"] for x in manual_review],
        },
        "candidate_details": candidates,
        "future_commands_for_manual_approval_only": {
            "preflight": [
                "python3 scripts/learning-v2-release-gate.py"
            ],
            "force_add": [
                "git add -f " + " ".join(x["path"] for x in force_add_selected)
            ] if force_add_selected else [],
            "normal_add": [
                "git add " + " ".join(x["path"] for x in normal_add_selected)
            ] if normal_add_selected else [],
            "inspect": [
                "git diff --cached --stat",
                "git diff --cached --name-status"
            ],
            "commit": [
                "git commit -m \"" + commit_message + "\""
            ],
            "forbidden_now": [
                "git push",
                "wrangler deploy",
                "Cloudflare Pages deploy"
            ],
        },
    }

    json_path = SNAPSHOT_DIR / f"learning-v2-commit-plan-{stamp()}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-commit-plan-{stamp()}.md"

    save_json(json_path, plan)

    lines = []
    lines.append("# learning-v2 dry-run commit plan")
    lines.append("")
    lines.append(f"generated_at: {plan['generated_at']}")
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append("- commit_now: false")
    lines.append("- push_now: false")
    lines.append("- deploy_now: false")
    lines.append("- reason: current policy forbids commit / push / deploy")
    lines.append("")
    lines.append("## Gate summary")
    lines.append("")
    for k, v in gate_summary.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Force-add selected files")
    lines.append("")
    if force_add_selected:
        for x in force_add_selected:
            lines.append(f"- {x['path']}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Normal-add selected files")
    lines.append("")
    if normal_add_selected:
        for x in normal_add_selected:
            lines.append(f"- {x['path']}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Excluded runtime files")
    lines.append("")
    if excluded:
        for x in excluded:
            lines.append(f"- {x['path']}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Manual review only")
    lines.append("")
    if manual_review:
        for x in manual_review:
            lines.append(f"- {x['path']} status={x['status']}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Future commands for manual approval only")
    lines.append("")
    lines.append("Preflight:")
    lines.append("")
    lines.append("    python3 scripts/learning-v2-release-gate.py")
    lines.append("")
    if force_add_selected:
        lines.append("Force add:")
        lines.append("")
        lines.append("    git add -f " + " ".join(x["path"] for x in force_add_selected))
        lines.append("")
    if normal_add_selected:
        lines.append("Normal add:")
        lines.append("")
        lines.append("    git add " + " ".join(x["path"] for x in normal_add_selected))
        lines.append("")
    lines.append("Inspect:")
    lines.append("")
    lines.append("    git diff --cached --stat")
    lines.append("    git diff --cached --name-status")
    lines.append("")
    lines.append("Commit, still forbidden now:")
    lines.append("")
    lines.append("    git commit -m \"" + commit_message + "\"")
    lines.append("")
    lines.append("Push/deploy, forbidden now:")
    lines.append("")
    lines.append("    git push")
    lines.append("    wrangler deploy")
    lines.append("")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    state["last_commit_plan"] = {
        "generated_at": plan["generated_at"],
        "json": str(json_path),
        "md": str(md_path),
        "dry_run_only": True,
        "force_add_selected_count": len(force_add_selected),
        "normal_add_selected_count": len(normal_add_selected),
        "excluded_count": len(excluded),
        "manual_review_count": len(manual_review),
    }
    save_json(STATE, state)

    print("commit_planner = dry_run_only")
    print("commit_now = False")
    print("push_now = False")
    print("deploy_now = False")
    print("commit_plan_json =", json_path)
    print("commit_plan_md =", md_path)
    print("force_add_selected_count =", len(force_add_selected))
    print("normal_add_selected_count =", len(normal_add_selected))
    print("excluded_count =", len(excluded))
    print("manual_review_count =", len(manual_review))
    print()
    print("force_add_selected_files:")
    for x in force_add_selected:
        print(" ", x["path"])
    print()
    print("normal_add_selected_files:")
    for x in normal_add_selected:
        print(" ", x["path"])
    print()
    print("excluded_runtime_files:")
    for x in excluded:
        print(" ", x["path"])
    print()
    print("manual_review_only_files:")
    for x in manual_review:
        print(" ", x["path"], x["status"])

if __name__ == "__main__":
    main()
