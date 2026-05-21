#!/usr/bin/env python3
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
VISUAL_DIR = BASE / "visual-evidence"
RUNTIME_DIR = BASE / "runtime" / "visual-capture"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
VISUAL_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-browser-visual-capture-v0"

TARGETS = [
    {
        "name": "homepage_desktop",
        "source_path": "public/index.html",
        "url_kind": "file",
        "viewport": "1440,1000",
        "required": True,
        "mobile_validation": False,
    },
    {
        "name": "homepage_mobile",
        "source_path": "public/index.html",
        "url_kind": "file",
        "viewport": "390,844",
        "required": True,
        "mobile_validation": True,
    },
    {
        "name": "nav_mobile",
        "source_path": "components/nav.html",
        "url_kind": "wrapper",
        "viewport": "390,844",
        "required": True,
        "mobile_validation": True,
    },
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def latest_report(pattern):
    files = sorted(REPORT_DIR.glob(pattern))
    return files[-1] if files else None

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

def run_cmd(args):
    p = subprocess.run(
        args,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return {
        "args": args,
        "returncode": p.returncode,
        "output": p.stdout.strip(),
    }

def file_url(path: Path) -> str:
    return path.resolve().as_uri()

def build_nav_wrapper():
    nav_path = WORKSPACE / "components/nav.html"
    nav_css = WORKSPACE / "components/nav.css"
    site_css = WORKSPACE / "public/styles.css"

    nav_html = nav_path.read_text(encoding="utf-8") if nav_path.exists() else "<!-- missing nav -->"

    wrapper = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Nav Mobile Visual Evidence Wrapper</title>
<link rel="stylesheet" href="{file_url(site_css)}" />
<link rel="stylesheet" href="{file_url(nav_css)}" />
<style>
body {{
  margin: 0;
  min-height: 100vh;
  background: #f7f7f7;
}}
.visual-wrapper {{
  padding: 12px;
}}
</style>
</head>
<body>
<div class="visual-wrapper">
{nav_html}
</div>
</body>
</html>
"""
    wrapper_path = RUNTIME_DIR / "nav-mobile-wrapper.html"
    wrapper_path.write_text(wrapper, encoding="utf-8")
    return wrapper_path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Capture screenshots into learning-v2/visual-evidence; never edits website source.")
    args = ap.parse_args()

    visual_validation_path = latest_report("learning-v2-visual-evidence-capture-validation-dry-run-*.json")
    if not visual_validation_path:
        raise SystemExit("no visual evidence capture validation report found")

    visual_validation = load_json(visual_validation_path, {})

    hard_blocks = []
    warnings = []

    if visual_validation.get("validation_status") != "browser_visual_capture_module_required":
        hard_blocks.append("visual_validation_not_requesting_browser_capture_module")
    if visual_validation.get("visual_tooling_available") is not True:
        hard_blocks.append("visual_tooling_not_available")
    if visual_validation.get("source_change_gate_allowed") is not False:
        hard_blocks.append("visual_validation_allows_gate_too_early")

    npx_check = run_cmd(["npx", "playwright", "--version"])
    if npx_check["returncode"] != 0:
        hard_blocks.append("playwright_not_available")

    run_id = stamp()
    run_dir = VISUAL_DIR / f"browser-capture-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    nav_wrapper_path = None
    target_results = []

    if not hard_blocks:
        nav_wrapper_path = build_nav_wrapper()

    for t in TARGETS:
        src = WORKSPACE / t["source_path"]
        output_path = run_dir / f"{t['name']}.png"

        result = {
            "name": t["name"],
            "source_path": t["source_path"],
            "viewport": t["viewport"],
            "required": t["required"],
            "mobile_validation": t["mobile_validation"],
            "source_exists": src.exists(),
            "screenshot_path": str(output_path),
            "screenshot_exists": False,
            "actual_visual_captured": False,
            "actual_mobile_validated": False,
            "command": None,
            "returncode": None,
            "output": None,
        }

        if not src.exists():
            result["output"] = "source file missing"
            hard_blocks.append(f"{t['source_path']}:source_missing")
            target_results.append(result)
            continue

        if hard_blocks:
            result["output"] = "skipped because hard blocks exist"
            target_results.append(result)
            continue

        if t["url_kind"] == "wrapper":
            url = file_url(nav_wrapper_path)
        else:
            url = file_url(src)

        cmd = [
            "npx",
            "playwright",
            "screenshot",
            "--viewport-size",
            t["viewport"],
            url,
            str(output_path),
        ]

        capture = run_cmd(cmd)

        result["command"] = cmd
        result["returncode"] = capture["returncode"]
        result["output"] = capture["output"]
        result["screenshot_exists"] = output_path.exists()
        result["actual_visual_captured"] = capture["returncode"] == 0 and output_path.exists()
        result["actual_mobile_validated"] = bool(t["mobile_validation"] and result["actual_visual_captured"])

        if t["required"] and not result["actual_visual_captured"]:
            hard_blocks.append(f"{t['name']}:visual_capture_failed")
        if t["mobile_validation"] and not result["actual_mobile_validated"]:
            hard_blocks.append(f"{t['name']}:mobile_validation_failed")

        target_results.append(result)

    captured_count = sum(1 for x in target_results if x["actual_visual_captured"])
    mobile_validated_count = sum(1 for x in target_results if x["actual_mobile_validated"])
    required_count = sum(1 for x in target_results if x["required"])

    if hard_blocks:
        capture_status = "blocked"
        recommended_next_action = "fix_browser_visual_capture_before_gate"
        visual_evidence_audit_allowed = False
    elif captured_count >= required_count:
        capture_status = "browser_visual_capture_ready_for_audit"
        recommended_next_action = "run_browser_visual_capture_auditor_before_gate"
        visual_evidence_audit_allowed = True
    else:
        capture_status = "browser_visual_capture_incomplete"
        recommended_next_action = "rerun_browser_visual_capture_after_fix"
        visual_evidence_audit_allowed = False

    payload = {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "result": "ok",
        "mode": "dry_run_apply_artifacts" if args.apply else "dry_run",
        "apply": bool(args.apply),
        "visual_validation_source": str(visual_validation_path),
        "capture_status": capture_status,
        "recommended_next_action": recommended_next_action,
        "run_dir": str(run_dir),
        "target_count": len(TARGETS),
        "required_count": required_count,
        "captured_count": captured_count,
        "mobile_validated_count": mobile_validated_count,
        "target_results": target_results,
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "visual_evidence_audit_allowed": visual_evidence_audit_allowed,
        "source_change_gate_allowed": False,
        "source_change_gate_opened": False,
        "safety": {
            "state_written": False,
            "business_source_written": False,
            "website_source_written": False,
            "source_change_gate_opened": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "artifact_written": True,
        },
    }

    json_path = REPORT_DIR / f"learning-v2-browser-visual-capture-dry-run-{run_id}.json"
    md_path = SNAPSHOT_DIR / f"learning-v2-browser-visual-capture-dry-run-{run_id}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Browser Visual Capture Dry Run")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- result: `{payload['result']}`")
    md.append(f"- capture_status: `{capture_status}`")
    md.append(f"- recommended_next_action: `{recommended_next_action}`")
    md.append(f"- run_dir: `{run_dir}`")
    md.append(f"- captured_count: `{captured_count}`")
    md.append(f"- mobile_validated_count: `{mobile_validated_count}`")
    md.append(f"- visual_evidence_audit_allowed: `{str(visual_evidence_audit_allowed).lower()}`")
    md.append(f"- source_change_gate_allowed: `false`")
    md.append(f"- website_source_written: `false`")
    md.append(f"- deploy: `false`")
    md.append("")
    md.append("## Target Results")
    md.append("")
    for r in target_results:
        md.append(f"### {r['name']}")
        md.append(f"- source_path: `{r['source_path']}`")
        md.append(f"- viewport: `{r['viewport']}`")
        md.append(f"- screenshot_path: `{r['screenshot_path']}`")
        md.append(f"- screenshot_exists: `{str(r['screenshot_exists']).lower()}`")
        md.append(f"- actual_visual_captured: `{str(r['actual_visual_captured']).lower()}`")
        md.append(f"- actual_mobile_validated: `{str(r['actual_mobile_validated']).lower()}`")
        md.append(f"- returncode: `{r['returncode']}`")
        md.append("")
    md.append("## Hard Blocks")
    md.append("")
    if hard_blocks:
        for x in hard_blocks:
            md.append(f"- {x}")
    else:
        md.append("- none")
    md.append("")
    md.append("## Safety")
    md.append("")
    for k, v in payload["safety"].items():
        md.append(f"- {k}: `{str(v).lower()}`")

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("browser_visual_capture = ok")
    print("mode =", payload["mode"])
    print("capture_status =", capture_status)
    print("recommended_next_action =", recommended_next_action)
    print("run_dir =", run_dir)
    print("target_count =", len(TARGETS))
    print("required_count =", required_count)
    print("captured_count =", captured_count)
    print("mobile_validated_count =", mobile_validated_count)
    print("visual_evidence_audit_allowed =", str(visual_evidence_audit_allowed).lower())
    print("source_change_gate_allowed = false")
    print("source_change_gate_opened = false")
    print("hard_blocks =", json.dumps(hard_blocks, ensure_ascii=False))
    print("warnings =", json.dumps(warnings, ensure_ascii=False))
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
