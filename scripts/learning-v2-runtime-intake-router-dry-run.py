#!/usr/bin/env python3
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
INTAKE = WORKSPACE / "scripts" / "learning-v2-runtime-intake-envelope-dry-run.py"
ROUTER_POLICY = WORKSPACE / "projects" / "BLXST-runtime-intake-router-policy.json"
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

def run_intake(origin, text, source_type):
    p = subprocess.run(
        ["python3", str(INTAKE), "--origin", origin, "--text", text, "--source-type", source_type],
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
        return None, p.stdout, p.stderr
    return Path(report), p.stdout, p.stderr

def load_intake(args):
    if args.input_report:
        p = Path(args.input_report)
        return p, load_json(p)
    p, stdout, stderr = run_intake(args.origin, args.text, args.source_type)
    if not p:
        raise RuntimeError("intake_failed_or_report_missing\nSTDOUT:\n" + stdout + "\nSTDERR:\n" + stderr)
    return p, load_json(p)

def choose_route(intake_payload, policy):
    envelope = intake_payload.get("intake_envelope") or {}
    candidates = envelope.get("content_family_candidates") or []
    families = [c.get("family") for c in candidates if c.get("family")]
    routes = policy.get("routes_non_exhaustive") or {}
    priority = policy.get("route_priority_non_exhaustive") or []

    route_candidates = []
    warnings = []

    for family in families:
        spec = routes.get(family)
        if spec:
            route_candidates.append({
                "content_family": family,
                "selected_route": spec.get("selected_route"),
                "allowed_effect": spec.get("allowed_effect"),
                "requires_review_before_apply": spec.get("requires_review_before_apply"),
                "policy_matched": True
            })
        else:
            warnings.append("content_family_without_policy_route:" + str(family))

    if not route_candidates:
        spec = routes.get("unknown_content", {})
        route_candidates.append({
            "content_family": "unknown_content",
            "selected_route": spec.get("selected_route", "review_gate_dry_run"),
            "allowed_effect": spec.get("allowed_effect", "review_only"),
            "requires_review_before_apply": True,
            "policy_matched": True
        })
        warnings.append("fallback_to_unknown_content_review")

    def rank(item):
        fam = item.get("content_family")
        try:
            return priority.index(fam)
        except ValueError:
            return 999

    selected = sorted(route_candidates, key=rank)[0]

    status = "intake_route_ready"
    if envelope.get("review_status") != "review_required":
        warnings.append("unexpected_review_status:" + str(envelope.get("review_status")))
    if envelope.get("mutation_allowed") is not False:
        status = "intake_route_blocked_unsafe_envelope"
        warnings.append("intake_envelope_mutation_allowed_not_false")
    if selected.get("content_family") == "unknown_content":
        status = "intake_route_safe_stop_review_required"

    return status, selected, route_candidates, warnings

def write_report(source, intake_payload, status, selected, candidates, warnings, policy):
    ts = stamp()
    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-runtime-intake-router-dry-run-v0",
        "mode": "dry_run",
        "source_intake_report": str(source),
        "policy": {
            "path": str(ROUTER_POLICY),
            "policy_id": policy.get("policy_id"),
            "policy_driven": policy.get("policy_driven"),
            "examples_are_non_exhaustive": policy.get("examples_are_non_exhaustive")
        },
        "route_status": status,
        "selected_route": selected,
        "route_candidates": candidates,
        "warnings": sorted(set(warnings)),
        "review_required": True,
        "mutation_allowed": False,
        "deploy_allowed": False,
        "safety": {
            "dry_run_only": True,
            "route_proposal_only": True,
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

    jp = REPORT_DIR / f"learning-v2-runtime-intake-router-dry-run-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-runtime-intake-router-dry-run-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Runtime Intake Router Dry-run\n\n"
        f"- route_status: `{status}`\n"
        f"- selected_route: `{selected.get('selected_route')}`\n"
        f"- content_family: `{selected.get('content_family')}`\n"
        "- review_required: `true`\n"
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
    ap.add_argument("--source-type", default="user_submitted")
    args = ap.parse_args()

    policy = load_json(ROUTER_POLICY)
    source, intake_payload = load_intake(args)
    status, selected, candidates, warnings = choose_route(intake_payload, policy)
    jp, mp = write_report(source, intake_payload, status, selected, candidates, warnings, policy)

    print("runtime_intake_router_dry_run =", "ok")
    print("route_status =", status)
    print("selected_route =", selected.get("selected_route"))
    print("content_family =", selected.get("content_family"))
    print("review_required = true")
    print("mutation_allowed = false")
    print("deploy = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    raise SystemExit(0)

if __name__ == "__main__":
    main()
