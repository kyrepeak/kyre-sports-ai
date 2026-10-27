# KYRE GUARDIAN Security + Configuration Hardening V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove verified orphaned security/configuration debt while preserving frozen sports behavior and API2/MONSTER isolation.

**Architecture:** Treat the live Supabase Advisor and Vercel/GitHub account state as the authoritative external health signals. Use read-only dependency/reference proof before any destructive database or configuration cleanup, then verify the same advisors, deployment parity, branch protection, and runtime error surfaces after changes.

**Tech Stack:** Supabase Postgres + Advisors, Vercel production services, GitHub branch/PR protection and deployment status.

**Spec:** `docs/superpowers/specs/2026-10-27-guardian-security-configuration-hardening-v1.md`

## Global Constraints
- Guardian-only lane.
- Do not modify API2 or MONSTER private/frozen state.
- Do not modify sports models, sports page behavior, or provider routing.
- Preserve existing Guardian Infrastructure + Automation Cleanup V1 freeze.
- Never expose or invent secrets.

## Review Focus
- Orphan proof must precede dropping temporary objects.
- SECURITY DEFINER functions must not remain callable by `anon`/`authenticated` unless explicitly required.
- Search-path hardening must preserve function behavior.
- Finalizer cleanup must remove only completed/stale workstream selectors, never credentials still in use.
- Final proof must verify exact production SHA convergence and zero new runtime errors.

---

### Task 1: Establish authoritative RED diagnostics
- [ ] Record current Supabase Security Advisor findings.
- [ ] Prove repository references and database dependencies for candidate temporary objects.
- [ ] Record Finalizer environment keys and Vercel runtime/deployment state.

### Task 2: Harden Supabase security surface
- [ ] Remove only zero-reference/zero-dependency temporary tables and functions.
- [ ] Set explicit safe search paths on retained functions without changing semantics.
- [ ] Re-run Security Advisor until ERROR/WARN findings caused by this lane are cleared or explicitly classified.

### Task 3: Clean Finalizer configuration
- [ ] Remove only provably stale production task/workstream/fencing selectors from completed API2 work.
- [ ] Preserve GitHub App credentials and any branch-scoped preview variables still required by active work.
- [ ] Do not create a Supabase service-role credential unless it can be transferred securely through connected tools.

### Task 4: Performance hygiene
- [ ] Add covering indexes for foreign keys only where the table remains active and the index is absent.
- [ ] Do not delete indexes solely because the advisor marks them unused.
- [ ] Re-run Performance Advisor and classify remaining informational findings.

### Task 5: Terminal verification + freeze
- [ ] Verify Supabase ACTIVE_HEALTHY and Security Advisor zero ERROR.
- [ ] Verify three Vercel production services READY on the authoritative branch SHA with zero new runtime error clusters.
- [ ] Verify `main` protection still requires `runless-final-gate`.
- [ ] Commit a freeze receipt with the terminal evidence and token `GUARDIAN_SECURITY_CONFIGURATION_HARDENING_V1_FROZEN`.
- [ ] Open one PR, obtain terminal gate success, merge once, and verify production converges to the merge SHA.
