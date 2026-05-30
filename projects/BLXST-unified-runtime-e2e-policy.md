# BLXST Unified Runtime E2E Policy v0

Purpose: route a BLXST runtime task into the correct dry-run E2E chain.

## Core Law

The unified runtime E2E orchestrator is dry-run only.

Branch selection must come from policy and router output, not hardcoded resource names.

It must not write D1, R2, KV, Workers, website source, registry, Cloudflare, git, or deployment state.

Unknown branches safe-stop into review.
