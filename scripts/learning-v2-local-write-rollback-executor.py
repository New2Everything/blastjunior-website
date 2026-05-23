#!/usr/bin/env python3
import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(".")
RUNTIME = Path("learning-v2/runtime")
REPORTS = Path("learning-v2/reports")
FREEZE = Path("learning-v2/freezes/local-write-rollback")
RUNTIME.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)
FREEZE.mkdir(parents=True, exist_ok=True)

ALLOWED_TARGETS = {
    "public/gallery.html",
}

BLOCKED_PREFIXES = (
    "components/",
    "worker/",
    "sql/",
)

BLOCKED_EXACT = {
    "public/index.html",
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def sh(cmd):
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def sha256(path):
    p = Path(path)
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()

def git_status_path(path):
    return sh(["git", "status", "--porcelain", "--", str(path)]).stdout.strip()

def git_diff_stat(path):
    return sh(["git", "diff", "--stat", "--", str(path)]).stdout.strip()

def is_tracked(path):
    return bool(sh(["git", "ls-files", "--", str(path)]).stdout.strip())

def fail_report(payload, reason):
    payload["executor_status"] = "blocked"
    payload["hard_blocks"].append(reason)
    write_reports(payload)
    print_summary(payload)
    raise SystemExit(0)

def write_reports(payload):
    s = stamp()
    json_path = REPORTS / f"learning-v2-local-write-rollback-executor-{payload['mode']}-{s}.json"
    md_path = RUNTIME / f"learning-v2-local-write-rollback-executor-{payload['mode']}-{s}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Local Write Rollback Executor",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- mode: `{payload['mode']}`",
        f"- executor_status: `{payload['executor_status']}`",
        f"- target: `{payload['target']}`",
        f"- apply: `{str(payload['apply']).lower()}`",
        f"- local_write_performed: `{str(payload['local_write_performed']).lower()}`",
        f"- rollback_performed: `{str(payload['rollback_performed']).lower()}`",
        f"- rollback_ok: `{payload.get('rollback_ok')}`",
        f"- git_commit: `{str(payload['git_commit']).lower()}`",
        f"- git_push: `{str(payload['git_push']).lower()}`",
        f"- deploy: `{str(payload['deploy']).lower()}`",
        "",
        "## Hard Blocks",
        "",
    ]
    if payload["hard_blocks"]:
        for b in payload["hard_blocks"]:
            lines.append(f"- {b}")
    else:
        lines.append("- none")

    lines += [
        "",
        "## Safety",
        "",
        "- no git commit",
        "- no git push",
        "- no deploy",
        "- no Cloudflare API mutation",
    ]

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    payload["_json_report"] = str(json_path)
    payload["_md_report"] = str(md_path)

