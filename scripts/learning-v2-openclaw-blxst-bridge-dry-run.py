#!/usr/bin/env python3
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
ENTRYPOINT = WORKSPACE / "scripts" / "learning-v2-runtime-entrypoint-dry-run.py"
ORIGIN_POLICY = WORKSPACE / "projects" / "BLXST-runtime-origin-policy.json"
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

def run_entrypoint(origin, text):
    p = subprocess.run(
        ["python3", str(ENTRYPOINT), "--origin", origin, "--text", text],
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    report = None
    for line in p.stdout.splitlines():
        if line.startswith("report_json ="):
            report = line.split("=", 1)[1].strip()
    return p.returncode, report, p.stdout, p.stderr

def infer_origin(text, explicit_origin):
    if explicit_origin:
        return explicit_origin
    if text.strip().startswith("/blxst"):
        return "user_direct_with_/blxst"
    return "manual_probe"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--origin")
    args = ap.parse_args()

    policy = load_json(ORIGIN_POLICY)
    origins = policy.get("authorized_origins") or {}
    origin = infer_origin(args.text, args.origin)

    warnings = []
    if origin not in origins:
        status = "bridge_safe_stop_authorization_required"
        entry_report = None
        rc = 0
        hard = []
        warnings.append("origin_not_authorized_by_policy:" + origin)
    else:
        spec = origins[origin]
        if spec.get("requires_prefix") == "/blxst" and not args.text.strip().startswith("/blxst"):
            warnings.append("origin_requires_blxst_prefix")
        rc, entry_report, stdout, stderr = run_entrypoint(origin, args.text)
        status = "bridge_entrypoint_completed" if rc == 0 and entry_report else "bridge_entrypoint_blocked"
        hard = [] if rc == 0 and entry_report else ["entrypoint_failed_or_report_missing"]

    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-openclaw-blxst-bridge-dry-run-v0",
        "mode": "dry_run",
        "input_text": args.text,
        "origin": origin,
        "origin_authorized_by_policy": origin in origins,
        "bridge_status": status,
        "source_entrypoint_report": entry_report,
        "warnings": warnings,
        "hard_failures": hard,
        "safety": {
            "dry_run_only": True,
            "bridge_only": True,
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
    jp = REPORT_DIR / f"learning-v2-openclaw-blxst-bridge-dry-run-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-openclaw-blxst-bridge-dry-run-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 OpenClaw BLXST Bridge Dry-run\n\n"
        f"- bridge_status: `{status}`\n"
        f"- origin: `{origin}`\n"
        f"- origin_authorized_by_policy: `{str(origin in origins).lower()}`\n"
        f"- hard_failure_count: `{len(hard)}`\n"
        "- deploy: `false`\n",
        encoding="utf-8"
    )

    print("openclaw_blxst_bridge_dry_run =", "ok" if not hard else "blocked")
    print("bridge_status =", status)
    print("origin =", origin)
    print("origin_authorized_by_policy =", str(origin in origins).lower())
    print("hard_failure_count =", len(hard))
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    raise SystemExit(0 if not hard else 1)

if __name__ == "__main__":
    main()
