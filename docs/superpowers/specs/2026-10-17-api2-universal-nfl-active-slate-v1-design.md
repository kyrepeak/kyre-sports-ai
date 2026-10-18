# API 2 — Universal NFL Active-Slate Resolver V1 Design

**Date:** 2026-10-17
**Workstream:** API 2
**Repository:** `kyrepeak/kyre-sports-ai`
**Approved architecture:** Option 1 — Universal NFL Active-Slate Resolver

## 1. Problem

NFL pages currently do not have one universal date authority. Multiple NFL surfaces initialize or own `nfl_v1_date` independently, and some pages have page-specific smart-slate logic. As a result, a user can open an NFL page on a calendar date with no remaining games and see an empty slate, or switch NFL markets and land on inconsistent dates.

The desired product behavior is that the next active NFL game date appears automatically on every NFL page without the user manually searching for it.

## 2. User-approved behavior

The universal NFL active slate must behave as follows:

1. On entry to any NFL page, automatically resolve the nearest date that still has at least one NFL game that is scheduled or live.
2. If the current Eastern-date slate has at least one upcoming or live NFL game, keep the current date.
3. If every NFL game on the current date is final, immediately advance to the next date containing a scheduled NFL game.
4. If the current date has no NFL games, advance to the next date containing a scheduled NFL game.
5. This must naturally support Thursday Night Football, Sunday slates, Sunday Night Football, Monday Night Football, international games, postseason games, and any irregular NFL schedule without hard-coding weekdays.
6. The behavior applies universally to the NFL section: Slate, Moneyline, Spread, Game Total, Passing Yards, Rushing Yards, Receiving Yards, Receptions, Passing TDs, Anytime TD, Daily Picks, and future NFL markets that join the shared NFL shell.
7. The existing date picker remains available as a manual override.
8. A deliberate manual date selection must be respected and must not immediately snap back to the automatic active slate.
9. Automatic mode becomes authoritative again on a fresh NFL session/entry or when the manual override is explicitly cleared/reset by the shared controller.
10. If schedule verification is unavailable, fail closed rather than inventing a date.

## 3. Design goal

Create one upstream NFL date authority and make individual NFL pages consumers of that state rather than independent owners of default-date behavior.

This prevents market-by-market drift and removes duplicated smart-slate implementations as the source of truth.

## 4. Existing reusable behavior

The repository already contains useful pieces that should be generalized instead of rebuilt:

- `nfl_v1_date` is already used as shared NFL date state across multiple markets.
- `nfl_spread_next_slate_v1.py` can preserve a verified selected day, use nflverse schedule dates for fast future-date discovery, and use bounded primary-loader fallback when the calendar is unavailable.
- `nfl_spread_autodate_repair_v1.py` already demonstrates safe empty-date auto-advance while avoiding permanent caching of a transient `NO_GAMES` result.
- Passing Yards and Receiving Yards contain their own smart-slate controllers/resolvers, proving the behavior exists today but is duplicated.

V1 should consolidate ownership rather than stack another page-specific resolver on top.

## 5. Universal state model

Introduce a shared NFL slate controller with explicit automatic/manual mode.

Recommended state contract:

- `nfl_v1_date`: the currently rendered NFL date, retained for compatibility.
- `nfl_active_slate_mode`: `AUTO` or `MANUAL`.
- `nfl_active_slate_date`: the last verified automatic active slate.
- `nfl_manual_slate_date`: the user-selected override date when mode is `MANUAL`.
- `nfl_active_slate_checked_at`: timestamp for safe short-lived rerender caching.
- `nfl_active_slate_source`: diagnostic source that established the date.
- `nfl_active_slate_state`: `FOUND`, `UNAVAILABLE`, or equivalent fail-closed status.

Only the shared controller may decide the default active NFL date. Market pages may read the result and may request a manual override, but they must not independently overwrite the automatic authority.

## 6. Resolution algorithm

Use Eastern Time as the canonical NFL slate calendar boundary, matching the existing NFL date guard.

### AUTO mode

1. Determine `today_et`.
2. Load/verify games for `today_et` using the existing authoritative NFL schedule/game loader.
3. If at least one game is `scheduled`, `pre`, `in_progress`, `live`, `halftime`, or another canonical non-final active state, resolve to `today_et`.
4. If games exist but every game is final/closed/completed, treat the date as exhausted and search forward.
5. If no games exist, search forward.
6. Discover the next known NFL schedule date from the verified schedule calendar.
7. Verify the candidate date with the authoritative renderable game loader before exposing it as active.
8. If calendar discovery is unavailable, use a bounded forward network fallback, not an unbounded daily scan.
9. If no candidate can be verified, return fail-closed `UNAVAILABLE`/`NO_GAMES` without fabricating a date.

### MANUAL mode

1. Use the user-selected date.
2. Do not auto-advance merely because that date is empty or completed.
3. Surface the actual state for that requested date.
4. Preserve the override while the user remains in the manual flow.
5. Allow a single shared reset-to-active action or fresh-entry policy to return to `AUTO`.

## 7. Game-status rule

The automatic date remains on a slate only while that slate still contains at least one non-final game.

