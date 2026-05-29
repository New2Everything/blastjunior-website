# BLXST Gate Policy Registry v0

Purpose: recommend gate families from resource classification output without freezing BLXST into hardcoded resource-to-gate mappings.

## Core Law

Gate recommendation must be policy-driven and registry-driven.

Seed hints are allowed, but they are not complete truth.

Unknown or newly discovered resources must be marked `registry_update_required` / `review_required`, not ignored.

## Decision Dimensions

- authorized intent context
- resource type
- operation intent
- risk level
- provenance requirement
- mutation level
- unknown/new resource

## Non-Exhaustive Gate Families

- authorized_context_gate
- resource_classifier_gate
- provenance_gate
- registry_update_gate
- review_required_gate
- source_change_gate
- data_mutation_gate
- media_mutation_gate
- worker_api_gate
- controlled_deploy_gate
- outcome_record_gate

## Hard Rules

- Do not turn seed hints into hardcoded truth.
- Do not hardcode future D1/R2/KV/Worker/Page structures into classifier code.
- Unknown resources require registry update or review.
- Real-world content requires provenance checks.
- push != deploy.
