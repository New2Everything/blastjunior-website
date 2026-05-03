#!/usr/bin/env python3
import difflib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FAMILY = "community.onboarding_experience"
EXECUTOR_ID = "learning-v2-gallery-next-action-source-change-dry-run-v0"
TARGET_FILE = WORKSPACE / "public/gallery.html"
TARGET_REL = "public/gallery.html"

GALLERY_ACTION_BLOCK = """
<section class="gallery-next-action" aria-labelledby="gallery-next-action-title">
  <div class="section-inner">
    <p class="section-kicker">After watching HADO moments</p>
    <h2 id="gallery-next-action-title">Take the next simple step</h2>
    <p>
      Photos and highlights show the energy of HADO. The next step is simple:
      understand the game, try it with others, and join the club community.
    </p>
    <p class="gallery-action-links">
      <a href="/join.html" class="btn primary">Try or join HADO</a>
      <a href="/index.html" class="btn secondary">Back to homepage</a>
    </p>
  </div>
</section>
""".strip()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def latest_report(pattern):
    reports = sorted(REPORT_DIR.glob(pattern))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def insert_block(original):
    if "gallery-next-action-title" in original or "gallery-next-action" in original:
        return original, "already_present"

    insertion = "\n\n" + GALLERY_ACTION_BLOCK + "\n"

    if re.search(r"</main\s*>", original, flags=re.I):
        proposed = re.sub(r"</main\s*>", insertion + "\n</main>", original, count=1, flags=re.I)
        return proposed, "before_closing_main"

    if re.search(r"</body\s*>", original, flags=re.I):
        proposed = re.sub(r"</body\s*>", insertion + "\n</body>", original, count=1, flags=re.I)
        return proposed, "before_closing_body"

    return original.rstrip() + insertion + "\n", "append_eof"

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    plan_path, plan = latest_report("community-onboarding-controlled-source-change-plan-*.json")
    milestone = state.get("last_controlled_learning_source_change_closed") or {}

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if milestone.get("target_file") != "public/index.html":
        failures.append("first_controlled_homepage_milestone_not_closed")

    if not plan_path:
        failures.append("missing_controlled_source_change_plan")

    if plan.get("result") != "ok":
        failures.append(f"controlled_source_change_plan_not_ok:{plan.get('result')}")

    gallery_plan = None
    for item in plan.get("change_plans") or []:
        if item.get("proposal_id") == "gallery-next-action":
            gallery_plan = item
            break

    if not gallery_plan:
        failures.append("missing_gallery_next_action_change_plan")
    else:
        if gallery_plan.get("target_file") != TARGET_REL:
            failures.append(f"unexpected_gallery_target:{gallery_plan.get('target_file')}")
        if gallery_plan.get("execution_status") != "second_candidate_after_homepage":
            failures.append(f"gallery_plan_not_second_candidate:{gallery_plan.get('execution_status')}")
        if gallery_plan.get("risk") != "low":
            failures.append(f"gallery_plan_risk_not_low:{gallery_plan.get('risk')}")

    if not TARGET_FILE.exists():
        failures.append("target_file_missing:public/gallery.html")

    original = TARGET_FILE.read_text(encoding="utf-8", errors="ignore") if TARGET_FILE.exists() else ""
    proposed, insertion_mode = insert_block(original)

    original_lines = original.splitlines()
    proposed_lines = proposed.splitlines()

    diff_lines = list(difflib.unified_diff(
        original_lines,
        proposed_lines,
        fromfile=TARGET_REL,
        tofile=TARGET_REL + ".proposed",
        lineterm=""
    ))

    changed = original != proposed
    already_present = insertion_mode == "already_present"

    if already_present:
        failures.append("gallery_next_action_block_already_present")

    if not changed:
        failures.append("no_gallery_change_to_dry_run")

    payload = {
        "generated_at": now_iso(),
        "executor_id": EXECUTOR_ID,
        "result": "ok" if not failures else "blocked",
        "target_family": TARGET_FAMILY,
        "target_file": TARGET_REL,
        "change_plan_report": str(plan_path) if plan_path else None,
        "gallery_change_plan": gallery_plan,
        "insertion_mode": insertion_mode,
        "changed_in_dry_run": changed,
        "already_present": already_present,
        "diff_line_count": len(diff_lines),
        "diff_preview": diff_lines[:240],
        "proposed_block": GALLERY_ACTION_BLOCK,
        "acceptance_checks": [
            "No source file was written.",
            "No state file was written.",
            "No git commit, push, or deploy was attempted.",
            "Diff only targets public/gallery.html.",
            "Change shape is one compact gallery next-action section.",
            "No gallery data loading, upload, R2 paths, auth, API, D1, KV, Worker, or navigation JavaScript is modified."
        ],
        "policy": {
            "source_written": False,
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "dry_run_only": True
        },
        "failures": failures
    }

    out_json = REPORT_DIR / f"gallery-next-action-source-change-dry-run-{stamp()}.json"
    out_md = REPORT_DIR / f"gallery-next-action-source-change-dry-run-{stamp()}.md"
    out_diff = REPORT_DIR / f"gallery-next-action-source-change-dry-run-{stamp()}.diff"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_diff.write_text("\n".join(diff_lines) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Gallery Next Action Source Change Dry Run")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- executor_id: `{EXECUTOR_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- target_file: `{TARGET_REL}`")
    lines.append(f"- insertion_mode: `{insertion_mode}`")
    lines.append(f"- changed_in_dry_run: `{str(changed).lower()}`")
    lines.append(f"- diff_line_count: `{len(diff_lines)}`")
    lines.append("- source_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Proposed block")
    lines.append("")
    lines.append("```html")
    lines.append(GALLERY_ACTION_BLOCK)
    lines.append("```")
    lines.append("")
    lines.append("## Diff preview")
    lines.append("")
    lines.append("```diff")
    lines.extend(diff_lines[:240])
    lines.append("```")
    if failures:
        lines.append("")
        lines.append("## Failures")
        for f in failures:
            lines.append(f"- {f}")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("gallery_next_action_source_change_dry_run =", payload["result"])
    print("executor_id =", EXECUTOR_ID)
    print("target_family =", TARGET_FAMILY)
    print("target_file =", TARGET_REL)
    print("change_plan_report =", plan_path)
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("report_diff =", out_diff)
    print("insertion_mode =", insertion_mode)
    print("changed_in_dry_run =", str(changed).lower())
    print("already_present =", str(already_present).lower())
    print("diff_line_count =", len(diff_lines))
    print("source_written = false")
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    print()
    print("diff_preview =")
    for line in diff_lines[:100]:
        print(line)

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
