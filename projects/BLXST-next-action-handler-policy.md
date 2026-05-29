# BLXST Next-Action Dry-run Handler Policy v0

Purpose: turn dispatcher selected_next_action into a dry-run proposal or report.

This is not an auto-repair tool.

## Core Law

The handler may create proposals and reports only.

It must not write registry, website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

## Non-Hardcoded Principle

Handler families are non-exhaustive.

Unknown handler family defaults to unknown-state triage and do-not-mutate.