def print_summary(payload):
    print("local_write_rollback_executor =", payload["executor_status"])
    print("mode =", payload["mode"])
    print("target =", payload["target"])
    print("apply =", str(payload["apply"]).lower())
    print("local_write_performed =", str(payload["local_write_performed"]).lower())
    print("post_write_ok =", payload.get("post_write_ok"))
    print("rollback_performed =", str(payload["rollback_performed"]).lower())
    print("rollback_ok =", payload.get("rollback_ok"))
    print("git_status_before =", repr(payload.get("git_status_before")))
    print("git_status_after =", repr(payload.get("git_status_after")))
    print("git_diff_after =", repr(payload.get("git_diff_after")))
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("hard_blocks =", json.dumps(payload["hard_blocks"], ensure_ascii=False))
    if payload.get("_json_report"):
        print("report_json =", payload["_json_report"])
    if payload.get("_md_report"):
        print("report_md =", payload["_md_report"])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="public/gallery.html")
    ap.add_argument("--apply", action="store_true", help="perform local write and rollback; never commit/push/deploy")
    args = ap.parse_args()

    target = Path(args.target)
    target_str = str(target)

    payload = {
        "generated_at": now_iso(),
        "executor_id": "learning-v2-local-write-rollback-executor-v0",
        "mode": "apply" if args.apply else "dry_run",
        "apply": args.apply,
        "target": target_str,
        "executor_status": None,
        "hard_blocks": [],
        "warnings": [],
        "target_exists": target.exists(),
        "target_tracked": is_tracked(target),
        "git_status_before": git_status_path(target),
        "hash_before": sha256(target),
        "backup": None,
        "backup_hash": None,
        "marker": None,
        "hash_after_write": None,
        "post_write_ok": None,
        "rollback_ok": None,
        "git_status_after": None,
        "git_diff_after": None,
        "local_write_performed": False,
        "rollback_performed": False,
        "source_changed": False,
        "website_source_written": False,
        "git_commit": False,
        "git_push": False,
        "cloudflare_api_called": False,
        "cloudflare_deploy_triggered": False,
        "deploy": False,
        "rules": {
            "allow_git_commit": False,
            "allow_git_push": False,
            "allow_deploy": False,
            "allow_cloudflare_api_mutation": False,
            "require_backup_before_write": True,
            "require_rollback_after_write": True,
            "allowed_targets": sorted(ALLOWED_TARGETS),
        },
    }

    if target_str in BLOCKED_EXACT:
        fail_report(payload, f"blocked_exact_target:{target_str}")

    if any(target_str.startswith(p) for p in BLOCKED_PREFIXES):
        fail_report(payload, f"blocked_prefix_target:{target_str}")

    if target_str not in ALLOWED_TARGETS:
        fail_report(payload, f"target_not_in_allowed_round5_set:{target_str}")

    if not target.exists():
        fail_report(payload, "target_missing")

    if not payload["target_tracked"]:
        fail_report(payload, "target_not_tracked")

    if payload["git_status_before"]:
        fail_report(payload, f"target_dirty_before_write:{payload['git_status_before']}")

    backup = FREEZE / f"{target.name}.before-local-write-rollback-{stamp()}"
    payload["backup"] = str(backup)

    if not args.apply:
        payload["executor_status"] = "dry_run_ready_for_apply"
        payload["recommended_next_action"] = "rerun_with_apply_to_perform_local_write_then_rollback"
        write_reports(payload)
        print_summary(payload)
        return

    shutil.copy2(target, backup)
    payload["backup_hash"] = sha256(backup)

    if payload["backup_hash"] != payload["hash_before"]:
        fail_report(payload, "backup_hash_mismatch_before_write")

    marker = f"<!-- LEARNING_V2_LOCAL_WRITE_ROLLBACK_EXECUTOR {now_iso()} no-commit no-push no-deploy -->\n"
    payload["marker"] = marker.strip()

    original = target.read_text(encoding="utf-8")
    target.write_text(marker + original, encoding="utf-8")

    payload["local_write_performed"] = True
    payload["source_changed"] = True
    payload["website_source_written"] = True
    payload["hash_after_write"] = sha256(target)

    status_after_write = git_status_path(target)
    text_after_write = target.read_text(encoding="utf-8", errors="replace")
    payload["post_write_ok"] = (
        status_after_write.startswith("M ")
        and marker.strip() in text_after_write
        and payload["hash_after_write"] != payload["hash_before"]
    )

    if not payload["post_write_ok"]:
        fail_report(payload, f"post_write_validation_failed:{status_after_write}")

    shutil.copy2(backup, target)
    payload["rollback_performed"] = True
    payload["git_status_after"] = git_status_path(target)
    payload["git_diff_after"] = git_diff_stat(target)

    payload["rollback_ok"] = (
        payload["git_status_after"] == ""
        and payload["git_diff_after"] == ""
        and sha256(target) == payload["hash_before"]
    )

    if not payload["rollback_ok"]:
        fail_report(payload, "rollback_restore_validation_failed")

    payload["source_changed"] = False
    payload["website_source_written"] = False
    payload["executor_status"] = "local_write_and_rollback_verified"
    payload["recommended_next_action"] = "record_native_executor_success_and_consider_system_governance_commit"

    write_reports(payload)
    print_summary(payload)

if __name__ == "__main__":
    main()
