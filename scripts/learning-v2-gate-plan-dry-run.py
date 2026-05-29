#!/usr/bin/env python3
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
CLASSIFIER = WORKSPACE / "scripts" / "learning-v2-resource-classifier.py"
POLICY = WORKSPACE / "projects" / "BLXST-gate-policy-registry.json"
REPORT_DIR = WORKSPACE / "learning-v2" / "reports"
SNAPSHOT_DIR = WORKSPACE / "learning-v2" / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-gate-plan-dry-run-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def run_classifier(origin, text):
    cmd = ["python3", str(CLASSIFIER), "--origin", origin, "--text", text]
    proc = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    report_json = None
    for line in proc.stdout.splitlines():
        if line.startswith("report_json ="):
            report_json = line.split("=", 1)[1].strip()
    if proc.returncode != 0 or not report_json:
        raise RuntimeError("classifier_failed_or_report_missing\nSTDOUT:\n" + proc.stdout + "\nSTDERR:\n" + proc.stderr)
    return proc, Path(report_json), load_json(report_json)

def gate_families_for_resource(policy, resource):
    out = []
    resource_type = resource.get("resource_type")
    hints = policy.get("seed_hints_non_exhaustive") or []
    for hint in hints:
        when = hint.get("when") or {}
        if when.get("resource_type") == resource_type:
            out.extend(hint.get("recommend_gate_families") or [])
    return out

def build_plan(origin, text):
    policy = load_json(POLICY)
    proc, classifier_report_path, classifier_payload = run_classifier(origin, text)

    resources = classifier_payload.get("classified_resources") or []
    authorized = bool(classifier_payload.get("authorized_context"))
    warnings = list(classifier_payload.get("warnings") or [])

    gate_families = []
    per_resource = []

    for resource in resources:
        families = gate_families_for_resource(policy, resource)
        if not families:
            families = ["review_required_gate", "registry_update_gate"]
            warnings.append("resource_without_matching_policy_hint_requires_review")
        per_resource.append({
            "resource": resource,
            "recommended_gate_families": sorted(set(families)),
            "policy_source": str(POLICY),
            "seed_hint_based": True,
            "seed_hint_is_complete_truth": False
        })
        gate_families.extend(families)

    if not resources:
        gate_families.extend(["resource_classifier_gate"])
        if not authorized:
            gate_families.append("review_required_gate")

    if not authorized:
        plan_status = "analysis_or_clarification_only"
        mutation_allowed = False
        warnings.append("authorized_context_missing_mutation_blocked")
    elif any(r.get("resource_type") == "unknown_resource_boundary" for r in resources):
        plan_status = "registry_update_or_review_required"
        mutation_allowed = False
    elif "registry_update_required" in (classifier_payload.get("recommended_gates") or []):
        plan_status = "registry_update_or_review_required"
        mutation_allowed = False
    else:
        plan_status = "gate_plan_ready_for_next_dry_run"
        mutation_allowed = False

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "mode": "dry_run",
        "input_text": text,
        "origin": origin,
        "authorized_context": authorized,
        "classifier_report": str(classifier_report_path),
        "policy_registry": {
            "path": str(POLICY),
            "registry_id": policy.get("registry_id"),
            "policy_driven": policy.get("policy_driven"),
            "examples_are_non_exhaustive": policy.get("examples_are_non_exhaustive"),
            "seed_hints_are_complete_truth": False
        },
        "plan_status": plan_status,
        "classified_resources": resources,
        "per_resource_gate_plan": per_resource,
        "recommended_gate_families": sorted(set(gate_families)),
        "warnings": sorted(set(warnings)),
        "hard_rules": policy.get("hard_rules") or [],
        "safety": {
            "planning_only": True,
            "state_written": False,
            "website_source_written": False,
            "d1_written": False,
            "r2_written": False,
            "kv_written": False,
            "worker_changed": False,
            "cloudflare_mutation": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "mutation_allowed_by_planner": mutation_allowed
        }
    }
    return payload

def write_reports(payload):
    ts = stamp()
    jp = REPORT_DIR / f"learning-v2-gate-plan-dry-run-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-gate-plan-dry-run-{ts}.md"

    jp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Gate Plan Dry Run",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- origin: `{payload['origin']}`",
        f"- authorized_context: `{str(payload['authorized_context']).lower()}`",
        f"- plan_status: `{payload['plan_status']}`",
        f"- resource_count: `{len(payload['classified_resources'])}`",
        f"- gate_families: `{', '.join(payload['recommended_gate_families'])}`",
        "- planning_only: `true`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
        "",
        "## Per Resource Gate Plan",
    ]
    if payload["per_resource_gate_plan"]:
        for item in payload["per_resource_gate_plan"]:
            r = item["resource"]
            lines.append(
                f"- `{r.get('resource_type')}` / `{r.get('name')}` / risk=`{r.get('risk')}` → "
                f"`{', '.join(item['recommended_gate_families'])}`"
            )
    else:
        lines.append("- none")
    lines += ["", "## Warnings"]
    lines += [f"- {w}" for w in payload["warnings"]] if payload["warnings"] else ["- none"]
    mp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return jp, mp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", required=True)
    ap.add_argument("--text", required=True)
    args = ap.parse_args()

    payload = build_plan(args.origin, args.text)
    jp, mp = write_reports(payload)

    print("gate_plan_dry_run = ok")
    print("authorized_context =", str(payload["authorized_context"]).lower())
    print("plan_status =", payload["plan_status"])
    print("resource_count =", len(payload["classified_resources"]))
    print("recommended_gate_families =", ",".join(payload["recommended_gate_families"]))
    print("report_json =", jp)
    print("report_md =", mp)
    print("planning_only = true")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
