#!/usr/bin/env python3
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
REVIEWER = WORKSPACE / "scripts" / "learning-v2-content-proposal-review-gate.py"
POLICY = WORKSPACE / "projects" / "BLXST-content-review-apply-policy.json"
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

def run_review(origin, text):
    p = subprocess.run(
        ["python3", str(REVIEWER), "--origin", origin, "--text", text],
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    report = None
    for line in p.stdout.splitlines():
        if line.startswith("report_json ="):
            report = line.split("=", 1)[1].strip()
    if p.returncode != 0 or not report:
        raise RuntimeError("review_failed_or_report_missing\nSTDOUT:\n" + p.stdout + "\nSTDERR:\n" + p.stderr)
    return Path(report), load_json(report)

def load_review_report(args):
    if args.input_report:
        p = Path(args.input_report)
        return p, load_json(p)
    return run_review(args.origin, args.text)

def build_apply_plan(source, payload, policy):
    review = payload.get("content_review") or {}
    allowed = bool(review.get("apply_rehearsal_allowed"))
    family = review.get("apply_rehearsal_family")
    proposal_type = review.get("proposal_type")

    blockers = []
    if not allowed:
        blockers.append("apply_rehearsal_not_allowed_by_review_gate:" + str(review.get("review_result")))

    status = "content_apply_rehearsal_ready" if not blockers else "content_apply_rehearsal_blocked"

    plan = {
        "apply_rehearsal_status": status,
        "apply_rehearsal_family": family,
        "proposal_type": proposal_type,
        "source_review_report": str(source),
        "real_apply_allowed": False,
        "mutation_allowed": False,
        "deploy_allowed": False,
        "blockers": blockers,
        "draft_apply_manifest": {
            "status": "draft_only",
            "write_now": False,
            "target_candidates_non_exhaustive": []
        },
        "validation_plan": {
            "status": "draft_only",
            "execute_now": False,
            "checks_non_exhaustive": [
                "provenance_ref_present",
                "review_gate_ready",
                "no_production_mutation",
                "post_apply_validation_required_later"
            ]
        },
        "rollback_or_recovery_note": {
            "status": "draft_only",
            "required_before_real_apply": True
        },
        "next_safe_action": "controlled_content_apply_context_required" if not blockers else "return_to_content_review_gate"
    }

    targets = plan["draft_apply_manifest"]["target_candidates_non_exhaustive"]
    if family == "event_data_and_page_apply_rehearsal":
        targets.extend(["D1 event/match tables candidate", "event page source candidate", "content provenance record candidate"])
    elif family == "event_page_apply_rehearsal":
        targets.extend(["event page source candidate", "route/navigation candidate", "content provenance record candidate"])
    elif family == "media_asset_staging_apply_rehearsal":
        targets.extend(["R2 media object candidate", "gallery/event media mapping candidate", "thumbnail/web derivative candidate"])
    elif family == "source_copy_change_apply_rehearsal":
        targets.extend(["website source copy block candidate", "preview validation candidate", "rollback diff candidate"])
    else:
        targets.extend(["review or registry handoff candidate"])

    return plan

def write_report(source, plan, policy):
    ts = stamp()
    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-content-apply-rehearsal-dry-run-v0",
        "mode": "dry_run",
        "policy": {
            "path": str(POLICY),
            "policy_id": policy.get("policy_id"),
            "policy_driven": policy.get("policy_driven"),
            "not_real_apply": policy.get("not_real_apply")
        },
        "content_apply_rehearsal": plan,
        "safety": {
            "dry_run_only": True,
            "apply_rehearsal_only": True,
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
    jp = REPORT_DIR / f"learning-v2-content-apply-rehearsal-dry-run-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-content-apply-rehearsal-dry-run-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Content Apply Rehearsal Dry-run\n\n"
        f"- apply_rehearsal_status: `{plan['apply_rehearsal_status']}`\n"
        f"- apply_rehearsal_family: `{plan['apply_rehearsal_family']}`\n"
        "- real_apply_allowed: `false`\n"
        "- mutation_allowed: `false`\n"
        "- deploy: `false`\n",
        encoding="utf-8"
    )
    return jp, mp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-report")
    ap.add_argument("--origin", default="user_direct_with_/blxst")
    ap.add_argument("--text", default="/blxst 这是HPL最新比赛记录：A队 5:3 B队，请创建赛事独立页面并更新积分。")
    args = ap.parse_args()

    policy = load_json(POLICY)
    source, payload = load_review_report(args)
    plan = build_apply_plan(source, payload, policy)
    jp, mp = write_report(source, plan, policy)

    print("content_apply_rehearsal_dry_run = ok")
    print("apply_rehearsal_status =", plan["apply_rehearsal_status"])
    print("apply_rehearsal_family =", plan["apply_rehearsal_family"])
    print("real_apply_allowed = false")
    print("mutation_allowed = false")
    print("deploy = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    raise SystemExit(0)

if __name__ == "__main__":
    main()
