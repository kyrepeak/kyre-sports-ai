# NBA Spread Provider Resilience Step 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CBS Sports as an independent semantic HTML NBA schedule provider and certify a strict 2-of-3 NBA Official / ESPN NBA / CBS Sports schedule quorum without reopening frozen Step 1 or the production router.

**Architecture:** Keep frozen NBA Official and ESPN parsing unchanged. Add a Step-2-only CBS adapter that scopes extraction to semantic scoreboard game cards, maps explicit CBS team aliases to canonical KYRE NBA tricodes, parses card-local tip time using an explicit source timezone, and produces the existing normalized schedule row schema. A Step-2 reconciliation layer certifies any agreeing pair of independent schedule providers, fails closed on one-source evidence or unresolved disagreement, and records only the providers actually used.

**Tech Stack:** Python 3.13, stdlib `html.parser`, `zoneinfo`, existing NBA schedule modules, pytest, Runless V2.

**Spec:** User-supplied `API 2 — NBA PROVIDER RESILIENCE STEP 2 / CBS SEMANTIC SCOREBOARD NORMALIZER — EXACT REPAIR PATH` in the current conversation.

## Global Constraints

- Reuse branch `nba-spread-provider-resilience-step2-r1`; do not create another Step-2 branch.
- Create exactly one PR only after the first coherent implementation candidate exists.
- Do not mutate frozen Step 1, `nba_spread_schedule_v1.py`, the model, projection, probability, sportsbook, injuries, or production router.
- CBS is schedule-only independent confirming/fallback data; never page-wide master truth.
- No fuzzy team matching, no fabricated matchup/time, no global-navigation scraping, no private/opaque CBS JSON dependency.
- Quorum is any two independent providers that agree on canonical matchup/date and tip time within the existing tolerance; one source alone and unresolved disagreement fail closed.
- GitHub Actions fallback = 0; final proof uses exactly one Runless exact-head proof through existing transport.

## Review Focus

- Global-nav team links must never become schedule games.
- A card missing one participant, an unknown CBS team identity, or a reliable tip time must be skipped/fail closed.
- CBS date authority comes from the requested `/scoreboard/YYYYMMDD/` route while canonical game date comes from the parsed tip converted through UTC into `America/Phoenix`.
- Pairwise quorum must succeed for Official+ESPN, Official+CBS, and ESPN+CBS while one-source evidence remains unavailable.
- A disagreeing third provider must not overwrite an already-agreeing pair, but no pair agreement must fail closed.

---

### Task 1: CBS semantic parser fixtures and adapter

**Files:**
- Create: `tests/fixtures/nba_cbs_scoreboard_step2_valid.html`
- Create: `tests/fixtures/nba_cbs_scoreboard_step2_nav_and_two_games.html`
- Create: `tests/fixtures/nba_cbs_scoreboard_step2_malformed.html`
- Create: `tests/test_nba_spread_provider_resilience_step2_r1.py`
- Create: `nba_spread_schedule_provider_resilience_step2_r1.py`

**Interfaces:**
- Consumes: Step-1 transport module and frozen normalized row schema.
- Produces: `parse_cbs_scoreboard_html(html: str, requested_date: str, source_timezone: str = "America/New_York") -> dict`, returning normalized rows plus deterministic parser diagnostics.

- [ ] Write fixture-driven failing tests for semantic card scoping, aliases, unknown/malformed identities, missing time, two games, and Phoenix time conversion.
- [ ] Run only the new Step-2 test file and verify RED because the Step-2 module does not exist.
- [ ] Implement the minimal semantic HTML adapter using stable HTML semantics and explicit aliases only.
- [ ] Re-run parser tests and make them GREEN.

### Task 2: 2-of-3 schedule quorum

**Files:**
- Modify: `nba_spread_schedule_provider_resilience_step2_r1.py`
- Test: `tests/test_nba_spread_provider_resilience_step2_r1.py`

**Interfaces:**
- Consumes: normalized provider rows from NBA Official, ESPN NBA, and CBS Sports.
- Produces: `reconcile_resilient_schedule(provider_games: dict[str, list[dict]], window_dates: tuple[str, ...]) -> dict` and `load_verified_nba_schedule(...) -> dict`.

- [ ] Add RED tests for all three pairwise paths, one-source fail closed, third-provider disagreement with one valid pair, full disagreement, and one-provider-unreachable fallback.
- [ ] Implement pairwise identity/time agreement using the existing 15-minute tolerance and deterministic provider provenance.
- [ ] Re-run all Step-2 tests GREEN, then run Step-1 regression suites unchanged.

### Task 3: Live 7-day certification and Runless metadata

**Files:**
- Create: `devsystem/execution_plans/nba-spread-provider-resilience-step2-r1.json`
- Create: `devsystem/runless_proof_plans/nba-spread-provider-resilience-step2-r1.json`
- Create: `devsystem/task_ledgers/nba-spread-provider-resilience-step2-r1.json`

**Interfaces:**
- Consumes: exact Step-2 candidate and current main authority.
- Produces: one Runless proof plan and finalization identity for `NBA_SPREAD_PROVIDER_RESILIENCE_STEP2_R1_FROZEN`.

- [ ] Run live rolling-7-day certification and print all required provider counts/keys/pairwise agreement/CBS diagnostics.
- [ ] Create the three control-plane files bound to the current synchronized main.
- [ ] Run complete compile + Step-1 + Step-2 suites GREEN.
- [ ] Create exactly one PR, resolve exact scope lease/authorization, submit exactly one Runless exact-head proof, require App 5204253 gate success, expected-head merge, merged-main provenance, finalization ledger transaction, canonical readback, lease release, and terminal `GREEN_FROZEN`.
