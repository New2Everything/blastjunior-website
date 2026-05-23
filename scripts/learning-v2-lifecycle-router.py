#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

ROUTER_ID = "learning-v2-lifecycle-router-v0.1"
REGISTRY_PATH = BASE / "target-family-registry.json"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}

def latest(pattern):
    files = sorted(REPORT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None, {}
    return files[0], load_json(files[0])


def load_target_family_registry():
    registry = load_json(REGISTRY_PATH)
    families = registry.get("families") or {}
    return registry, families


def discovery_target(data):
    if data.get("recommended_target_family"):
        return data.get("recommended_target_family")
    c = data.get("recommended_candidate") or {}
    return c.get("target_family")

def main():
    discovery_path, discovery = latest("design-opportunity-discovery-*.json")
    evidence_path, evidence = latest("opportunity-evidence-hypothesis-*.json")
    proposal_path, proposal_payload = latest("opportunity-proposal-*.json")
    validation_path, validation = latest("opportunity-validation-gate-*.json")
    plan_path, plan_payload = latest("opportunity-controlled-change-plan-*.json")

    proposal = proposal_payload.get("proposal") or {}
    plan = plan_payload.get("plan") or {}

    target_family = (
        plan_payload.get("target_family")
        or validation.get("target_family")
        or proposal_payload.get("target_family")
        or evidence.get("target_family")
        or discovery_target(discovery)
    )

    registry, registry_families = load_target_family_registry()
    registry_family = registry_families.get(target_family) or {}

    warnings = []
    failures = []

    if target_family and not registry_family:
        warnings.append(f"target_family_not_in_registry:{target_family}")

    report_targets = {
        "discovery": discovery_target(discovery),
        "evidence": evidence.get("target_family"),
        "proposal": proposal_payload.get("target_family"),
        "validation": validation.get("target_family"),
        "plan": plan_payload.get("target_family"),
    }

    for name, value in report_targets.items():
        if value and target_family and value != target_family:
            warnings.append(f"target_family_mismatch:{name}:{value}")

    lifecycle_stage = "no_candidate"
    next_allowed_stage = "design_opportunity_discovery"

    if discovery_target(discovery):
        lifecycle_stage = "candidate_discovered"
        next_allowed_stage = "evidence_hypothesis"

    if evidence.get("result") == "built" and evidence.get("target_family") == target_family:
        lifecycle_stage = "evidence_hypothesis_built"
        next_allowed_stage = "proposal"

    if proposal_payload.get("result") == "built" and proposal_payload.get("target_family") == target_family:
        lifecycle_stage = "proposal_built"
        next_allowed_stage = "validation_gate"

    if validation.get("result") == "ok" and validation.get("target_family") == target_family:
        lifecycle_stage = "validation_passed"
        next_allowed_stage = validation.get("recommended_next_stage") or "controlled_change_plan"

    if plan_payload.get("result") == "ok" and plan_payload.get("target_family") == target_family:
        lifecycle_stage = "controlled_change_plan_ready"
        next_allowed_stage = plan_payload.get("recommended_next_stage") or "review"

    change_type = plan.get("change_type")
    files_to_change = plan_payload.get("files_to_change") or validation.get("files_to_change") or []

    apply_allowed = False
    source_change_allowed = False

    if change_type == "proposal_only_no_source_change":
        apply_allowed = False
        source_change_allowed = False
        next_allowed_stage = "design_review_or_implementation_readiness"
    elif lifecycle_stage == "controlled_change_plan_ready":
        apply_allowed = False
        source_change_allowed = False
        warnings.append("controlled_plan_exists_but_apply_requires_autonomous_policy_gate")

    forbidden_actions = [
        "do_not_edit_public_files_without_source_change_gate",
        "do_not_apply_without_autonomous_policy_gate",
        "do_not_commit_without_dedicated_commit_gate",
        "do_not_push_without_push_approval_gate",
        "do_not_deploy",
        "do_not_restore_cloudflare_auto_deploy",
    ]

    allowed_actions = [
        "read_reports",
        "generate_snapshots",
        "run_agent_status",
        "run_system_integrity",
    ]

    if next_allowed_stage in ["evidence_hypothesis", "proposal", "validation_gate", "controlled_change_plan"]:
        allowed_actions.append(f"run_{next_allowed_stage}")

    if next_allowed_stage == "design_review_or_implementation_readiness":
        allowed_actions.append("prepare_design_review_or_readiness_report")

    payload = {
        "generated_at": now_iso(),
        "router_id": ROUTER_ID,
        "result": "ok" if not failures else "blocked",
        "target_family": target_family,
        "registry_family_status": registry_family.get("status"),
        "registry_current_support": registry_family.get("current_support"),
        "registry_type": registry_family.get("type"),
        "registry_lane": registry_family.get("lane"),
        "registry_path": str(REGISTRY_PATH),
        "lifecycle_stage": lifecycle_stage,
        "next_allowed_stage": next_allowed_stage,
        "apply_allowed": apply_allowed,
        "source_change_allowed": source_change_allowed,
        "commit_allowed": False,
        "push_allowed": False,
        "deploy_allowed": False,
        "files_to_change": files_to_change,
        "plan_change_type": change_type,
        "report_paths": {
            "discovery": str(discovery_path) if discovery_path else None,
            "evidence": str(evidence_path) if evidence_path else None,
            "proposal": str(proposal_path) if proposal_path else None,
            "validation": str(validation_path) if validation_path else None,
            "plan": str(plan_path) if plan_path else None,
        },
        "report_targets": report_targets,
        "allowed_actions": allowed_actions,
        "forbidden_actions": forbidden_actions,
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "dry_run_only": True,
            "website_files_changed": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
        },
    }

    out_json = REPORT_DIR / f"learning-v2-lifecycle-router-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-lifecycle-router-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Lifecycle Router",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- result: `{payload['result']}`",
        f"- target_family: `{target_family}`",
        f"- registry_family_status: `{registry_family.get('status')}`",
        f"- registry_current_support: `{registry_family.get('current_support')}`",
        f"- registry_type: `{registry_family.get('type')}`",
        f"- lifecycle_stage: `{lifecycle_stage}`",
        f"- next_allowed_stage: `{next_allowed_stage}`",
        f"- apply_allowed: `{str(apply_allowed).lower()}`",
        f"- source_change_allowed: `{str(source_change_allowed).lower()}`",
        f"- commit_allowed: `false`",
        f"- push_allowed: `false`",
        f"- deploy_allowed: `false`",
        "",
        "## Allowed Actions",
    ]

    for item in allowed_actions:
        lines.append(f"- {item}")

    lines += ["", "## Forbidden Actions"]
    for item in forbidden_actions:
        lines.append(f"- {item}")

    lines += ["", "## Warnings"]
    lines += [f"- {w}" for w in warnings] if warnings else ["- none"]

    lines += ["", "## Failures"]
    lines += [f"- {f}" for f in failures] if failures else ["- none"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("lifecycle_router =", payload["result"])
    print("target_family =", target_family)
    print("registry_family_status =", registry_family.get("status"))
    print("registry_current_support =", registry_family.get("current_support"))
    print("registry_type =", registry_family.get("type"))
    print("lifecycle_stage =", lifecycle_stage)
    print("next_allowed_stage =", next_allowed_stage)
    print("apply_allowed =", str(apply_allowed).lower())
    print("source_change_allowed =", str(source_change_allowed).lower())
    print("commit_allowed = false")
    print("push_allowed = false")
    print("deploy_allowed = false")
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("website_files_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    if warnings:
        print("warnings =", json.dumps(warnings, ensure_ascii=False))
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
