# Learning V2 Research Policy Summary

## Purpose

This file records the durable summary and handling policy for the Learning V2 research data subsystem.

It intentionally does not commit the full raw `learning-v2/research/` directory.

## Source Directory Reviewed

- `learning-v2/research/`

## Current Research Shape

- research files: `25`
- total size bytes: `943072`
- invalid JSON / JSONL entries: `0`

## Research Buckets

### Core Research Pipeline State

Count: `6`

These files form the core research pipeline:

- `queries.jsonl`
- `source-plans.jsonl`
- `sources.jsonl`
- `digests.jsonl`
- `design-patterns.jsonl`
- `target-family-candidates.jsonl`

Pipeline shape:

`queries → source-plans → sources → digests → design-patterns → target-family-candidates`

Policy:

- Do not archive these files blindly.
- Do not commit the raw files as-is until repository size, privacy, copyright, and lifecycle policy are reviewed.
- Promote durable learning through smaller reviewed summaries, canonical pattern state, or explicit policy files.

### Web Source Candidate Pipeline State

Count: `7`

Files:

- `web-source-discovery-queue.jsonl`
- `web-source-candidates.jsonl`
- `web-source-candidate-validations.jsonl`
- `web-source-candidate-enrichment-packets.jsonl`
- `web-source-candidate-enrichments.jsonl`
- `web-source-candidate-revalidations.jsonl`
- `web-source-candidate-relevance-triage.jsonl`

Policy:

- Treat as active research workflow state.
- Keep visible for review.
- Do not commit raw candidate records as-is.
- Do not delete while consumer scripts still reference them.

### Supporting Research Workflow State

Count: `3`

Files:

- `real-source-collection-requests.jsonl`
- `manual-collection-packets.jsonl`
- `evidence-reinforcements.jsonl`

Policy:

- Treat as supporting workflow state.
- Keep visible for now.
- Review before tracking, archiving, or excluding.

### Test / Sample / Dry-run Fixture Candidates

Count: `9`

Files:

- `design-patterns-test.jsonl`
- `digests-test.jsonl`
- `sources-test.jsonl`
- `target-family-candidates-test.jsonl`
- `sample-enriched-candidate-dryrun.json`
- `sample-real-source-dryrun.json`
- `sample-source-test.json`
- `sample-web-source-candidate-dryrun.json`
- `source-record-draft-from-revalidation-dryrun.json`

Policy:

- Do not delete immediately.
- Some test files are referenced by test auditors and pipeline readiness scripts.
- Separate fixture/archive policy should be decided later.
- If archived later, preserve enough fixtures for test-mode auditors to remain meaningful.

## Repository Policy

Do not commit the entire `learning-v2/research/` directory as raw data.

Do not archive or exclude the entire research directory blindly.

Use reviewed summary files to record durable governance decisions before moving raw research artifacts.

Future handling should separate:

1. canonical pipeline state
2. active workflow state
3. raw candidate records
4. test fixtures
5. dry-run examples
6. obsolete local evidence

## Safety

This summary does not permit:

- source writes to business website files
- git add
- git commit
- git push
- deploy
- direct Cloudflare deployment

All operational changes still require the normal Learning V2 gates.
