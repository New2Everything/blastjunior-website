#!/usr/bin/env python3
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
ORCH = WORKSPACE / "scripts" / "learning-v2-unified-runtime-e2e-dry-run-orchestrator.py"
REPORT_DIR = WORKSPACE / "learning-v2" / "reports"
SNAPSHOT_DIR = WORKSPACE / "learning-v2" / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCENARIOS = [
    ("match_record", "user_direct_with_/blxst", "/blxst 这是HPL最新比赛记录：A队 5:3 B队，请创建赛事独立页面并更新积分。", "content_runtime_e2e", "unified_runtime_e2e_content_guarded_for_later_controlled_apply"),
    ("homepage_copy", "user_direct_with_/blxst", "/blxst 更新首页宣传语：让每个孩子拥有自己的科技赛场。", "content_runtime_e2e", "unified_runtime_e2e_content_guarded_for_later_controlled_apply"),
    ("media_asset", "user_direct_with_/blxst", "/blxst 把这批照片放进上周HPL比赛页面。", "content_runtime_e2e", "unified_runtime_e2e_content_guarded_for_later_controlled_apply"),
    ("resource_structure", "user_direct_with_/blxst", "/blxst 新增一个D1数据表，记录HPL每一轮详细战报。", "registry_runtime_e2e", "unified_runtime_e2e_registry_ready_for_later_controlled_apply"),
    ("normal_text", "manual_probe", "帮我分析这场比赛的战术", "safe_stop_review", "unified_runtime_e2e_safe_stop_review_required")
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def run_one(name, origin, text, expected_branch, expected_status):
    p = subprocess.run(
        ["python3", str(ORCH), "--origin", origin, "--text", text],
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    report = None
    for line in p.stdout.splitlines():
        if line.startswith("report_json ="):
            report = line.split("=", 1)[1].strip()
    failures = []
    if p.returncode != 0 or not report:
        failures.append("unified_orchestrator_failed_or_report_missing")
        return {"scenario": name, "ok": False, "failures": failures, "stdout": p.stdout, "stderr": p.stderr}
    payload = load_json(report)
    safety = payload.get("safety") or {}
    if payload.get("branch") != expected_branch:
        failures.append("unexpected_branch:" + str(payload.get("branch")))
    if payload.get("final_status") != expected_status:
        failures.append("unexpected_final_status:" + str(payload.get("final_status")))
    if payload.get("real_apply_allowed_now") is not False:
        failures.append("real_apply_allowed_now_not_false")
    if payload.get("production_mutation_ready") is not False:
        failures.append("production_mutation_ready_not_false")
    if payload.get("production_deploy_ready") is not False:
        failures.append("production_deploy_ready_not_false")
    for k in ["registry_written","website_source_written","d1_written","r2_written","kv_written","worker_changed","cloudflare_mutation","git_commit","git_push","deploy"]:
        if safety.get(k) is not False:
            failures.append("unsafe_flag:" + k + ":" + str(safety.get(k)))
    return {
        "scenario": name,
        "ok": not failures,
        "branch": payload.get("branch"),
        "final_status": payload.get("final_status"),
        "report": report,
        "failures": failures
    }

def main():
    results = [run_one(*s) for s in SCENARIOS]
    hard = [r["scenario"] + ":" + f for r in results for f in r["failures"]]
    status = "ok" if not hard else "blocked"

    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-unified-runtime-e2e-smoke-v0",
        "mode": "dry_run",
        "unified_runtime_e2e_smoke": status,
        "scenario_count": len(results),
        "scenario_results": results,
        "hard_failures": hard,
        "safety": {
            "dry_run_only": True,
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
    jp = REPORT_DIR / f"learning-v2-unified-runtime-e2e-smoke-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-unified-runtime-e2e-smoke-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Unified Runtime E2E Smoke\n\n"
        f"- unified_runtime_e2e_smoke: `{status}`\n"
        f"- scenario_count: `{len(results)}`\n"
        f"- hard_failure_count: `{len(hard)}`\n"
        "- deploy: `false`\n",
        encoding="utf-8"
    )

    print("unified_runtime_e2e_smoke =", status)
    print("scenario_count =", len(results))
    print("hard_failure_count =", len(hard))
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    raise SystemExit(0 if status == "ok" else 1)

if __name__ == "__main__":
    main()
