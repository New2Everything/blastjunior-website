#!/usr/bin/env python3
import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from lxml import html

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
RESEARCH_DIR = BASE / "research"

QUEUE = RESEARCH_DIR / "web-source-discovery-queue.jsonl"
CANDIDATES = RESEARCH_DIR / "web-source-candidates.jsonl"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

DISCOVERY_ID = "learning-v2-research-web-candidate-discovery-v1"

BLOCKED_DOMAINS = {
    "google.com",
    "bing.com",
    "duckduckgo.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "pinterest.com",
    "reddit.com",
}

PREFERRED_DOMAINS = {
    "nngroup.com",
    "web.dev",
    "developer.mozilla.org",
    "gov.uk",
    "material.io",
    "microsoft.com",
    "apple.com",
    "w3.org",
    "baymard.com",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def read_jsonl(path):
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def append_jsonl(path, rows):
    with Path(path).open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def domain_of(url):
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def normalize_ddg_url(href):
    if not href:
        return None

    # DuckDuckGo often returns protocol-relative redirect links:
    # //duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com
    if href.startswith("//"):
        href = "https:" + href

    # Also handle root-relative DDG redirect links.
    if href.startswith("/l/?"):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        if "uddg" in q and q["uddg"]:
            return q["uddg"][0]

    # Handle full DuckDuckGo redirect URLs after protocol normalization.
    parsed = urllib.parse.urlparse(href)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    if host == "duckduckgo.com" and parsed.path.startswith("/l/"):
        q = urllib.parse.parse_qs(parsed.query)
        if "uddg" in q and q["uddg"]:
            return q["uddg"][0]

    if href.startswith("http://") or href.startswith("https://"):
        return href

    return None


def fetch_search_results(query, limit):
    """
    Real web discovery v1:
    - Prefer DuckDuckGo HTML.
    - Fall back to Bing HTML when DDG returns a structure we cannot parse.
    - Only returns candidate URLs; never writes sources.jsonl.
    """
    failures = []

    ddg_url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    try:
        req = urllib.request.Request(
            ddg_url,
            headers={
                "User-Agent": "Mozilla/5.0 learning-v2-web-candidate-discovery-v1",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            body = r.read()
        doc = html.fromstring(body)
        results = parse_generic_result_links(doc, limit, source="duckduckgo")
        if results:
            return results
    except Exception as e:
        failures.append(f"duckduckgo_failed:{type(e).__name__}:{str(e)[:120]}")

    bing_url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query})
    try:
        req = urllib.request.Request(
            bing_url,
            headers={
                "User-Agent": "Mozilla/5.0 learning-v2-web-candidate-discovery-v1",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            body = r.read()
        doc = html.fromstring(body)
        results = parse_bing_result_links(doc, limit)
        if results:
            return results
        results = parse_generic_result_links(doc, limit, source="bing_generic")
        if results:
            return results
    except Exception as e:
        failures.append(f"bing_failed:{type(e).__name__}:{str(e)[:120]}")

    return []


def parse_bing_result_links(doc, limit):
    results = []
    seen = set()

    anchors = doc.xpath('//li[contains(@class, "b_algo")]//h2/a[@href]')
    for a in anchors:
        title = " ".join(a.text_content().split())
        href = normalize_ddg_url(a.get("href"))
        if not title or not href:
            continue

        dom = domain_of(href)
        if not dom:
            continue
        if any(dom == b or dom.endswith("." + b) for b in BLOCKED_DOMAINS):
            continue
        if href in seen:
            continue
        seen.add(href)

        snippet = ""
        li = a
        for _ in range(5):
            li = li.getparent()
            if li is None:
                break
            texts = li.xpath('.//p//text()')
            if texts:
                snippet = " ".join(" ".join(texts).split())
                break

        results.append({
            "title": title[:240],
            "url": href,
            "domain": dom,
            "snippet": snippet[:500],
        })
        if len(results) >= limit:
            break

    return results


def parse_generic_result_links(doc, limit, source):
    results = []
    seen = set()

    preferred = doc.xpath('//a[contains(@class, "result__a")][@href]')
    anchors = preferred or doc.xpath("//a[@href]")

    bad_texts = {
        "images", "videos", "news", "maps", "shopping", "settings",
        "privacy", "terms", "advertise", "about", "feedback",
    }

    for a in anchors:
        title = " ".join(a.text_content().split())
        href = normalize_ddg_url(a.get("href"))
        if not title or not href:
            continue

        clean_title = title.strip()
        if len(clean_title) < 8:
            continue
        if clean_title.lower() in bad_texts:
            continue

        dom = domain_of(href)
        if not dom:
            continue
        if any(dom == b or dom.endswith("." + b) for b in BLOCKED_DOMAINS):
            continue
        if href in seen:
            continue

        seen.add(href)

        snippet = ""
        container = a
        for _ in range(5):
            parent = container.getparent()
            if parent is None:
                break
            container = parent
            texts = container.xpath('.//*[contains(@class, "result__snippet") or contains(@class, "b_caption")]//text()')
            if not texts:
                texts = container.xpath(".//p//text()")
            if texts:
                snippet = " ".join(" ".join(texts).split())
                break

        results.append({
            "title": clean_title[:240],
            "url": href,
            "domain": dom,
            "snippet": snippet[:500],
        })

        if len(results) >= limit:
            break

    return results


def fetch_ddg_results(query, limit):
    # Backward-compatible function name used by main().
    return fetch_search_results(query, limit)

def confidence_for(domain, title, snippet):
    text = f"{title} {snippet}".lower()
    if domain in PREFERRED_DOMAINS or any(domain.endswith("." + d) for d in PREFERRED_DOMAINS):
        return "medium-high"
    if any(x in text for x in ["guideline", "case study", "research", "design system", "ux", "accessibility"]):
        return "medium"
    return "low"


def source_type_guess(title, snippet, domain):
    text = f"{title} {snippet} {domain}".lower()
    if "case study" in text:
        return "UX case study"
    if "guideline" in text or "design system" in text:
        return "official guideline / design system"
    if "research" in text:
        return "research article"
    return "website case"


def existing_candidate_keys():
    return {
        (r.get("task_id"), r.get("url"))
        for r in read_jsonl(CANDIDATES)
        if r.get("task_id") and r.get("url")
    }


def build_candidate(task, result, rank):
    return {
        "candidate_id": f"web-source-candidate-{task.get('query_id')}-{stamp()}-{rank}",
        "task_id": task.get("task_id"),
        "packet_id": task.get("packet_id"),
        "request_id": task.get("request_id"),
        "query_id": task.get("query_id"),
        "topic": task.get("topic"),
        "search_phrase": task.get("search_phrase"),
        "title": result.get("title"),
        "url": result.get("url"),
        "publisher_or_author": result.get("domain"),
        "source_type_guess": source_type_guess(result.get("title") or "", result.get("snippet") or "", result.get("domain") or ""),
        "why_relevant": f"Search result for '{task.get('search_phrase')}' with snippet: {(result.get('snippet') or '')[:220]}",
        "candidate_confidence": confidence_for(result.get("domain") or "", result.get("title") or "", result.get("snippet") or ""),
        "requires_validation_before_intake": True,
        "web_browsed_by_openclaw": True,
        "sources_jsonl_written": False,
        "business_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "status": "candidate_needs_validation",
        "discovery_id": DISCOVERY_ID,
        "discovered_at": now_iso(),
    }


def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    out_json = REPORT_DIR / f"research-web-candidate-discovery-v1-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"research-web-candidate-discovery-v1-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Web Candidate Discovery v1",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- discovery_id: `{DISCOVERY_ID}`",
        f"- result: `{payload['result']}`",
        f"- apply: `{str(apply).lower()}`",
        f"- mode: `real_web_duckduckgo_html_v1`",
        f"- input_task_count: `{payload['input_task_count']}`",
        f"- searched_task_count: `{payload['searched_task_count']}`",
        f"- candidate_count: `{payload['candidate_count']}`",
        f"- fresh_candidate_count: `{payload['fresh_candidate_count']}`",
        f"- duplicate_candidate_count: `{payload['duplicate_candidate_count']}`",
        "- sources_jsonl_written: `false`",
        "- state_written: `false`",
        "- business_source_written: `false`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
        "",
        "## Candidate preview",
        "",
    ]

    for c in payload["candidates_preview"][:20]:
        lines += [
            f"### `{c.get('candidate_id')}`",
            "",
            f"- query_id: `{c.get('query_id')}`",
            f"- topic: `{c.get('topic')}`",
            f"- title: {c.get('title')}",
            f"- url: {c.get('url')}",
            f"- confidence: `{c.get('candidate_confidence')}`",
            f"- source_type_guess: `{c.get('source_type_guess')}`",
            "",
        ]

    if payload["failures"]:
        lines += ["", "## Failures", ""]
        lines += [f"- {f}" for f in payload["failures"]]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_json, out_md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="append real web candidates to web-source-candidates.jsonl only")
    ap.add_argument("--limit-tasks", type=int, default=3)
    ap.add_argument("--limit-results-per-task", type=int, default=2)
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

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

    tasks = read_jsonl(QUEUE)
    if not tasks:
        failures.append("missing_web_source_discovery_queue")

    existing = existing_candidate_keys()
    existing_task_ids = {task_id for task_id, url in existing if task_id}
    pending_tasks = [t for t in tasks if t.get("task_id") not in existing_task_ids]

    fresh = []
    duplicate_count = 0
    searched = 0

    if not failures:
        for task in pending_tasks[:args.limit_tasks]:
            searched += 1
            query = task.get("search_phrase") or ""
            try:
                results = fetch_ddg_results(query, args.limit_results_per_task)
            except Exception as e:
                failures.append(f"search_failed:{task.get('task_id')}:{type(e).__name__}:{str(e)[:160]}")
                continue

            for idx, result in enumerate(results, 1):
                c = build_candidate(task, result, idx)
                key = (c.get("task_id"), c.get("url"))
                if key in existing:
                    duplicate_count += 1
                    continue
                fresh.append(c)
                existing.add(key)

            time.sleep(1.0)

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "discovery_id": DISCOVERY_ID,
        "result": result,
        "apply": args.apply,
        "mode": "real_web_duckduckgo_html_v1",
        "input_task_count": len(tasks),
        "pending_task_count": len(pending_tasks),
        "searched_task_count": searched,
        "candidate_count": len(fresh) + duplicate_count,
        "fresh_candidate_count": len(fresh),
        "duplicate_candidate_count": duplicate_count,
        "candidates_preview": fresh[:30],
        "policy": {
            "writes_web_source_candidates": bool(args.apply and result == "ok"),
            "sources_jsonl_written": False,
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "requires_validation_before_real_source_intake": True,
        },
        "failures": failures,
    }

    report_json, report_md = write_report(payload, args.apply)

    print("research_web_candidate_discovery_v1 =", result)
    print("discovery_id =", DISCOVERY_ID)
    print("mode = real_web_duckduckgo_html_v1")
    print("report_json =", report_json)
    print("report_md =", report_md)
    print("input_task_count =", len(tasks))
    print("pending_task_count =", len(pending_tasks))
    print("searched_task_count =", searched)
    print("fresh_candidate_count =", len(fresh))
    print("duplicate_candidate_count =", duplicate_count)
    print("sources_jsonl_written = false")
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if fresh:
        print()
        print("candidate_preview =")
        for c in fresh[:10]:
            print(f"- {c.get('query_id')} {c.get('candidate_confidence')} {c.get('title')} {c.get('url')}")

    if failures:
        print()
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        print("web_source_candidates_written = false")
        raise SystemExit(2)

    if not args.apply:
        print("web_source_candidates_written = false")
        return 0

    if not fresh:
        print("web_source_candidates_written = false")
        print("reason = no_fresh_candidates")
        return 0

    append_jsonl(CANDIDATES, fresh)
    print("web_source_candidates_written = true")
    print("web_source_candidates_path =", CANDIDATES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
