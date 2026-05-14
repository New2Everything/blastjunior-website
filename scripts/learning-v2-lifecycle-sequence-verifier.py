#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
REGISTRY_PATH = BASE / "target-family-registry.json"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

VERIFIER_ID = "learning-v2-lifecycle-sequence-verifier-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"__load_error__": str(e), "__path__": str(path)}

def latest_report(pattern):
    files = sorted(
        REPORT_DIR.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None

def policy_false(payload, key):
    policy = payload.get("policy") or {}
    return policy.get(key) is False

def add_policy_checks(name, payload, failures):
    for key in ["website_files_changed", "git_commit", "git_push", "deploy", "restore_cloudflare_auto_deploy"]:
        if not policy_false(payload, key):
            failures.append(f"{name}_policy_{key}_not_false:{(payload.get('policy') or {}).get(key)}")

def main():
    failures = []
    warnings = []

    proposal_path = latest_report("opportunity-proposal-*.json")
    validation_path = latest_report("opportunity-validation-gate-*.json")
    plan_path = latest_report("opportunity-controlled-change-plan-*.json")
    router_path = latest_report("learning-v2-lifecycle-router-*.json")

    paths = {
        "proposal": proposal_path,
        "validation": validation_path,
        "controlled_change_plan": plan_path,
        "router": router_path,
    }

    for name, path in paths.items():
        if not path:
            failures.append(f"missing_latest_report:{name}")

    proposal = load_json(proposal_path, default={}) if proposal_path else {}
    validation = load_json(validation_path, default={}) if validation_path else {}
    plan = load_json(plan_path, default={}) if plan_path else {}
    router = load_json(router_path, default={}) if router_path else {}
    registry = load_json(REGISTRY_PATH, default={}) or {}
    families = registry.get("families") or {}

    for name, payload in [
        ("proposal", proposal),
        ("validation", validation),
        ("controlled_change_plan", plan),
        ("router", router),
        ("registry", registry),
    ]:
        if payload.get("__load_error__"):
            failures.append(f"{name}_load_error:{payload.get('__load_error__')}")

    target_family_values = {
        "proposal": proposal.get("target_family"),
        "validation": validation.get("target_family"),
        "controlled_change_plan": plan.get("target_family"),
        "router": router.get("target_family"),
    }

    unique_target_families = sorted(set(v for v in target_family_values.values() if v))
    target_family = unique_target_families[0] if len(unique_target_families) == 1 else None

    if len(unique_target_families) != 1:
        failures.append(f"target_family_mismatch:{target_family_values}")

    registry_family = families.get(target_family) if target_family else None
    if target_family and not registry_family:
        failures.append(f"target_family_not_in_registry:{target_family}")

    if registry_family:
        if registry_family.get("status") != "supported":
            failures.append(f"registry_family_not_supported:{target_family}:{registry_family.get('status')}")

        expected_current_support = registry_family.get("current_support")
        expected_type = registry_family.get("type")
        expected_lane = registry_family.get("lane")
        expected_validation_mode = registry_family.get("validation_mode")
        expected_plan_mode = registry_family.get("plan_mode")

        for name, payload in [
            ("proposal", proposal),
            ("validation", validation),
            ("controlled_change_plan", plan),
            ("router", router),
        ]:
            if payload.get("registry_family_status") != "supported":
                failures.append(f"{name}_registry_family_status_not_supported:{payload.get('registry_family_status')}")
            if payload.get("registry_current_support") != expected_current_support:
                failures.append(f"{name}_registry_current_support_mismatch:{payload.get('registry_current_support')}:{expected_current_support}")
            if payload.get("registry_type") != expected_type:
                failures.append(f"{name}_registry_type_mismatch:{payload.get('registry_type')}:{expected_type}")

        for name, payload in [
            ("proposal", proposal),
            ("validation", validation),
            ("controlled_change_plan", plan),
        ]:
            if payload.get("registry_lane") != expected_lane:
                failures.append(f"{name}_registry_lane_mismatch:{payload.get('registry_lane')}:{expected_lane}")

        if validation.get("registry_validation_mode") != expected_validation_mode:
            failures.append(f"validation_registry_validation_mode_mismatch:{validation.get('registry_validation_mode')}:{expected_validation_mode}")

        if plan.get("registry_plan_mode") != expected_plan_mode:
            failures.append(f"plan_registry_plan_mode_mismatch:{plan.get('registry_plan_mode')}:{expected_plan_mode}")

    if proposal.get("result") != "built":
        failures.append(f"proposal_result_not_built:{proposal.get('result')}")

    if proposal.get("recommended_next_stage") != "validation_gate":
        failures.append(f"proposal_next_stage_unexpected:{proposal.get('recommended_next_stage')}")

    if validation.get("result") != "ok":
        failures.append(f"validation_result_not_ok:{validation.get('result')}")

    if validation.get("recommended_next_stage") != "controlled_change_plan":
        failures.append(f"validation_next_stage_unexpected:{validation.get('recommended_next_stage')}")

    if plan.get("result") != "ok":
        failures.append(f"controlled_change_plan_result_not_ok:{plan.get('result')}")

    router_ok = router.get("result") == "ok" or router.get("lifecycle_router") == "ok"
    if not router_ok:
        failures.append(f"router_not_ok:{router.get('result') or router.get('lifecycle_router')}")

    if plan.get("recommended_next_stage") != router.get("next_allowed_stage"):
        failures.append(f"plan_router_next_stage_mismatch:{plan.get('recommended_next_stage')}:{router.get('next_allowed_stage')}")

    for name, payload in [
        ("proposal", proposal),
        ("validation", validation),
        ("controlled_change_plan", plan),
    ]:
        add_policy_checks(name, payload, failures)

    for key in ["apply_allowed", "source_change_allowed", "commit_allowed", "push_allowed", "deploy_allowed"]:
        if router.get(key) is not False:
            failures.append(f"router_{key}_not_false:{router.get(key)}")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "verifier_id": VERIFIER_ID,
        "result": result,
        "target_family": target_family,
        "source_reports": {k: str(v) if v else None for k, v in paths.items()},
        "registry_path": str(REGISTRY_PATH),
        "registry_family_status": registry_family.get("status") if registry_family else None,
        "registry_current_support": registry_family.get("current_support") if registry_family else None,
        "registry_type": registry_family.get("type") if registry_family else None,
        "registry_lane": registry_family.get("lane") if registry_family else None,
        "registry_validation_mode": registry_family.get("validation_mode") if registry_family else None,
        "registry_plan_mode": registry_family.get("plan_mode") if registry_family else None,
        "proposal_next_stage": proposal.get("recommended_next_stage"),
        "validation_next_stage": validation.get("recommended_next_stage"),
        "plan_next_stage": plan.get("recommended_next_stage"),
        "router_next_allowed_stage": router.get("next_allowed_stage"),
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

    out_json = REPORT_DIR / f"learning-v2-lifecycle-sequence-verifier-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"learning-v2-lifecycle-sequence-verifier-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Lifecycle Sequence Verifier",
        "",
        f"- result: `{result}`",
        f"- target_family: `{target_family}`",
        f"- registry_family_status: `{payload['registry_family_status']}`",
        f"- registry_current_support: `{payload['registry_current_support']}`",
        f"- registry_validation_mode: `{payload['registry_validation_mode']}`",
        f"- registry_plan_mode: `{payload['registry_plan_mode']}`",
        f"- proposal_next_stage: `{payload['proposal_next_stage']}`",
        f"- validation_next_stage: `{payload['validation_next_stage']}`",
        f"- plan_next_stage: `{payload['plan_next_stage']}`",
        f"- router_next_allowed_stage: `{payload['router_next_allowed_stage']}`",
        "",
        "## Failures",
    ]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    lines += ["", "## Warnings"]
    lines += [f"- {x}" for x in warnings] if warnings else ["- none"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("lifecycle_sequence_verifier =", result)
    print("target_family =", target_family)
    print("registry_family_status =", payload["registry_family_status"])
    print("registry_current_support =", payload["registry_current_support"])
    print("registry_validation_mode =", payload["registry_validation_mode"])
    print("registry_plan_mode =", payload["registry_plan_mode"])
    print("proposal_next_stage =", payload["proposal_next_stage"])
    print("validation_next_stage =", payload["validation_next_stage"])
    print("plan_next_stage =", payload["plan_next_stage"])
    print("router_next_allowed_stage =", payload["router_next_allowed_stage"])
    print("failure_count =", len(failures))
    print("warning_count =", len(warnings))
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("website_files_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
