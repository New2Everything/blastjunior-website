#!/usr/bin/env python3
import argparse
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from lxml import html

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
RESEARCH_DIR = BASE / "research"

PACKETS = RESEARCH_DIR / "web-source-candidate-enrichment-packets.jsonl"
ENRICHMENTS = RESEARCH_DIR / "web-source-candidate-enrichments.jsonl"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

ENRICHER_ID = "learning-v2-research-candidate-enrichment-v1"


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


def clean_text(s):
    return re.sub(r"\s+", " ", s or "").strip()


def fetch_page(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 learning-v2-candidate-enrichment-v1",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        body = r.read()
        final_url = r.geturl()
        status = r.status
        ctype = r.headers.get("content-type", "")
    return status, final_url, ctype, body


def extract_page(body):
    doc = html.fromstring(body)

    for bad in doc.xpath("//script|//style|//noscript|//svg|//nav|//footer|//header|//form"):
        parent = bad.getparent()
        if parent is not None:
            parent.remove(bad)

    title = clean_text(doc.xpath("string(//title)"))

    metas = doc.xpath('//meta[translate(@name,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz")="description"]/@content')
    meta_desc = clean_text(metas[0]) if metas else ""

    headings = [clean_text(x) for x in doc.xpath("//h1//text()|//h2//text()") if clean_text(x)]
    paragraphs = [clean_text(x) for x in doc.xpath("//p//text()") if len(clean_text(x)) >= 40]
    list_items = [clean_text(x) for x in doc.xpath("//li//text()") if len(clean_text(x)) >= 40]

    body_text = clean_text(" ".join(paragraphs[:24] + list_items[:12]))

    return {
        "title": title,
        "meta_desc": meta_desc,
        "headings": headings[:10],
        "body_text": body_text,
        "text_len": len(body_text),
    }


def first_sentences(text, n=3):
    if not text:
        return []
    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    out = []
    for p in parts:
        p = clean_text(p)
        if 50 <= len(p) <= 260:
            out.append(p)
        if len(out) >= n:
            break
    return out


def make_claim_summary(pkt, page):
    pieces = []
    if page.get("meta_desc"):
        pieces.append(page["meta_desc"])
    for h in page.get("headings") or []:
        if len(h) >= 8:
            pieces.append(h)
    pieces += first_sentences(page.get("body_text") or "", 2)

    joined = clean_text(" ".join(pieces))
    if not joined:
        return None

    return joined[:420]


def make_key_claims(pkt, page):
    claims = []

    if page.get("meta_desc"):
        claims.append(page["meta_desc"][:240])

    for s in first_sentences(page.get("body_text") or "", 5):
        if s not in claims:
            claims.append(s[:260])
        if len(claims) >= 4:
            break

    if len(claims) < 2:
        return []

    return claims[:4]


def make_design_principles(pkt, page):
    text = f"{pkt.get('title')} {pkt.get('search_phrase')} {page.get('title')} {page.get('meta_desc')} {page.get('body_text')}".lower()

    principles = []

    if any(x in text for x in ["onboarding", "new user", "setup", "first"]):
        principles.append("Make the first successful action obvious and reduce setup friction for new users.")

    if any(x in text for x in ["case study", "examples", "inspiration", "gallery"]):
        principles.append("Use concrete examples or case studies to help visitors understand what good participation looks like.")

    if any(x in text for x in ["community", "engagement", "participation", "members"]):
        principles.append("Show participation pathways clearly so community members know how to join, contribute, or stay involved.")

    if any(x in text for x in ["sports", "club", "league", "team", "event"]):
        principles.append("For sports communities, surface teams, events, membership, and proof of activity before asking users to act.")

    if any(x in text for x in ["template", "website", "design", "responsive", "mobile"]):
        principles.append("Keep visual design energetic but structured, with responsive sections that remain readable on mobile.")

    if len(principles) < 2:
        principles.append("Organize content around the visitor’s next decision rather than around internal categories.")
        principles.append("Prefer concise, scannable sections that connect user motivation with practical next steps.")

    # Deduplicate while preserving order
    out = []
    for p in principles:
        if p not in out:
            out.append(p)
    return out[:4]


def existing_enrichment_candidate_ids():
    return {
        r.get("candidate_id")
        for r in read_jsonl(ENRICHMENTS)
        if r.get("candidate_id")
    }


def build_record(pkt, page, final_url):
    claim_summary = make_claim_summary(pkt, page)
    key_claims = make_key_claims(pkt, page)
    design_principles = make_design_principles(pkt, page)

    if not claim_summary or len(key_claims) < 2 or len(design_principles) < 2:
        return None, {
            "candidate_id": pkt.get("candidate_id"),
            "reason": "insufficient_extracted_content_for_required_fields",
            "text_len": page.get("text_len"),
            "has_claim_summary": bool(claim_summary),
            "key_claims_count": len(key_claims),
            "design_principles_count": len(design_principles),
        }

    record = {
        "enrichment_id": f"candidate-enrichment-{pkt.get('candidate_id')}-{stamp()}",
        "candidate_id": pkt.get("candidate_id"),
        "task_id": pkt.get("task_id"),
        "query_id": pkt.get("query_id"),
        "topic": pkt.get("topic"),
        "title": pkt.get("title"),
        "url": final_url or pkt.get("url"),
        "publisher_or_author": pkt.get("publisher_or_author"),
        "source_type_guess": pkt.get("source_type_guess"),
        "candidate_confidence": pkt.get("candidate_confidence"),
        "retrieved_or_created_at": now_iso().split("T")[0],
        "claim_summary": claim_summary,
        "key_claims": key_claims,
        "design_principles": design_principles,
        "applicability_to_blastjunior": (
            "This source can inform BLXST / HADO website improvements around community onboarding, "
            "sports-club participation paths, trust-building examples, and clearer next-step guidance."
        ),
        "web_browsed_by_openclaw": True,
        "sources_jsonl_written": False,
        "notes": "Generated by automatic enrichment v1. Must be validated by enriched-candidate-intake and revalidated before real-source-intake.",
    }

    return record, None


def write_report(payload, apply):
    suffix = "apply" if apply else "dry-run"
    report_json = REPORT_DIR / f"research-candidate-enrichment-v1-{suffix}-{stamp()}.json"
    report_md = REPORT_DIR / f"research-candidate-enrichment-v1-{suffix}-{stamp()}.md"
    output_jsonl = REPORT_DIR / f"research-candidate-enrichment-v1-{suffix}-{stamp()}.jsonl"

    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with output_jsonl.open("w", encoding="utf-8") as f:
        for row in payload["records_preview"]:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    lines = [
        "# Learning V2 Candidate Enrichment v1",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- enricher_id: `{ENRICHER_ID}`",
        f"- result: `{payload['result']}`",
        f"- apply: `{str(apply).lower()}`",
        f"- packet_count: `{payload['packet_count']}`",
        f"- processed_packet_count: `{payload['processed_packet_count']}`",
        f"- enriched_count: `{payload['enriched_count']}`",
        f"- skipped_count: `{payload['skipped_count']}`",
        f"- output_jsonl: `{output_jsonl}`",
        "- sources_jsonl_written: `false`",
        "- state_written: `false`",
        "- business_source_written: `false`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
        "",
        "## Enrichment preview",
        "",
    ]

    for r in payload["records_preview"][:10]:
        lines += [
            f"### `{r.get('candidate_id')}`",
            "",
            f"- title: {r.get('title')}",
            f"- url: {r.get('url')}",
            f"- claim_summary: {r.get('claim_summary')}",
            f"- key_claims_count: `{len(r.get('key_claims') or [])}`",
            f"- design_principles_count: `{len(r.get('design_principles') or [])}`",
            "",
        ]

    if payload["skips"]:
        lines += ["", "## Skips", ""]
        for s in payload["skips"][:20]:
            lines.append(f"- `{s.get('candidate_id')}`: {s.get('reason')} text_len={s.get('text_len')}")

    if payload["failures"]:
        lines += ["", "## Failures", ""]
        lines += [f"- {f}" for f in payload["failures"]]

    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_json, report_md, output_jsonl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="append enriched records to web-source-candidate-enrichments.jsonl")
    ap.add_argument("--limit", type=int, default=3)
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

    packets = read_jsonl(PACKETS)
    done = existing_enrichment_candidate_ids()
    pending = [p for p in packets if p.get("candidate_id") not in done]

    records = []
    skips = []
    processed = 0

    if not failures:
        for pkt in pending[:args.limit]:
            processed += 1
            try:
                status, final_url, ctype, body = fetch_page(pkt.get("url"))
                page = extract_page(body)
                record, skip = build_record(pkt, page, final_url)
                if record:
                    records.append(record)
                elif skip:
                    skips.append(skip)
            except Exception as e:
                skips.append({
                    "candidate_id": pkt.get("candidate_id"),
                    "reason": f"fetch_or_extract_failed:{type(e).__name__}:{str(e)[:180]}",
                    "url": pkt.get("url"),
                })

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "enricher_id": ENRICHER_ID,
        "result": result,
        "apply": args.apply,
        "packet_count": len(packets),
        "pending_packet_count": len(pending),
        "processed_packet_count": processed,
        "enriched_count": len(records),
        "skipped_count": len(skips),
        "records_preview": records,
        "skips": skips,
        "policy": {
            "writes_enrichments": False,
            "sources_jsonl_written": False,
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "requires_revalidation_before_real_source_intake": True,
        },
        "failures": failures,
    }

    report_json, report_md, output_jsonl = write_report(payload, args.apply)

    print("research_candidate_enrichment_v1 =", result)
    print("enricher_id =", ENRICHER_ID)
    print("report_json =", report_json)
    print("report_md =", report_md)
    print("output_jsonl =", output_jsonl)
    print("packet_count =", len(packets))
    print("pending_packet_count =", len(pending))
    print("processed_packet_count =", processed)
    print("enriched_count =", len(records))
    print("skipped_count =", len(skips))
    print("sources_jsonl_written = false")
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if records:
        print()
        print("enrichment_preview =")
        for r in records[:6]:
            print(f"- {r.get('candidate_id')} title={r.get('title')} claims={len(r.get('key_claims') or [])} principles={len(r.get('design_principles') or [])}")

    if skips:
        print()
        print("skip_preview =")
        for s in skips[:8]:
            print(json.dumps(s, ensure_ascii=False))

    if failures:
        print()
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        print("enrichments_written = false")
        raise SystemExit(2)

    if args.apply:
        print("enrichments_written = false")
        print("reason = formal_enrichment_store_write_disabled_use_intake_script")
        print("next_step = run learning-v2-research-enriched-candidate-intake.py --enrichment-file <output_jsonl> --apply")
        return 0

    print("enrichments_written = false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
