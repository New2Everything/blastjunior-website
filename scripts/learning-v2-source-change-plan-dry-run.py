#!/usr/bin/env python3
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
STATE = BASE / "state.json"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-source-change-plan-dry-run-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    if default is None:
        default = {}
    try:
        p = Path(path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_load_error": str(e), "_path": str(path)}
    return default

def latest_report(pattern):
    files = sorted(REPORT_DIR.glob(pattern))
    return files[-1] if files else None

def file_info(rel):
    p = WORKSPACE / rel
    if not p.exists() or not p.is_file():
        return {
            "path": rel,
            "exists": False,
            "sha256": None,
            "size_bytes": None,
        }
    data = p.read_bytes()
    return {
        "path": rel,
        "exists": True,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
    }

def normalize_surface(surface):
    mapping = {
        "public/index.html": "public/index.html",
        "public/styles.css": "public/styles.css",
        "components/nav.html": "components/nav.html",
        "gallery.html": "public/gallery.html",
        "news.html": "public/news.html",
        "profile.html": "public/profile.html",
    }
    if surface in mapping:
        return mapping[surface]
    return None

def build_file_plan(rel, linked_targets):
    if rel == "public/index.html":
        return {
            "path": rel,
            "change_intent": "Clarify first-screen action hierarchy and connect homepage/community/event entry paths.",
            "planned_operations": [
                "Inspect existing first-screen hero / CTA structure.",
                "Prepare a minimal content hierarchy adjustment plan.",
                "Avoid layout rewrite unless evidence proves necessary.",
                "Keep HADO / Lanxing identity and existing navigation stable.",
            ],
            "acceptance_checks": [
                "Homepage first action is visible without scrolling on desktop.",
                "Homepage first action is understandable for parent/student visitors.",
                "Event/community entry does not compete with primary CTA.",
                "No duplicate CTA blocks are introduced.",
            ],
            "risk": "medium",
        }

    if rel == "components/nav.html":
        return {
            "path": rel,
            "change_intent": "Review whether navigation supports the first-success path without increasing mobile density.",
            "planned_operations": [
                "Inspect current nav labels and order.",
                "Do not add new nav items unless mobile evidence allows it.",
                "Prefer clarifying existing labels over expanding navigation.",
            ],
            "acceptance_checks": [
                "No new mobile overflow risk.",
                "Existing login/profile/gallery paths remain reachable.",
                "Navigation change, if any, is reversible.",
            ],
            "risk": "medium",
        }

    if rel == "public/gallery.html":
        return {
            "path": rel,
            "change_intent": "Check whether gallery can support community/event proof after first action.",
            "planned_operations": [
                "Inspect whether gallery acts as proof of activity.",
                "Do not modify media loading or performance-sensitive logic in first pass.",
            ],
            "acceptance_checks": [
                "No change to image loading behavior.",
                "No regression to poster/gallery performance.",
            ],
            "risk": "medium",
        }

    if rel == "public/news.html":
        return {
            "path": rel,
            "change_intent": "Check whether event entry information belongs in news/event surfaces or should remain homepage-only.",
            "planned_operations": [
                "Inspect current event/news content structure.",
                "Defer any change if event pages are not clearly present.",
            ],
            "acceptance_checks": [
                "No broken links.",
                "No duplicate event explanation.",
            ],
            "risk": "low-medium",
        }

    if rel == "public/profile.html":
        return {
            "path": rel,
            "change_intent": "Check whether profile is part of first-success path or should be excluded.",
            "planned_operations": [
                "Inspect if profile requires login and should not be primary first-success path.",
                "Likely defer profile edits unless evidence says otherwise.",
            ],
            "acceptance_checks": [
                "No auth/session behavior changes.",
                "No token/localStorage behavior changes.",
            ],
            "risk": "medium",
        }

    if rel == "public/styles.css":
        return {
            "path": rel,
            "change_intent": "Only plan minimal style support if content hierarchy requires it.",
            "planned_operations": [
                "Avoid broad visual redesign.",
                "Prefer existing CSS classes and patterns.",
                "No color/theme changes in first pass.",
            ],
            "acceptance_checks": [
                "Desktop and mobile remain readable.",
                "No global CSS regression.",
            ],
            "risk": "medium",
        }

    return {
        "path": rel,
        "change_intent": "Unclassified candidate file; inspect before planning.",
        "planned_operations": ["Inspect only."],
        "acceptance_checks": ["No write without explicit plan."],
        "risk": "unknown",
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Reserved; v0 is report-only and never edits website source.")
    args = ap.parse_args()

    policy_path = latest_report("learning-v2-autonomous-review-policy-dry-run-*.json")
    packet_path = latest_report("learning-v2-consolidated-source-change-review-packet-dry-run-*.json")

    if not policy_path:
        raise SystemExit("no autonomous review policy report found")
    if not packet_path:
        raise SystemExit("no consolidated source-change review packet found")

    policy = load_json(policy_path, {})
    packet = load_json(packet_path, {})

    if policy.get("source_change_plan_dry_run_allowed") is not True:
        raise SystemExit("source-change plan dry-run is not allowed by autonomous policy")
    if policy.get("source_change_gate_allowed") is not False:
        raise SystemExit("unexpected: autonomous policy allows source_change_gate too early")

    scope = packet.get("proposed_review_scope") or {}
    records = packet.get("records") or []
    raw_surfaces = scope.get("included_surfaces") or []

    normalized = []
    unresolved = []

    target_by_surface = {}
    for r in records:
        for s in r.get("candidate_surfaces") or []:
            target_by_surface.setdefault(s, []).append(r.get("target_family"))

    for s in raw_surfaces:
        rel = normalize_surface(s)
        if rel:
            normalized.append({
                "surface": s,
                "path": rel,
                "linked_targets": target_by_surface.get(s, []),
            })
        else:
            unresolved.append({
                "surface": s,
                "reason": "not a concrete file path or not mapped in v0",
            })

    dedup_paths = []
    seen = set()
    for x in normalized:
        if x["path"] not in seen:
            seen.add(x["path"])
            dedup_paths.append(x["path"])

    file_snapshots = [file_info(rel) for rel in dedup_paths]
    missing_files = [x["path"] for x in file_snapshots if not x["exists"]]

    file_plans = []
    for rel in dedup_paths:
        linked = []
        for x in normalized:
            if x["path"] == rel:
                linked.extend(x.get("linked_targets") or [])
        file_plans.append({
            "file": file_info(rel),
            "linked_targets": sorted(set(linked)),
            "plan": build_file_plan(rel, sorted(set(linked))),
        })

    by_risk = Counter(x["plan"]["risk"] for x in file_plans)

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run",
        "apply": bool(args.apply),
        "autonomous_policy_source": str(policy_path),
        "consolidated_packet_source": str(packet_path),
        "decision": "source_change_plan_dry_run_ready",
        "recommended_next_action": "audit_source_change_plan_before_any_gate_or_website_write",
        "source_change_plan_dry_run_allowed": True,
        "source_change_gate_allowed": False,
        "record_count": len(records),
        "candidate_file_count": len(dedup_paths),
        "missing_file_count": len(missing_files),
        "missing_files": missing_files,
        "unresolved_surfaces": unresolved,
        "file_plans": file_plans,
        "by_risk": dict(by_risk),
        "required_before_any_apply": [
            "source-change plan auditor passes",
            "file-level patch preview exists",
            "pre-change hashes captured",
            "rollback plan exists",
            "post-validation checklist exists",
            "source_change_gate explicitly opens in a later step"
        ],
        "safety": {
            "state_written": False,
            "business_source_written": False,
            "website_source_written": False,
            "source_change_gate_opened": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
    }

    ts = stamp()
    json_path = REPORT_DIR / f"learning-v2-source-change-plan-dry-run-{ts}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-source-change-plan-dry-run-{ts}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Source-Change Plan Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- decision: `{payload['decision']}`")
    md.append(f"- recommended_next_action: `{payload['recommended_next_action']}`")
    md.append(f"- candidate_file_count: `{payload['candidate_file_count']}`")
    md.append(f"- missing_file_count: `{payload['missing_file_count']}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## File Plans")
    md.append("")
    for fp in file_plans:
        info = fp["file"]
        plan = fp["plan"]
        md.append(f"### {info['path']}")
        md.append("")
        md.append(f"- exists: `{str(info['exists']).lower()}`")
        md.append(f"- sha256: `{info['sha256']}`")
        md.append(f"- risk: `{plan['risk']}`")
        md.append(f"- change_intent: {plan['change_intent']}")
        md.append("- planned_operations:")
        for op in plan["planned_operations"]:
            md.append(f"  - {op}")
        md.append("- acceptance_checks:")
        for check in plan["acceptance_checks"]:
            md.append(f"  - {check}")
        md.append("")
    md.append("## Unresolved Surfaces")
    md.append("")
    if unresolved:
        for x in unresolved:
            md.append(f"- `{x['surface']}`: {x['reason']}")
    else:
        md.append("- none")
    md.append("")
    md.append("## Required Before Any Apply")
    md.append("")
    for x in payload["required_before_any_apply"]:
        md.append(f"- {x}")
    md.append("")
    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("source_change_plan_dry_run = ok")
    print("mode = dry_run")
    print("decision = source_change_plan_dry_run_ready")
    print("recommended_next_action = audit_source_change_plan_before_any_gate_or_website_write")
    print("candidate_file_count =", len(dedup_paths))
    print("missing_file_count =", len(missing_files))
    print("missing_files =", json.dumps(missing_files, ensure_ascii=False))
    print("unresolved_surfaces =", json.dumps(unresolved, ensure_ascii=False))
    print("by_risk =", json.dumps(dict(by_risk), ensure_ascii=False))
    print("source_change_gate_allowed = false")
    print("source_change_gate_opened = false")
    print("state_written = false")
    print("business_source_written = false")
    print("website_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("report_json =", json_path)
    print("report_md =", md_path)

if __name__ == "__main__":
    raise SystemExit(main())
