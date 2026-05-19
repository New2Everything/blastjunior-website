#!/usr/bin/env python3
import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
SCRIPT_DIR = WORKSPACE / "scripts"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

GENERATOR_ID = "learning-v2-research-derived-probe-scaffold-generator-v0"

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
    files = sorted(REPORT_DIR.glob(pattern))
    if not files:
        return None, {}
    p = files[-1]
    return p, load_json(p, default={})

def safe_probe_script_name(name):
    if not name:
        return False
    p = Path(name)
    if p.name != name:
        return False
    if not name.startswith("learning-v2-"):
        return False
    if not name.endswith("-probe.py"):
        return False
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        return False
    return True

def safe_id(s):
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(s or "unknown")).strip("-")[:90] or "unknown"

def pick_candidate(report):
    selected = report.get("selected_candidate")
    if isinstance(selected, dict):
        return selected

    top = report.get("top_blocked_candidate")
    if isinstance(top, dict):
        blockers = top.get("blockers") or []
        if any(str(x).startswith("recommended_probe_script_missing:") for x in blockers):
            return top

    return None

def build_probe_script(candidate):
    candidate_json = json.dumps(candidate, ensure_ascii=False, indent=2)

    return f'''#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

PROBE_ID = "learning-v2-research-derived-observe-only-probe-v0"
CANDIDATE = json.loads({candidate_json!r})

SCAN_FILES = [
    "public/index.html",
    "index.html",
    "public/gallery.html",
    "public/news.html",
    "public/campaigns.html",
    "public/profile.html",
    "components/nav.html",
    "public/styles.css",
]

STOPWORDS = {{
    "the", "and", "for", "with", "that", "this", "from", "into", "before",
    "after", "should", "clearly", "communities", "community", "users",
    "visitors", "members", "action", "good", "looks", "what", "how",
}}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def clean_text(s):
    return re.sub(r"\\s+", " ", s or "").strip()

def read_site_files():
    rows = []
    for rel in SCAN_FILES:
        p = WORKSPACE / rel
        if not p.exists() or not p.is_file():
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        rows.append({{
            "path": rel,
            "text": txt,
            "text_lower": txt.lower(),
            "length": len(txt),
        }})
    return rows

def keywords_for(principle):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+", (principle or "").lower())
    out = []
    for w in words:
        w = w.strip("-_")
        if len(w) < 4:
            continue
        if w in STOPWORDS:
            continue
        if w not in out:
            out.append(w)
    return out[:14]

def score_principle(principle, files):
    kws = keywords_for(principle)
    file_hits = []
    total_hits = 0

    for f in files:
        matched = []
        for kw in kws:
            n = f["text_lower"].count(kw)
            if n:
                matched.append({{"keyword": kw, "count": n}})
                total_hits += n
        if matched:
            file_hits.append({{
                "path": f["path"],
                "matched_keywords": matched[:12],
            }})

    status = "signal_present" if total_hits >= 3 else "review_recommended"
    return {{
        "principle": principle,
        "keywords": kws,
        "total_keyword_hits": total_hits,
        "file_hits": file_hits,
        "status": status,
        "reason": (
            "existing_site_has_some_matching_language"
            if status == "signal_present"
            else "observe_only_probe_found_low_matching_signal_in_site_files"
        ),
    }}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="reserved; this probe never modifies website source")
    args = ap.parse_args()

    files = read_site_files()
    principles = CANDIDATE.get("principles") or []
    findings = [score_principle(p, files) for p in principles]

    review_findings = [x for x in findings if x.get("status") == "review_recommended"]
    signal_findings = [x for x in findings if x.get("status") == "signal_present"]

    target_family = CANDIDATE.get("target_family")
    safe_family = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(target_family or "unknown")).strip("-")[:90] or "unknown"

    payload = {{
        "generated_at": now_iso(),
        "probe_id": PROBE_ID,
        "result": "ok",
        "target_family": target_family,
        "candidate_id": CANDIDATE.get("candidate_id"),
        "topic": CANDIDATE.get("topic"),
        "recommended_stage": CANDIDATE.get("recommended_stage"),
        "pattern_count": CANDIDATE.get("pattern_count"),
        "source_titles": CANDIDATE.get("source_titles") or [],
        "scanned_file_count": len(files),
        "finding_count": len(findings),
        "review_recommended_count": len(review_findings),
        "signal_present_count": len(signal_findings),
        "findings": findings,
        "policy": {{
            "observe_only": True,
            "state_written": False,
            "business_source_written": False,
            "website_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "source_change_gate_opened": False,
        }},
    }}

    out_json = REPORT_DIR / f"research-derived-probe-{{safe_family}}-{{stamp()}}.json"
    out_md = SNAPSHOT_DIR / f"research-derived-probe-{{safe_family}}-{{stamp()}}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")

    lines = [
        "# Learning V2 Research-Derived Observe-Only Probe",
        "",
        f"- generated_at: `{{payload['generated_at']}}`",
        f"- target_family: `{{target_family}}`",
        f"- candidate_id: `{{payload['candidate_id']}}`",
        f"- result: `{{payload['result']}}`",
        f"- scanned_file_count: `{{payload['scanned_file_count']}}`",
        f"- finding_count: `{{payload['finding_count']}}`",
        f"- review_recommended_count: `{{payload['review_recommended_count']}}`",
        f"- signal_present_count: `{{payload['signal_present_count']}}`",
        "- state_written: `false`",
        "- business_source_written: `false`",
        "- website_source_written: `false`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
        "",
        "## Findings",
        "",
    ]

    for item in findings:
        lines += [
            f"### {{item.get('status')}}",
            "",
            f"- principle: {{item.get('principle')}}",
            f"- total_keyword_hits: `{{item.get('total_keyword_hits')}}`",
            f"- reason: `{{item.get('reason')}}`",
            "",
        ]

    out_md.write_text("\\n".join(lines) + "\\n", encoding="utf-8")

    print("research_derived_observe_only_probe = ok")
    print("target_family =", target_family)
    print("candidate_id =", payload["candidate_id"])
    print("scanned_file_count =", len(files))
    print("finding_count =", len(findings))
    print("review_recommended_count =", len(review_findings))
    print("signal_present_count =", len(signal_findings))
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("state_written = false")
    print("business_source_written = false")
    print("website_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the missing observe-only probe scaffold")
    ap.add_argument("--force", action="store_true", help="overwrite existing probe script")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    discovery_path, discovery = latest_report("autonomous-target-discovery-*.json")
    candidate = pick_candidate(discovery)

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")
    if state.get("current_topic") is not None:
        failures.append(f"current_topic_not_idle:{state.get('current_topic')}")
    if state.get("current_stage") is not None:
        failures.append(f"current_stage_not_idle:{state.get('current_stage')}")
    if state.get("current_target_family") is not None:
        failures.append(f"current_target_family_not_idle:{state.get('current_target_family')}")
    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")
    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")
    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")
    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")
    if not discovery_path:
        failures.append("missing_autonomous_target_discovery_report")
    if not candidate:
        failures.append("missing_best_candidate_with_probe_scaffold_need")

    script_name = candidate.get("recommended_probe_script") if candidate else None
    if script_name and not safe_probe_script_name(script_name):
        failures.append(f"unsafe_recommended_probe_script:{script_name}")

    script_path = SCRIPT_DIR / script_name if script_name else None
    if script_path and script_path.exists() and not args.force:
        failures.append(f"probe_script_already_exists:{script_path}")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "generator_id": GENERATOR_ID,
        "result": result,
        "apply": args.apply,
        "discovery_report": str(discovery_path) if discovery_path else None,
        "candidate": candidate,
        "script_name": script_name,
        "script_path": str(script_path) if script_path else None,
        "policy": {
            "system_source_written": bool(args.apply and result == "ok"),
            "business_source_written": False,
            "website_source_written": False,
            "state_written": False,
            "source_change_gate_opened": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
        "failures": failures,
    }

    suffix = "apply" if args.apply else "dry-run"
    out_json = REPORT_DIR / f"research-derived-probe-scaffold-generator-{suffix}-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"research-derived-probe-scaffold-generator-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Research-Derived Probe Scaffold Generator",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- result: `{result}`",
        f"- apply: `{str(args.apply).lower()}`",
        f"- target_family: `{candidate.get('target_family') if candidate else None}`",
        f"- script_name: `{script_name}`",
        f"- system_source_written: `{str(payload['policy']['system_source_written']).lower()}`",
        "- business_source_written: `false`",
        "- website_source_written: `false`",
        "- state_written: `false`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
    ]

    if failures:
        lines += ["", "## Failures", ""]
        lines += [f"- {x}" for x in failures]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("research_derived_probe_scaffold_generator =", result)
    print("mode =", "apply" if args.apply else "dry_run")
    print("discovery_report =", discovery_path)
    print("target_family =", candidate.get("target_family") if candidate else None)
    print("script_name =", script_name)
    print("script_path =", script_path)
    print("system_source_written =", "true" if args.apply and result == "ok" else "false")
    print("business_source_written = false")
    print("website_source_written = false")
    print("state_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("report_json =", out_json)
    print("report_md =", out_md)

    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    if not args.apply:
        return 0

    script_path.write_text(build_probe_script(candidate), encoding="utf-8")
    os.chmod(script_path, 0o755)
    print("probe_script_written = true")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
