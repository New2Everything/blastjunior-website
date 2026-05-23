#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

POLICY = Path("learning-v2/deployment-policy.json")
REPORTS = Path("learning-v2/reports")
RUNTIME = Path("learning-v2/runtime")
REPORTS.mkdir(parents=True, exist_ok=True)
RUNTIME.mkdir(parents=True, exist_ok=True)

REQUIRED_PHRASES = [
    "GitHub is the source of truth",
    "Cloudflare Pages is the deployment target",
    "guarded source-change lifecycle",
    "No direct Cloudflare deploy unless emergency override is explicitly enabled",
]

REQUIRED_ROUTE = [
    "OpenClaw / learning-v2 modifies local repository files",
    "local validation",
    "rollback packet",
    "git diff audit",
    "commit gate",
    "push gate",
    "git push to GitHub",
    "Cloudflare Pages Git integration auto deploy",
    "post-deploy observer",
]

BLOCKED_PRIMARY = [
    "direct Cloudflare Pages upload",
    "wrangler deploy as normal route",
    "Cloudflare API mutation as normal route",
    "editing deployed site without GitHub source update",
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

hard_blocks = []
warnings = []

if not POLICY.exists():
    hard_blocks.append("deployment_policy_missing")
    policy = {}
else:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))

law = policy.get("production_route_iron_law") or {}
rule = law.get("rule") or ""
route = law.get("canonical_route") or []
blocked = law.get("blocked_as_primary_route") or []
emergency = law.get("emergency_override") or {}

for phrase in REQUIRED_PHRASES:
    if phrase not in rule:
        hard_blocks.append(f"missing_required_rule_phrase:{phrase}")

for item in REQUIRED_ROUTE:
    if item not in route:
        hard_blocks.append(f"missing_canonical_route_step:{item}")

for item in BLOCKED_PRIMARY:
    if item not in blocked:
        hard_blocks.append(f"missing_blocked_primary_route:{item}")

if emergency.get("allowed") is not False:
    hard_blocks.append("emergency_override_must_default_false")

if emergency.get("requires_explicit_policy_change") is not True:
    hard_blocks.append("emergency_override_must_require_explicit_policy_change")

if emergency.get("requires_named_emergency_mode") is not True:
    hard_blocks.append("emergency_override_must_require_named_emergency_mode")

if emergency.get("requires_post_restore_to_github_source_of_truth") is not True:
    hard_blocks.append("emergency_override_must_require_github_restore")

status = "passed" if not hard_blocks else "blocked"

out = {
    "generated_at": now_iso(),
    "auditor_id": "learning-v2-production-route-iron-law-auditor-v0",
    "audit_status": status,
    "policy": str(POLICY),
    "rule": rule,
    "canonical_route": route,
    "blocked_as_primary_route": blocked,
    "emergency_override": emergency,
    "hard_blocks": hard_blocks,
    "warnings": warnings,
    "source_changed": False,
    "website_source_written": False,
    "git_commit": False,
    "git_push": False,
    "deploy": False,
    "governance_decision": "production_route_iron_law_enforced_by_policy_auditor" if status == "passed" else "production_route_iron_law_policy_needs_repair",
}

json_path = REPORTS / f"learning-v2-production-route-iron-law-auditor-{stamp()}.json"
md_path = RUNTIME / f"learning-v2-production-route-iron-law-auditor-{stamp()}.md"

json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

md_path.write_text(f"""# Learning V2 Production Route Iron Law Auditor

## Result

- audit_status: `{status}`
- source_changed: `false`
- website_source_written: `false`
- git_commit: `false`
- git_push: `false`
- deploy: `false`

## Rule

{rule}

## Canonical Route

{" -> ".join(route)}

## Hard Blocks

{json.dumps(hard_blocks, ensure_ascii=False, indent=2)}

## Meaning

The production route is locked as:

local repository -> GitHub -> Cloudflare Pages Git integration -> post-deploy observer.

Direct Cloudflare upload / wrangler deploy / Cloudflare API mutation are blocked as primary route.

""", encoding="utf-8")

print("production_route_iron_law_audit =", status)
print("report_json =", json_path)
print("report_md =", md_path)
print("hard_blocks =", json.dumps(hard_blocks, ensure_ascii=False))
print("git_commit = false")
print("git_push = false")
print("deploy = false")
