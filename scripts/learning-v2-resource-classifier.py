#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
REGISTRY = WORKSPACE / "projects" / "BLXST-cloudflare-resource-registry.json"
REPORT_DIR = WORKSPACE / "learning-v2" / "reports"
SNAPSHOT_DIR = WORKSPACE / "learning-v2" / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-resource-classifier-v0"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))

def has_any(text, words):
    low = text.lower()
    return any(w.lower() in low for w in words)

def classify(text, origin):
    registry = load_registry()
    low = text.lower()

    resources = []
    gates = []
    warnings = []

    def add(resource_type, name, reason, risk="medium"):
        item = {
            "resource_type": resource_type,
            "name": name,
            "reason": reason,
            "risk": risk,
        }
        if item not in resources:
            resources.append(item)

    if has_any(text, ["首页", "homepage", "宣传语", "slogan", "页面", "page", "html", "css", "导航", "nav"]):
        add("pages_or_static_source", registry["pages"]["project_name"], "website page/static source/content surface mentioned", "medium")
        gates.append("pages_static_source_gate")

    if has_any(text, ["发布", "上线", "deploy", "publish", "production", "生产"]):
        add("cloudflare_pages_deploy", registry["pages"]["project_name"], "publish/deploy intent mentioned", "high")
        gates.append("controlled_pages_deploy_gate")

    if has_any(text, ["比赛记录", "赛事", "积分", "战队", "选手", "报名", "赛季", "榜单", "match record", "event", "standings", "team", "player", "registration"]):
        add("d1_database", "blast-campaigns-db", "competition/event/team/player/standing data mentioned", "high")
        gates.append("d1_campaigns_data_gate")

    if has_any(text, ["新闻", "news", "文章", "报道"]):
        add("d1_database", "news-database", "news/content data mentioned", "high")
        gates.append("d1_news_data_gate")

    if has_any(text, ["用户", "登录", "注册", "账号", "auth", "login", "register", "session"]):
        add("worker_api", "blast-auth-api", "auth/login/register/session mentioned", "high")
        add("d1_database", "blast-user-db", "user/auth data mentioned", "high")
        add("kv_namespace", "blast-cache_or_session_related_namespace_review_required", "session/cache context mentioned", "high")
        gates.append("worker_api_gate")
        gates.append("d1_user_data_gate")
        gates.append("kv_session_gate")

    if has_any(text, ["照片", "图片", "图库", "媒体", "上传", "photo", "image", "gallery", "media", "upload"]):
        add("r2_bucket", "blastjunior-media", "media/photo/gallery/upload mentioned", "high")
        add("d1_database", "blast-photo-db", "photo metadata may be needed", "medium")
        gates.append("r2_media_gate")
        gates.append("d1_photo_metadata_gate")

    if has_any(text, ["worker", "api", "接口", "cors", "路由", "binding", "绑定"]):
        add("worker_api", "review_required", "worker/api/binding mentioned", "high")
        gates.append("worker_api_gate")

    if has_any(text, ["kv", "缓存", "会话", "presence", "online", "在线"]):
        add("kv_namespace", "review_required", "KV/cache/session/presence mentioned", "high")
        gates.append("kv_gate")

    if has_any(text, ["d1", "数据库", "database", "schema", "表", "入库"]):
        add("d1_database", "review_required", "database/schema/storage mentioned", "high")
        gates.append("d1_gate")

    unknown_markers = [
        "新增", "新建", "创建新的", "新增数据库", "新增表", "新表", "new database", "new table",
        "new worker", "new api", "new route", "new bucket", "new kv", "unknown resource",
        "新资源", "新结构", "新增结构", "新页面结构", "新内容结构"
    ]

    if has_any(text, unknown_markers):
        add("unknown_resource_boundary", "registry_update_required", "new or unknown resource/structure mentioned", "high")
        gates.append("registry_update_required")
        gates.append("review_required")
        warnings.append("unknown_or_new_resource_requires_registry_update")

    if not resources:
        gates.append("ordinary_or_uncertain_task")
        warnings.append("no_specific_cloudflare_resource_detected")

    authorized_context = origin in {
        "user_direct_with_/blxst",
        "user_confirmed_blxst_after_prompt",
        "scheduled_learning_task",
        "autonomous_learning_cycle",
        "controlled_deploy_phase",
        "maintenance_observer",
    }

    mutation_allowed_by_classifier = False

    return {
        "generated_at": now_iso(),
        "script_id": SCRIPT_ID,
        "mode": "dry_run",
        "input_text": text,
        "origin": origin,
        "authorized_context": authorized_context,
        "classified_resources": resources,
        "recommended_gates": sorted(set(gates)),
        "warnings": warnings,
        "registry_driven_policy": {
            "registry_is_source_of_truth": True,
            "seed_rules_are_not_complete_truth": True,
            "unknown_resources_require_review": True,
            "unknown_resource_labels": [
                "unknown_resource_boundary",
                "registry_update_required",
                "review_required"
            ]
        },
        "safety": {
            "classification_only": True,
            "state_written": False,
            "website_source_written": False,
            "cloudflare_mutation": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "mutation_allowed_by_classifier": mutation_allowed_by_classifier
        },
    }

def write_reports(payload):
    ts = stamp()
    jp = REPORT_DIR / f"learning-v2-resource-classifier-dry-run-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-resource-classifier-dry-run-{ts}.md"
    jp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Resource Classifier Dry Run",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- origin: `{payload['origin']}`",
        f"- authorized_context: `{str(payload['authorized_context']).lower()}`",
        f"- resource_count: `{len(payload['classified_resources'])}`",
        f"- gates: `{', '.join(payload['recommended_gates'])}`",
        "- classification_only: `true`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
        "",
        "## Resources",
    ]
    if payload["classified_resources"]:
        for r in payload["classified_resources"]:
            lines.append(f"- `{r['resource_type']}` / `{r['name']}` / risk=`{r['risk']}` / {r['reason']}")
    else:
        lines.append("- none")
    lines += ["", "## Warnings"]
    lines += [f"- {w}" for w in payload["warnings"]] if payload["warnings"] else ["- none"]
    mp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return jp, mp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--origin", default="manual_probe")
    args = ap.parse_args()

    payload = classify(args.text, args.origin)
    jp, mp = write_reports(payload)

    print("resource_classifier = ok")
    print("authorized_context =", str(payload["authorized_context"]).lower())
    print("resource_count =", len(payload["classified_resources"]))
    print("recommended_gates =", ",".join(payload["recommended_gates"]))
    for r in payload["classified_resources"]:
        print(f"resource = {r['resource_type']}::{r['name']} risk={r['risk']}")
    print("report_json =", jp)
    print("report_md =", mp)
    print("classification_only = true")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