Examples:

- Sunday morning before kickoff → Sunday.
- Sunday afternoon while early games are final but late/SNF is pending or live → Sunday.
- Sunday night after the last Sunday game becomes final → Monday if MNF exists.
- Monday after MNF becomes final → Thursday if TNF is next.
- Tuesday with no game → Thursday.
- Friday/Saturday with no game → Sunday.

Do not key behavior to weekday names; key it to the verified NFL schedule and game status.

## 8. Source and verification policy

The active-slate controller must not turn a calendar hint into a renderable slate without verification.

Preferred behavior:

1. Use the repository's existing authoritative NFL game loader for renderable game truth.
2. Use nflverse or existing schedule-calendar data for fast date discovery only where already adopted.
3. Preserve any existing multi-source schedule verification/router rather than replacing it with an ESPN-only dependency.
4. If sources disagree, do not silently invent consensus; return diagnostics and fail closed according to current NFL data contracts.
5. Cache only verified stable results for short rerender windows. Provider failures and `NO_GAMES` caused by unavailable data must remain retryable.

## 9. Integration boundary

The shared controller should run once at the NFL shell/navigation boundary before the selected NFL market renders.

Market pages then receive/read the resolved shared date.

This avoids:

- Slate showing one date while Spread shows another.
- Re-running independent date searches on every market.
- Keyboard/date widget side effects during navigation.
- Empty `0 games` default screens when the next NFL slate is known.
- Deep-link inconsistency caused by a navigation-only redirect.

Existing market-specific date widgets may remain visually present in V1, but their default value must be driven by the universal controller and their user changes must enter `MANUAL` mode through the shared contract.

## 10. Compatibility and migration

V1 should be additive and backward-compatible:

- Keep `nfl_v1_date` so frozen market code that already reads it does not break.
- Put new automatic/manual ownership around that key rather than renaming every existing consumer in one migration.
- Reuse current smart-slate helpers where practical, but route their final decision through one universal controller.
- After universal ownership is proven, page-specific duplicate resolvers can be deprecated in later cleanup work; removal is not required for V1 unless needed to prevent double ownership.

## 11. Performance

The resolver must feel instantaneous during normal NFL navigation.

Requirements:

- Do not perform a new full schedule scan on every Streamlit rerender.
- Cache a verified active slate for a short safe interval/session and invalidate when the date boundary, game-status terminal transition, manual override, or source state requires it.
- Use calendar discovery before bounded network scanning.
- Never loop through hundreds of dates with live network requests.
- Reuse the same result across all NFL markets in the same session.

## 12. Failure behavior

If the resolver cannot verify schedule truth:

- Do not manufacture a future date.
- Keep the last verified active date only if current cache rules consider it safe.
- Otherwise expose a clear fail-closed state and allow retry on rerender/source recovery.
- Never permanently cache a transient provider outage as `NO_GAMES`.

## 13. Testing and proof requirements

Implementation is not complete until tests cover at minimum:

1. Today has scheduled games → today remains selected.
2. Today has a live game → today remains selected.
3. Some games final but one later game remains → today remains selected.
4. All games today final → next NFL date is selected.
5. Today has zero NFL games → next NFL date is selected.
6. Sunday final → Monday Night Football.
7. Monday final → Thursday Night Football when next.
8. Thursday final → Sunday slate when next.
9. Irregular/international/postseason dates work without weekday assumptions.
10. Manual override to a past/future date is respected.
11. Switching among all NFL markets preserves the same shared date.
12. Fresh automatic entry after a manual session resolves the current active slate again according to the approved reset policy.
13. Calendar discovery unavailable → bounded primary fallback works.
14. Calendar + provider failure → fail closed and retryable.
15. No duplicate async work, network scan loops, or independent market ownership is introduced.
16. Mobile navigation/regression proof confirms the date widget does not reopen the keyboard or cause stale-page bleed during NFL market switching.

## 14. API 2 execution constraints

Implementation must remain isolated to the API 2 workstream and obey the current API 2 execution contract:

- Step 2A before implementation: one active problem, one authoritative branch/PR/run/deployment/proof path.
- No duplicate runs, PRs, deployments, leases, proof requests, or repeated polling.
- Exact-head verification and proof-before-merge.
- Preserve frozen-registry and regression protections.
- Do not import MONSTER live execution state, branches, PRs, SHAs, runs, blockers, leases, or proof authority.
- Final completion requires verified production behavior, GREEN status, and frozen/read-back proof before the workstream is declared complete.

## 15. Non-goals

V1 does not redesign NFL projections, sportsbook models, Monte Carlo logic, ranking logic, player analytics, or visual cards. It only establishes universal NFL active-date ownership and manual override behavior.

V1 does not create separate weekday-specific rules such as `if Thursday` or `if Monday`; schedule truth decides the next date.

V1 does not remove historical-date browsing.

## 16. Success criteria

The design is successful when a user can tap any NFL page and immediately see the next currently actionable NFL slate without manually searching for a date, while still retaining deliberate manual date browsing.

All NFL markets must agree on that date, all-final slates must roll forward automatically, and no page-specific date owner may silently fight the universal controller.
