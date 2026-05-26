# Learning V2 Source Evidence Summary

## Purpose

This file records the durable summary and handling policy for Learning V2 source evidence.

It intentionally does not commit the raw source log or cached source payloads.

## Source Files Reviewed

- `learning-v2/source_log.jsonl`
- `learning-v2/cache/`

## Current Evidence Shape

- raw source log rows: `99`
- valid JSONL rows: `99`
- invalid JSONL rows: `0`
- successful fetch rows: `97`
- error rows: `2`
- deduped source rows by `final_url` / `url`: `16`
- duplicate rows: `83`
- cache payload files: `97`
- cache refs missing after path normalization: `0`
- cache files not referenced after path normalization: `0`
- source log and cache relationship: `exact`

## Deduped Topic Coverage

- `homepage-information-hierarchy`: `5`
- `mobile-first`: `3`
- `accessibility-basics`: `3`
- `performance-basics`: `3`
- `simplicity`: `2`

## Deduped Domain Coverage

- `web.dev`: `10`
- `developer.mozilla.org`: `4`
- `www.w3.org`: `1`
- `lawsofux.com`: `1`

## Policy

`learning-v2/source_log.jsonl` is treated as raw evidence log state.

`learning-v2/cache/` is treated as the payload store for that raw evidence log.

Do not commit the raw source log as canonical learning state.

Do not commit cache payload files.

Durable learning should be promoted through reviewed, deduplicated, and summarized artifacts such as:

- `learning-v2/patterns.jsonl`
- this source evidence summary
- future reviewed source evidence summaries or policies

## Operational Guidance

When future source evidence is collected:

1. Keep raw fetched evidence in local raw evidence storage.
2. Deduplicate sources before promoting any durable summary.
3. Do not promote full excerpts or payload cache into git.
4. Promote only reviewed summaries, extracted patterns, or explicit policy files.
5. Re-check privacy, copyright, and repository size before committing any source evidence derivative.

## Safety

This summary does not permit:

- source writes to business website files
- git add
- git commit
- git push
- deploy
- direct Cloudflare deployment

All operational changes still require the normal Learning V2 gates.
