#!/usr/bin/env python3
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
INTAKE_POLICY = WORKSPACE / "projects" / "BLXST-runtime-intake-policy.json"
ORIGIN_POLICY = WORKSPACE / "projects" / "BLXST-runtime-origin-policy.json"
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

def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def classify_families(text, policy):
    low = text.lower()
    families = []
    for family, spec in (policy.get("content_families_non_exhaustive") or {}).items():
        hints = spec.get("seed_hints_non_exhaustive") or []
        if any(h.lower() in low for h in hints):
            families.append({
                "family": family,
                "matched_by_seed_hint": True,
                "recommended_next_family": spec.get("recommended_next_family")
            })
    if not families:
        spec = (policy.get("content_families_non_exhaustive") or {}).get("unknown_content") or {}
        families.append({
            "family": "unknown_content",
            "matched_by_seed_hint": False,
            "recommended_next_family": spec.get("recommended_next_family", "review_gate_dry_run")
        })
    return families

def evaluate_origin(origin, text, origin_policy):
    origins = origin_policy.get("authorized_origins") or {}
    warnings = []
    if origin not in origins:
        return False, ["origin_not_authorized_by_policy:" + origin]
    spec = origins.get(origin) or {}
    if spec.get("requires_prefix") == "/blxst" and not text.strip().startswith("/blxst"):
        warnings.append("origin_requires_blxst_prefix")
    return True, warnings

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--source-type", default="user_submitted")
    ap.add_argument("--submission-ref", default="")
    args = ap.parse_args()

    intake_policy = load_json(INTAKE_POLICY)
    origin_policy = load_json(ORIGIN_POLICY)

    origin_ok, origin_warnings = evaluate_origin(args.origin, args.text, origin_policy)
    source_types = intake_policy.get("source_types_non_exhaustive") or {}
    source_ok = args.source_type in source_types
    families = classify_families(args.text, intake_policy)

    warnings = list(origin_warnings)
    blockers = []
    if not origin_ok:
        blockers.append("authorized_origin_missing")
    if not source_ok:
        blockers.append("unknown_source_type:" + args.source_type)

    if any(f["family"] == "unknown_content" for f in families):
        warnings.append("unknown_content_family_requires_review")

    envelope_status = "intake_envelope_ready" if not blockers else "intake_safe_stop_review_required"
    review_status = "review_required"

    recommended = sorted(set(f.get("recommended_next_family") for f in families if f.get("recommended_next_family")))

    envelope = {
        "origin": args.origin,
        "origin_authorized": origin_ok,
        "source_type": args.source_type if source_ok else "unknown",
        "submission_ref": args.submission_ref or ("runtime_text_sha256:" + sha256_text(args.text)[:16]),
        "content_hash": sha256_text(args.text),
        "content_length": len(args.text),
        "content_family_candidates": families,
        "recommended_next_families": recommended,
        "provenance_note": "User/OpenClaw intake envelope. This does not publish or mutate production data.",
        "review_status": review_status,
        "mutation_allowed": False,
        "deploy_allowed": False,
        "blockers": blockers,
        "warnings": warnings
    }

    out = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-runtime-intake-envelope-dry-run-v0",
        "mode": "dry_run",
        "policy": {
            "path": str(INTAKE_POLICY),
            "policy_id": intake_policy.get("policy_id"),
            "policy_driven": intake_policy.get("policy_driven"),
            "examples_are_non_exhaustive": intake_policy.get("examples_are_non_exhaustive")
        },
        "intake_status": envelope_status,
        "intake_envelope": envelope,
        "safety": {
            "dry_run_only": True,
            "envelope_only": True,
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
    jp = REPORT_DIR / f"learning-v2-runtime-intake-envelope-dry-run-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-runtime-intake-envelope-dry-run-{ts}.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Runtime Intake Envelope Dry-run\n\n"
        f"- intake_status: `{envelope_status}`\n"
        f"- source_type: `{envelope['source_type']}`\n"
        f"- review_status: `{review_status}`\n"
        f"- mutation_allowed: `false`\n"
        f"- deploy_allowed: `false`\n",
        encoding="utf-8"
    )

    print("runtime_intake_envelope_dry_run =", "ok" if not blockers else "review_required")
    print("intake_status =", envelope_status)
    print("content_families =", ",".join(f["family"] for f in families))
    print("review_status =", review_status)
    print("mutation_allowed = false")
    print("deploy = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    raise SystemExit(0)

if __name__ == "__main__":
    main()
