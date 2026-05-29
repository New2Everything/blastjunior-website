# BLXST Failure Context Contract v0

Purpose: normalize blocked / review / unknown / no-auth / future failure states into machine-readable safe-stop and next-action guidance.

This is not an auto-repair tool.

## Core Law

The system must not depend on OldK or ChatGPT reading raw logs to recover.

When blocked, it must produce:

- failure reason
- safe-stop status
- whether continuation is allowed
- next action family
- mutation safety flags

## Non-Hardcoded Principle

This is policy-driven. Status families and examples are non-exhaustive.

Unknown or future failure states must default to `safe_stop_failure_triage_required`, `triage_unknown_state`, and `do_not_mutate`.

## Not Yet Proven

This contract does not prove real D1/R2/Worker mutation, autonomous source write, controlled deploy, rollback, or production recovery.
