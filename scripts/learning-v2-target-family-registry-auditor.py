#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REGISTRY = BASE / "target-family-registry.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

AUDITOR_ID = "learning-v2-target-family-registry-auditor-v0"

REQUIRED_SUPPORTED = {
    "quality.missing_asset_reference",
    "event.storytelling_path",
}

REQUIRED_POLICY_FALSE = [
    "website_files_changed",
    "git_commit",
    "git_push",
    "deploy",
    "restore_cloudflare_auto_deploy",
]

REQUIRED_FIELDS_BY_STATUS = {
    "supported": [
        "type",
        "lane",
        "current_support",
        "status",
    ],
    "candidate": [
        "type",
        "lane",
        "current_support",
        "status",
    ],
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"__load_error__": str(e)}

def main():
    failures = []
    warnings = []

    data = load_json(REGISTRY)
    families = data.get("families") or {}
    policy = data.get("policy") or {}

    if "__load_error__" in data:
        failures.append(f"registry_load_error:{data['__load_error__']}")

    if data.get("registry_id") != "learning-v2-target-family-registry-v0":
        warnings.append(f"unexpected_registry_id:{data.get('registry_id')}")

    for key in REQUIRED_POLICY_FALSE:
        if policy.get(key) is not False:
            failures.append(f"policy_{key}_not_false:{policy.get(key)}")

    for family in REQUIRED_SUPPORTED:
        if family not in families:
            failures.append(f"required_supported_family_missing:{family}")
        elif families[family].get("status") != "supported":
            failures.append(f"required_family_not_supported:{family}:{families[family].get('status')}")

    for name, meta in families.items():
        status = meta.get("status")
        if status not in REQUIRED_FIELDS_BY_STATUS:
            failures.append(f"unsupported_family_status:{name}:{status}")
            continue

        for field in REQUIRED_FIELDS_BY_STATUS[status]:
            if not meta.get(field):
                failures.append(f"family_missing_field:{name}:{field}")

        if status == "supported":
            for field in ["proposal_mode", "validation_mode", "plan_mode"]:
                if not meta.get(field):
                    warnings.append(f"supported_family_missing_mode_field:{name}:{field}")

            if meta.get("apply_allowed_by_default") is not False:
                failures.append(f"supported_family_apply_allowed_by_default_not_false:{name}")

            if meta.get("source_change_allowed_by_default") is not False:
                failures.append(f"supported_family_source_change_allowed_by_default_not_false:{name}")

    supported = sorted(k for k, v in families.items() if v.get("status") == "supported")
    candidates = sorted(k for k, v in families.items() if v.get("status") == "candidate")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "auditor_id": AUDITOR_ID,
        "result": result,
        "registry_path": str(REGISTRY),
        "registry_id": data.get("registry_id"),
        "family_count": len(families),
        "supported_families": supported,
        "candidate_families": candidates,
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

    out_json = REPORT_DIR / f"target-family-registry-auditor-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"target-family-registry-auditor-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Target Family Registry Auditor",
        "",
        f"- result: `{result}`",
        f"- registry_id: `{payload['registry_id']}`",
        f"- family_count: `{payload['family_count']}`",
        f"- supported_families: `{', '.join(supported)}`",
        f"- candidate_families: `{', '.join(candidates)}`",
        "",
        "## Failures",
    ]
    lines += [f"- {x}" for x in failures] if failures else ["- none"]
    lines += ["", "## Warnings"]
    lines += [f"- {x}" for x in warnings] if warnings else ["- none"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("target_family_registry_auditor =", result)
    print("registry_id =", payload["registry_id"])
    print("family_count =", payload["family_count"])
    print("supported_families =", ",".join(supported))
    print("candidate_families =", ",".join(candidates))
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
