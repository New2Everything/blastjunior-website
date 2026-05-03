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
EXECUTOR_ID = "learning-v2-homepage-onboarding-source-change-dry-run-v0"
TARGET_FILE = WORKSPACE / "public/index.html"

ONBOARDING_BLOCK = """
<section class="home-onboarding" aria-labelledby="home-onboarding-title">
  <div class="section-inner">
    <p class="section-kicker">New to HADO?</p>
    <h2 id="home-onboarding-title">Start with one simple path</h2>
    <div class="onboarding-steps" aria-label="HADO starter steps">
      <div class="onboarding-step">
        <strong>1. Understand</strong>
        <span>See how HADO combines sport, teamwork, and AR technology.</span>
      </div>
      <div class="onboarding-step">
        <strong>2. Try</strong>
        <span>Join a beginner-friendly experience with parents, players, or friends.</span>
      </div>
      <div class="onboarding-step">
        <strong>3. Belong</strong>
        <span>Meet the club community, follow events, and find your next match.</span>
      </div>
    </div>
    <p class="onboarding-action">
      <a href="/join.html" class="btn primary">Start here</a>
      <a href="/gallery.html" class="btn secondary">See HADO moments</a>
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

def latest_change_plan():
    reports = sorted(REPORT_DIR.glob("community-onboarding-controlled-source-change-plan-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def insert_block(original):
    if "home-onboarding-title" in original or "home-onboarding" in original:
        return original, "already_present"

    insertion = "\n\n" + ONBOARDING_BLOCK + "\n"

    # Prefer before closing main if present.
    if re.search(r"</main\s*>", original, flags=re.I):
        proposed = re.sub(r"</main\s*>", insertion + "\n</main>", original, count=1, flags=re.I)
        return proposed, "before_closing_main"

    # Otherwise before closing body.
    if re.search(r"</body\s*>", original, flags=re.I):
        proposed = re.sub(r"</body\s*>", insertion + "\n</body>", original, count=1, flags=re.I)
        return proposed, "before_closing_body"

    # Last resort append.
    return original.rstrip() + insertion + "\n", "append_eof"

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    plan_path, plan = latest_change_plan()
    first = plan.get("recommended_first_change") or {}

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    # This executor is dry-run only, so source changes must still be closed.
    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if not plan_path:
        failures.append("missing_controlled_source_change_plan")

    if plan.get("result") != "ok":
        failures.append(f"controlled_source_change_plan_not_ok:{plan.get('result')}")

    if first.get("target_file") != "public/index.html":
        failures.append(f"unexpected_first_target_file:{first.get('target_file')}")

    if first.get("execution_status") != "recommended_first_change":
        failures.append(f"first_change_not_recommended:{first.get('execution_status')}")

    if not TARGET_FILE.exists():
        failures.append("target_file_missing:public/index.html")

    original = TARGET_FILE.read_text(encoding="utf-8", errors="ignore") if TARGET_FILE.exists() else ""
    proposed, insertion_mode = insert_block(original)

    original_lines = original.splitlines()
    proposed_lines = proposed.splitlines()

    diff_lines = list(difflib.unified_diff(
        original_lines,
        proposed_lines,
        fromfile="public/index.html",
        tofile="public/index.html.proposed",
        lineterm=""
    ))

    changed = original != proposed
    already_present = insertion_mode == "already_present"

    payload = {
        "generated_at": now_iso(),
        "executor_id": EXECUTOR_ID,
        "result": "ok" if not failures else "blocked",
        "target_family": TARGET_FAMILY,
        "change_plan_report": str(plan_path) if plan_path else None,
        "target_file": "public/index.html",
        "insertion_mode": insertion_mode,
        "changed_in_dry_run": changed,
        "already_present": already_present,
        "diff_line_count": len(diff_lines),
        "diff_preview": diff_lines[:240],
        "proposed_block": ONBOARDING_BLOCK,
        "acceptance_checks": [
            "No source file was written.",
            "No state file was written.",
            "No git commit, push, or deploy was attempted.",
            "Diff only targets public/index.html.",
            "Change shape is one compact onboarding section.",
            "No auth, API, D1, KV, Worker, or gallery data-loading code is modified."
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

    out_json = REPORT_DIR / f"homepage-onboarding-source-change-dry-run-{stamp()}.json"
    out_md = REPORT_DIR / f"homepage-onboarding-source-change-dry-run-{stamp()}.md"
    out_diff = REPORT_DIR / f"homepage-onboarding-source-change-dry-run-{stamp()}.diff"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_diff.write_text("\n".join(diff_lines) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Homepage Onboarding Source Change Dry Run")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- executor_id: `{EXECUTOR_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- target_file: `public/index.html`")
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
    lines.append(ONBOARDING_BLOCK)
    lines.append("```")
    lines.append("")
    lines.append("## Diff preview")
    lines.append("")
    lines.append("```diff")
    lines.extend(diff_lines[:240])
    lines.append("```")
    lines.append("")
    if failures:
        lines.append("## Failures")
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("homepage_onboarding_source_change_dry_run =", payload["result"])
    print("executor_id =", EXECUTOR_ID)
    print("target_family =", TARGET_FAMILY)
    print("target_file = public/index.html")
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
    for line in diff_lines[:80]:
        print(line)

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
