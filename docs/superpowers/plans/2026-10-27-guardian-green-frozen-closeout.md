# Guardian Green + Frozen Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining Guardian-owned infrastructure defects without modifying API 2 or MONSTER private state, and freeze only conditions backed by fresh verification.

**Architecture:** Reuse the existing authoritative Guardian lane for each defect, keep one active problem at a time, and use red-green verification before merge. Shared product/data-routing semantics are not silently changed by Guardian; cross-owner defects remain explicit blockers until separately coordinated.

**Tech Stack:** Python 3.13, pytest, GitHub Actions, Vercel Sandbox, Vercel Git deployments.

**Spec:** User-approved 2026-10-27 Guardian diagnostic closeout sequence in the KYRE GUARDIAN project.

## Global Constraints

- Guardian must not modify or certify API 2 or MONSTER private branches, ledgers, frozen registries, proof receipts, percentages, or Steps 2A-2G state.
- Kyre Sports API remains the only application-facing sports data gateway.
- No SGO, ESPN, or ESPN BET introduction.
- One active Guardian problem / branch / PR / proof lane at a time.
- No blind retries or duplicate proof runs.
- No GREEN/FROZEN claim without fresh terminal verification.

## Review Focus

- Successful sandbox command with unavailable stdout/stderr must remain successful while recording deterministic capture-unavailable markers.
- Nonzero sandbox command must remain failed even when output capture is unavailable.
- Receipt-only branches must not create application preview noise while main/real feature branches still deploy normally.
- Legacy deployment references must not be replaced until the active runtime path is proven.
- Provider-routing or sportsbook behavior changes require explicit shared/product coordination and are not silently absorbed into Guardian maintenance.

---

### Task 1: Harden Vercel Sandbox output handoff

**Files:**
- Modify: `runless_v2/sandbox_executor.py`
- Test: `tests/test_guardian_runless_cleanup_v1.py`

**Interfaces:**
- Consumes: Vercel Sandbox command result object (`exit_code`, async `stdout()`, async `stderr()`).
- Produces: stable dict with `exit_code`, `stdout`, and `stderr` where stream-capture failure cannot overwrite the authoritative exit code.

- [x] Write failing regression test for exit-code 0 with stream-accessor failure.
- [x] Verify RED in Guardian CI.
- [ ] Implement minimal stream-capture fallback.
- [ ] Verify focused tests and full project test suite.
- [ ] Merge PR #1900 only after required checks are green.
- [ ] Verify exact-head production convergence and freeze receipt.

### Task 2: Stop receipt-only preview deployment noise

**Files/Settings:**
- Vercel project build-ignore settings for `kyre-sports-api` and `kyre-runless-proof` only if branch-specific behavior is supported without suppressing real feature branches.

- [ ] Confirm exact preview failure boundary from build logs.
- [ ] Add the smallest branch-specific ignore rule for `runless-proof-receipts`.
- [ ] Verify a receipt-only push is skipped and a normal branch remains eligible to build.
- [ ] Record rollback settings.

### Task 3: Legacy deployment-reference audit

**Files:** active clients containing `onrender.com` only after reachability proof.

- [ ] Trace each active Render default to current runtime consumers.
- [ ] Change only proven-live legacy defaults to certified Vercel origins with regression tests.
- [ ] Leave historical/docs-only references untouched unless misleading active operations.

### Task 4: Remaining cross-owner blockers

- [ ] Re-measure provider fan-out / DraftKings 403 behavior and NBA PRA latency after Guardian-owned fixes.
- [ ] If a remaining defect changes sportsbook routing, TTLs, product semantics, or API 2/MONSTER-owned page logic, classify it as shared/product coordination instead of falsely freezing Guardian as 100%.

### Task 5: Final verification and freeze

- [ ] Re-read current `main` SHA.
- [ ] Verify API / Runless / Finalizer exact-head production deployments.
- [ ] Verify runtime errors for all three projects.
- [ ] Verify Guardian checks and rollback anchors.
- [ ] Publish final Guardian health board with any cross-owner blockers separated from Guardian-owned state.
