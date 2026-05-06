#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "cloudflare-option-b-state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

GATE_ID = "learning-v2-cloudflare-option-b-gate-v0"

REQUIRED_TRUE_FLAGS = [
    "rollback_plan_exists",
    "pre_patch_config_verified",
    "cloudflare_patch_approved",
    "human_approved",
]

EXPECTED = {
    "option": "B",
    "project": "blastjunior-website",
    "target_setting": "production_deployments_enabled",
    "current_expected_value": True,
    "desired_temporary_value": False,
    "rollback_value": True,
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

def main():
    failures = []
    warnings = []

    if not STATE.exists():
        state = {}
        failures.append("cloudflare_option_b_state_missing")
    else:
        state = json.loads(STATE.read_text(encoding="utf-8"))

    for key, expected in EXPECTED.items():
        actual = state.get(key)
        if actual != expected:
            failures.append(f"state_mismatch:{key}:expected={expected}:actual={actual}")

    missing_true_flags = []
    for key in REQUIRED_TRUE_FLAGS:
        if state.get(key) is not True:
            missing_true_flags.append(key)
            failures.append(f"approval_flag_not_true:{key}")

    deploy_allowed = False
    git_push_allowed = False
    cloudflare_patch_allowed = not failures

    # Keep existing push/deploy gates visible and unchanged.
    safety_rc, safety_out, safety_err = run(["python3", "scripts/learning-v2-push-deploy-safety-gate.py"])
    approval_rc, approval_out, approval_err = run(["python3", "scripts/learning-v2-push-approval-gate.py"])

    result = "ok" if cloudflare_patch_allowed else "blocked"

    payload = {
        "generated_at": now_iso(),
        "gate_id": GATE_ID,
        "result": result,
        "cloudflare_patch_allowed": cloudflare_patch_allowed,
        "git_push": git_push_allowed,
        "deploy": deploy_allowed,
        "state": state,
        "required_true_flags": REQUIRED_TRUE_FLAGS,
        "missing_true_flags": missing_true_flags,
        "failures": failures,
        "warnings": warnings,
        "existing_gates": {
            "push_deploy_safety_gate_rc": safety_rc,
            "push_approval_gate_rc": approval_rc,
        },
        "policy": {
            "gate_only": True,
            "patch_cloudflare": cloudflare_patch_allowed,
            "git_push": False,
            "deploy": False,
            "manual_approval_required": True,
        },
        "recommended_next_step": (
            "Option B Cloudflare PATCH remains blocked; verify pre-patch config and record explicit human approval first"
            if result == "blocked"
            else "Option B gate ok; still perform explicit dry-run review before any Cloudflare PATCH"
        ),
    }

    out_json = REPORT_DIR / f"learning-v2-cloudflare-option-b-gate-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-cloudflare-option-b-gate-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Cloudflare Option B Gate",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- result: `{result}`",
        f"- cloudflare_patch_allowed: `{str(cloudflare_patch_allowed).lower()}`",
        "- git_push: `false`",
        "- deploy: `false`",
        "",
        "## Missing approval flags",
    ]

    if missing_true_flags:
        for key in missing_true_flags:
            lines.append(f"- `{key}`")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Failures")
    if failures:
        for item in failures:
            lines.append(f"- {item}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Recommended next step")
    lines.append(payload["recommended_next_step"])
    lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("cloudflare_option_b_gate =", result)
    print("cloudflare_patch_allowed =", str(cloudflare_patch_allowed).lower())
    print("git_push = false")
    print("deploy = false")
    print("recommended_next_step =", payload["recommended_next_step"])
    print("report_json =", out_json)
    print("report_md =", out_md)

    if missing_true_flags:
        print("missing_true_flags =", json.dumps(missing_true_flags, ensure_ascii=False))
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))

    if result == "blocked":
        raise SystemExit(2)

if __name__ == "__main__":
    main()
