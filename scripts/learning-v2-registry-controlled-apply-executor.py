#!/usr/bin/env python3
import argparse, json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
REPORT_DIR = WORKSPACE / "learning-v2" / "reports"
SNAPSHOT_DIR = WORKSPACE / "learning-v2" / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))

def latest(pattern):
    files = sorted(REPORT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-report")
    ap.add_argument("--allow-real-apply", action="store_true")
    args = ap.parse_args()

    if args.input_report:
        source = Path(args.input_report)
    else:
        source = latest("learning-v2-controlled-apply-context-gate-*.json")
        if not source:
            raise SystemExit("BLOCKED: no controlled apply context report found")

    payload = load_json(source)
    ctx = payload.get("controlled_apply_context") or {}
    ready = ctx.get("controlled_apply_context_status") == "controlled_apply_context_ready_dry_run"

    blockers = []
    if not ready:
        blockers.append("controlled_apply_context_not_ready")
    if args.allow_real_apply:
        blockers.append("allow_real_apply_flag_seen_but_executor_disabled_in_this_phase")
    if ctx.get("real_apply_allowed_now") is not False:
        blockers.append("context_real_apply_allowed_now_not_false")
    if ctx.get("registry_write_allowed_now") is not False:
        blockers.append("context_registry_write_allowed_now_not_false")

    status = "executor_refused_real_apply_as_expected" if blockers else "executor_ready_but_disabled"

    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-registry-controlled-apply-executor-skeleton-v0",
        "mode": "disabled_executor_dry_run",
        "source_context_report": str(source),
        "executor_status": status,
        "real_apply_executed": False,
        "registry_written": False,
        "blockers": blockers,
        "why": "Executor skeleton is intentionally disabled in this phase. It verifies refusal behavior only.",
        "safety": {
            "dry_run_only": True,
            "executor_disabled": True,
            "registry_written": False,
            "website_source_written": False,
            "d1_written": False,
            "r2_written": False,
            "kv_written": False,
            "worker_changed": False,
            "cloudflare_mutation": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False
        }
    }

    ts = stamp()
    jp = REPORT_DIR / f"learning-v2-registry-controlled-apply-executor-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-registry-controlled-apply-executor-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Registry Controlled Apply Executor Skeleton\n\n"
        f"- executor_status: `{status}`\n"
        "- real_apply_executed: `false`\n"
        "- registry_written: `false`\n"
        "- deploy: `false`\n",
        encoding="utf-8"
    )

    print("registry_controlled_apply_executor = ok")
    print("executor_status =", status)
    print("real_apply_executed = false")
    print("registry_written = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
