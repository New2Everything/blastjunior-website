#!/usr/bin/env python3
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
ROUTER = WORKSPACE / "scripts" / "learning-v2-runtime-intake-router-dry-run.py"
POLICY = WORKSPACE / "projects" / "BLXST-content-proposal-factory-policy.json"
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

def run_router(origin, text):
    p = subprocess.run(
        ["python3", str(ROUTER), "--origin", origin, "--text", text],
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
        raise RuntimeError("router_failed_or_report_missing\nSTDOUT:\n" + p.stdout + "\nSTDERR:\n" + p.stderr)
    return Path(report), load_json(report)

def load_router_report(args):
    if args.input_report:
        p = Path(args.input_report)
        return p, load_json(p)
    return run_router(args.origin, args.text)

def build_proposal(source, router_payload, policy):
    selected = router_payload.get("selected_route") or {}
    route = selected.get("selected_route")
    route_family = selected.get("content_family")
    shapes = policy.get("proposal_shapes_non_exhaustive") or {}
    spec = shapes.get(route)

    warnings = []
    if not spec:
        spec = shapes.get("review_gate_dry_run", {
            "proposal_type": "review_gate_proposal",
            "allowed_effect": "review_only",
            "requires_review_before_apply": True
        })
        warnings.append("unknown_selected_route_defaulted_to_review:" + str(route))
        route = "review_gate_dry_run"
        route_family = "unknown_content"

    proposal_type = spec.get("proposal_type")
    source_intake = router_payload.get("source_intake_report")
    review_required = bool(spec.get("requires_review_before_apply", True))

    content_proposal = {
        "proposal_status": "content_proposal_ready" if not warnings else "content_proposal_review_required",
        "proposal_type": proposal_type,
        "source_route_report": str(source),
        "source_intake_report": source_intake,
        "source_selected_route": selected,
        "route_family": route_family,
        "provenance_ref": source_intake,
        "review_status": "review_required",
        "mutation_allowed": False,
        "deploy_allowed": False,
        "allowed_effect": spec.get("allowed_effect"),
        "requires_review_before_apply": review_required,
        "warnings": warnings,
        "proposal_body": {
            "status": "draft_only",
            "write_now": False,
            "fields_non_exhaustive": []
        },
        "next_safe_action": "content_review_gate_dry_run"
    }

    if proposal_type == "event_data_and_page_proposal":
        content_proposal["proposal_body"]["fields_non_exhaustive"] = [
            "event_or_season_candidate",
            "match_record_candidates",
            "team_candidates",
            "score_candidates",
            "event_page_candidate",
            "d1_target_candidate",
            "review_required_before_publish"
        ]
    elif proposal_type == "event_page_proposal":
        content_proposal["proposal_body"]["fields_non_exhaustive"] = [
            "page_slug_candidate",
            "event_context",
            "source_content_refs",
            "page_sections_candidate",
            "review_required_before_publish"
        ]
    elif proposal_type == "media_asset_staging_proposal":
        content_proposal["proposal_body"]["fields_non_exhaustive"] = [
            "media_asset_refs",
            "r2_target_candidate",
            "gallery_or_event_page_candidate",
            "caption_or_alt_text_candidate",
            "review_required_before_publish"
        ]
    elif proposal_type == "source_copy_change_proposal":
        content_proposal["proposal_body"]["fields_non_exhaustive"] = [
            "target_page_candidate",
            "copy_block_candidate",
            "replacement_text_candidate",
            "review_required_before_publish"
        ]
    elif proposal_type == "registry_update_handoff_proposal":
        content_proposal["proposal_body"]["fields_non_exhaustive"] = [
            "resource_type_candidate",
            "registry_or_policy_target_candidate",
            "handoff_to_registry_update_proposal",
            "review_required_before_apply"
        ]
        content_proposal["next_safe_action"] = "registry_update_proposal_dry_run"
    else:
        content_proposal["proposal_body"]["fields_non_exhaustive"] = [
            "review_reason",
            "clarification_needed",
            "safe_stop_before_mutation"
        ]
        content_proposal["next_safe_action"] = "review_gate_dry_run"

    return content_proposal

def write_report(source, proposal, policy):
    ts = stamp()
    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-content-proposal-factory-dry-run-v0",
        "mode": "dry_run",
        "policy": {
            "path": str(POLICY),
            "policy_id": policy.get("policy_id"),
            "policy_driven": policy.get("policy_driven"),
            "examples_are_non_exhaustive": policy.get("examples_are_non_exhaustive")
        },
        "content_proposal": proposal,
        "safety": {
            "dry_run_only": True,
            "proposal_only": True,
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
    jp = REPORT_DIR / f"learning-v2-content-proposal-factory-dry-run-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-content-proposal-factory-dry-run-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Content Proposal Factory Dry-run\n\n"
        f"- proposal_status: `{proposal['proposal_status']}`\n"
        f"- proposal_type: `{proposal['proposal_type']}`\n"
        f"- review_status: `{proposal['review_status']}`\n"
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
    source, router_payload = load_router_report(args)
    proposal = build_proposal(source, router_payload, policy)
    jp, mp = write_report(source, proposal, policy)

    print("content_proposal_factory_dry_run = ok")
    print("proposal_status =", proposal["proposal_status"])
    print("proposal_type =", proposal["proposal_type"])
    print("next_safe_action =", proposal["next_safe_action"])
    print("review_status =", proposal["review_status"])
    print("mutation_allowed = false")
    print("deploy = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    raise SystemExit(0)

if __name__ == "__main__":
    main()
