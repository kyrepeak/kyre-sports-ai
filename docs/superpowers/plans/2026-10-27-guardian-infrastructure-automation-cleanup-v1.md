# KYRE GUARDIAN Infrastructure + Automation Cleanup V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate stale infrastructure references and false-red automation while preserving current sports behavior and Guardian isolation.

**Architecture:** Treat current Vercel production and current Guardian browser/runless proof as authoritative. Retire obsolete scheduled checks when they no longer represent production, repair active checks to use current targets, make small-slate canary semantics explicit, and make Finalizer health/configuration truthful.

**Tech Stack:** GitHub Actions YAML, Python 3.12, Vercel FastAPI services, pytest, Playwright/Streamlit Guardian proof.

**Spec:** `docs/superpowers/specs/2026-10-27-guardian-infrastructure-automation-cleanup-v1.md`

## Global Constraints

- Step 2A: one authoritative branch/PR/run path.
- Anti-Loop: classify root cause before repair; no blind reruns.
- No API 2 or MONSTER private state reuse or modification.
- No sports feature/provider-routing changes.
- No rewriting frozen historical product artifacts.
- Active production monitors must target current authoritative production services.

## Review Focus

- One-game/undersized slates must not falsely fail percentage canaries.
- Retired historical workflows must not keep scheduled triggers.
- Active monitors must not call obsolete Render or dead Streamlit roots.
- Finalizer must not report healthy/configured semantics when required authority is absent.
- Exact-head Guardian browser/runless proof must remain green after cleanup.

---

### Task 1: Classify stale scheduled workflows

**Files:**
- Inspect/Modify: `.github/workflows/*.yml`
- Create/Test: focused Guardian contract test if required.

**Interfaces:**
- Consumes: current production target inventory and recent failed workflow logs.
- Produces: a minimal set of CURRENT scheduled monitors; historical workflows become non-scheduled/retired.

- [ ] Identify scheduled workflows referencing obsolete Render or dead Streamlit targets.
- [ ] Separate CURRENT operational monitors from frozen/historical certification workflows.
- [ ] Remove schedules from historical workflows rather than forcing them green.
- [ ] Add assertions that retired workflows cannot regain schedules or obsolete production URLs.
- [ ] Run focused static tests.

### Task 2: Repair active monitor production targets and small-slate semantics

**Files:**
- Modify only active monitor workflow(s) proven current.
- Test: Guardian workflow-contract test.

**Interfaces:**
- Consumes: current Vercel production API endpoint and current browser/transport target.
- Produces: monitors that distinguish production regression from insufficient live-slate cardinality.

- [ ] Replace obsolete production targets in CURRENT monitors.
- [ ] Add semantic non-failure behavior for percentage canaries when floor(slatesize * percent) is zero.
- [ ] Preserve real failure behavior for transport, freshness, contract, and protected-impact violations.
- [ ] Run focused tests and exact workflow contract checks.

### Task 3: Finalizer configuration truthfulness

**Files:**
- Inspect/Modify: Finalizer health/config code only if needed.
- Vercel production env: add only required missing variables if safely derivable from existing authoritative project configuration.

**Interfaces:**
- Consumes: existing GitHub App/Supabase authority requirements.
- Produces: `/health` that reports configured truthfully and a production deployment with required authority active.

- [ ] Determine exact variables required for `configured=true`.
- [ ] Reuse existing authoritative secret/config sources; do not invent values.
- [ ] Configure production environment or, if configuration is intentionally absent, change health state to degraded and remove it from required closeout authority.
- [ ] Redeploy and verify `/health`.

### Task 4: Exact-head verification and freeze

**Files:**
- Guardian proof/plan files only if needed for this cleanup certification.

**Interfaces:**
- Consumes: Tasks 1-3 successor SHA.
- Produces: exact-head green checks, merge, production convergence, Guardian-owned freeze proof.

- [ ] Verify branch diff is Guardian-only maintenance.
- [ ] Run focused static contracts.
- [ ] Run real-browser Guardian certification.
- [ ] Verify Runless final gate if applicable.
- [ ] Merge with exact-head lease.
- [ ] Verify main SHA and Vercel production convergence.
- [ ] Verify Guardian-owned freeze token/receipt chain and report 100% GREEN + FROZEN only with fresh evidence.
