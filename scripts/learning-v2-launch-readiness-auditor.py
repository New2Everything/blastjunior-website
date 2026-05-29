#!/usr/bin/env python3
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
POLICY = WORKSPACE / "projects" / "BLXST-launch-readiness-policy.json"
ORIGIN_POLICY = WORKSPACE / "projects" / "BLXST-runtime-origin-policy.json"
ENTRYPOINT = WORKSPACE / "scripts" / "learning-v2-runtime-entrypoint-dry-run.py"
CONTROLLED_SMOKE = WORKSPACE / "scripts" / "learning-v2-controlled-apply-readiness-smoke.py"
REPORT_DIR = WORKSPACE / "learning-v2" / "reports"
SNAPSHOT_DIR = WORKSPACE / "learning-v2" / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def run(cmd):
    p = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    report = None
    for line in p.stdout.splitlines():
        if line.startswith("report_json ="):
            report = line.split("=", 1)[1].strip()
    return p.returncode, report, p.stdout, p.stderr

def git_clean():
    p = subprocess.run(["git", "status", "--porcelain"], cwd=str(WORKSPACE), text=True, stdout=subprocess.PIPE)
    return p.returncode == 0 and not p.stdout.strip()

def system_integrity_ok():
    p = subprocess.run(["python3", "scripts/learning-v2-system-integrity.py"], cwd=str(WORKSPACE), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode == 0 and "system_integrity = ok" in p.stdout

def main():
    policy = load_json(POLICY)
    checks = []
    failures = []
    warnings = []

    def add(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            failures.append(name + (":" + detail if detail else ""))

    add("system_integrity_ok", system_integrity_ok())
    add("git_clean", git_clean())

    for p in [ENTRYPOINT, CONTROLLED_SMOKE]:
        add("exists:" + p.name, p.exists(), str(p))
    add("runtime_origin_policy_exists", ORIGIN_POLICY.exists(), str(ORIGIN_POLICY))

    rc1, report1, out1, err1 = run([
        "python3", str(ENTRYPOINT),
        "--origin", "user_direct_with_/blxst",
        "--text", "/blxst 新增一个赛事数据表，用来记录未来HPL每一轮详细战报"
    ])
    add("runtime_unknown_resource_entrypoint", rc1 == 0 and bool(report1), report1 or "missing_report")

    rc2, report2, out2, err2 = run([
        "python3", str(ENTRYPOINT),
        "--origin", "manual_probe",
        "--text", "帮我分析这场比赛的战术"
    ])
    # Manual probe may safe-stop or be blocked; it should still produce a report and not mutate.
    add("runtime_manual_probe_safe_handled", bool(report2), report2 or "missing_report")

    rc3, report3, out3, err3 = run(["python3", str(CONTROLLED_SMOKE)])
    add("controlled_apply_readiness_smoke", rc3 == 0 and bool(report3), report3 or "missing_report")

    runtime_dry_run_ready = not failures
    controlled_apply_guard_ready = rc3 == 0 and bool(report3)

    remaining_gaps = [
        "real registry apply still disabled",
        "real D1 mutation not proven",
        "real R2 mutation not proven",
        "real Worker mutation not proven",
        "autonomous source write not proven",
        "production deploy not enabled by this readiness level"
    ]

    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-launch-readiness-auditor-v0",
        "mode": "dry_run",
        "policy": {
            "path": str(POLICY),
            "policy_id": policy.get("policy_id"),
            "policy_driven": policy.get("policy_driven"),
            "production_mutation_default": policy.get("production_mutation_default")
        },
        "launch_readiness": {
            "runtime_dry_run_ready": runtime_dry_run_ready,
            "controlled_apply_guard_ready": controlled_apply_guard_ready,
            "production_mutation_ready": False,
            "production_deploy_ready": False,
            "overall_status": "runtime_dry_run_ready" if runtime_dry_run_ready else "runtime_dry_run_blocked"
        },
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
        "remaining_gaps_before_production": remaining_gaps,
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
    jp = REPORT_DIR / f"learning-v2-launch-readiness-auditor-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-launch-readiness-auditor-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Launch Readiness Auditor\n\n"
        f"- overall_status: `{out['launch_readiness']['overall_status']}`\n"
        f"- runtime_dry_run_ready: `{str(runtime_dry_run_ready).lower()}`\n"
        f"- controlled_apply_guard_ready: `{str(controlled_apply_guard_ready).lower()}`\n"
        "- production_mutation_ready: `false`\n"
        "- production_deploy_ready: `false`\n",
        encoding="utf-8"
    )

    print("launch_readiness_auditor =", "ok" if runtime_dry_run_ready else "blocked")
    print("overall_status =", out["launch_readiness"]["overall_status"])
    print("runtime_dry_run_ready =", str(runtime_dry_run_ready).lower())
    print("controlled_apply_guard_ready =", str(controlled_apply_guard_ready).lower())
    print("production_mutation_ready = false")
    print("production_deploy_ready = false")
    print("failure_count =", len(failures))
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    raise SystemExit(0 if runtime_dry_run_ready else 1)

if __name__ == "__main__":
    main()
