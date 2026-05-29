# BLXST Next-Action Dispatcher Policy v0

Purpose: select the next safe dry-run or review action from Failure Context Resolver output.

This is not an auto-repair tool.

## Core Law

The dispatcher recommends the next action. It does not execute mutation.

It must not write website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

## Non-Hardcoded Principle

This policy is non-exhaustive.

Unknown next-action families must route to `triage_unknown_state` and `do_not_mutate`.

Priority order is policy guidance, not hardcoded truth.
