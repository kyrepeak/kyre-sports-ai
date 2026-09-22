# NFL Game Totals Multi-Source Data Router — Design

**Status:** Approved architecture, implementation not started
**Project:** NFL Game Totals
**Baseline main:** `4c7f8739795125728d2ded593b59025868c179c9`
**Scope:** Replace direct single-provider data acquisition under Steps 3–7 with a shared free/open multi-source routing layer while preserving the certified Step-8 projection formula and sportsbook firewall.

## 1. Problem

NFL Game Totals Steps 3–7 currently fetch provider-specific data directly. A failure from one provider can make multiple context layers unavailable and therefore prevent Step 8 from producing a projection even when the required football facts are available elsewhere.

The system needs a shared data-access layer that requests canonical football metrics, tries certified free/open providers in priority order, validates and normalizes responses, records provenance, and fails closed only when no trustworthy source can satisfy a metric.

## 2. Non-negotiable constraints

1. No paid data provider, API-key subscription, or metered commercial data dependency is introduced by this project.
2. Existing certified Step-8 projection math remains unchanged.
3. Sportsbook/FanDuel data remains outside the football-statistics router and retains exactly `0.0%` influence on Step-8 projection math.
4. Steps 3–7 keep their public output contracts unless an additive provenance field is explicitly introduced without breaking callers.
5. Existing adjacent NFL surfaces remain frozen unless a narrow compatibility change is required and separately certified.
6. The system must fail closed rather than fabricate, silently coerce, or guess ambiguous data.
7. Provider-specific definitions may be used only when they can be transformed into the canonical metric definition with documented validation.

## 3. Architecture

Introduce a shared backend routing layer, initially centered on:

- `sports_api/nfl_data_router_v1.py` — canonical metric requests, provider priority, fallback orchestration, validation gating, provenance, caching hooks.
- Provider adapters under a focused namespace or module family, such as:
  - nflverse adapter for schedules/completed-game/play-by-play-derived football data.
  - National Weather Service adapter for U.S. venue weather/forecast data.
  - existing verified slate/source adapter for matchup identity and current game-day truth.
  - ESPN adapter retained as a fallback, not the single point of failure.
- Normalization/validation functions that translate provider-specific payloads into canonical internal metric contracts.

The intended flow is:

`Step 3–7 context builder -> NFL Data Router -> provider adapter(s) -> validator/normalizer -> canonical context -> Step 8`

Step 8 must not know which provider supplied the data. It continues to consume the same certified context values it already understands.

## 4. Source hierarchy

### 4.1 Completed-game statistics and projection inputs

Primary strategy: use free/open historical and play-by-play data that can be normalized into the canonical definitions used by the Game Totals model. nflverse is the preferred initial backbone for completed-game and play-by-play-derived metrics. Existing verified public sources may be used as secondary providers. ESPN remains a fallback.

Priority is metric-specific rather than globally provider-specific. A provider is eligible only for metrics whose definitions and freshness can be certified.

### 4.2 Schedule, matchup identity, and venue

Use the existing verified slate/game identity path first when it already has exact event identity. Supplement or fall back to free/open schedule data and then provider-specific event sources where necessary.

### 4.3 Weather

For outdoor U.S. NFL games, use National Weather Service data based on stadium coordinates and kickoff timing as the preferred weather path. Indoor games remain weather-neutral by contract. Additional free/open fallbacks may be added only after licensing, field semantics, and freshness are validated. ESPN weather may remain a last fallback.

### 4.4 Market data

Market totals and prices remain on the existing separate sportsbook path. They are not inputs to this router and do not affect Step-8 projection math.

## 5. Canonical metrics by Game Totals step

### Step 3 — Scoring context

Canonical inputs include completed-game points scored and points allowed, current/prior-season blending inputs, and opponent identity needed to preserve the existing scoring context contract.

### Step 4 — Pace and possession

Canonical inputs include plays per game and possession/opportunity context. If a provider supplies raw play-by-play rather than a pre-aggregated field, the adapter may derive the canonical value using one documented formula.

### Step 5 — Explosive scoring

The router must define one canonical explosive-play definition. Provider fields are accepted only if they match that definition or can be transformed exactly. Otherwise the provider is ineligible for this metric. Raw play-by-play derivation is preferred when it provides clearer semantic control.

### Step 6 — Red zone and drive sustainability

Canonical inputs include red-zone touchdown rate, third-down conversion rate, first downs per game, and—where trustworthy raw data permits—real drive-level context. Existing Step-6 outputs remain compatible; richer drive information may be additive but cannot silently redefine existing fields.

### Step 7 — Environment

Canonical inputs include exact venue identity, indoor/outdoor status, stadium coordinates where required, kickoff time, temperature, precipitation probability/measure, and wind/gust values sufficient for the existing environment-pressure classification. Indoor games always neutralize weather effects.

## 6. Validation rules

Every metric must pass validation before it becomes `ready: true`.

Validation includes:

- exact team identity and canonical abbreviation mapping;
- season and game-date consistency;
- exact event identity where game-specific data is used;
- expected field type and numeric finiteness;
- sane physical/statistical ranges;
- canonical metric-definition compatibility;
- freshness appropriate to the metric;
- no unresolved duplicate/ambiguous records.

A provider returning a number is not sufficient. The system must verify what that number means.

## 7. Provenance contract

Every routed result should carry additive provenance sufficient for debugging and certification. At minimum:

- `provider_used`
- `fallback_rank`
- `data_freshness`
- `fields_verified`
- `quality`
- `diagnostics`

Where useful, also record source timestamp, fetch timestamp, season/game identifier, and the provider failures that caused fallback.

Normal UI may keep this compact; diagnostics must expose it clearly when a context fails.

## 8. Quality policy

Use `HIGH`, `MEDIUM`, and `LOW` quality as a transport/data-confidence label, not as a model recommendation.

Quality should consider:

- source authority/reliability for that metric;
- definition match;
- completeness;
- freshness;
- whether fallback was needed;
- whether independent cross-source sanity evidence agrees.

Low-quality data must not silently appear equivalent to certified high-quality data. If a metric falls below the minimum accepted quality for projection use, return it as unavailable/fail-closed rather than injecting it into Step 8.

## 9. Freshness and caching

Caching is required both for speed and to avoid unnecessary load on free public sources.

Policy:

- immutable/completed historical game data: long-lived cache;
- season-to-date aggregates: medium-lived cache, refreshed after new completed games;
- schedules and event identity: shorter-lived cache around slate changes;
- upcoming outdoor weather: progressively shorter TTL as kickoff approaches;
- indoor venue status: long-lived unless venue/game metadata changes;
- per-team profiles: fetch once per relevant cache window and reuse across matchups;
- per-game environment data: cache by exact game/event identity and kickoff window.

The existing Game Totals `Reload Data` action should invalidate only relevant Game Totals router/context caches, not unrelated site state.

## 10. Cross-source sanity checks

When more than one certified provider is available for an important metric, the router may compare values.

Rules:

- expected small differences caused by timing/rounding are acceptable within documented tolerances;
- material disagreements trigger diagnostics and either prefer the higher-authority/fresher canonical source or fail closed if the discrepancy cannot be resolved;
- the router must never average contradictory values merely to make the field available.

## 11. Failure and fallback behavior

For each metric request:

1. try the highest-priority eligible provider;
2. validate and normalize;
3. if unavailable/invalid, record the diagnostic and try the next certified provider;
4. continue until a valid canonical value is obtained;
5. if all eligible providers fail, return `ready: false` with complete diagnostics.

A provider HTTP error such as `403`, timeout, schema drift, missing field, or malformed response is a fallback event, not an automatic projection failure.

No fallback may bypass validation.

## 12. Step migration strategy

Migrate Steps 3–7 one context at a time behind tests rather than replacing all provider logic in one uncontrolled cutover.

For each step:

- add router-facing tests first;
- prove the canonical output matches the existing certified context contract;
- preserve classifier thresholds/formulas unless separately approved;
- prove provider failure triggers fallback;
- prove all providers failing remains fail-closed;
- prove provenance is correct;
- run existing regression/freeze tests before moving to the next step.

Step 8 is not modified during the migration except for tests that prove its input contract and formula remain unchanged.

## 13. Projection firewall

The Step-8 total projection remains a pure consumer of football context. Its formula and public helper signature remain frozen.

Permanent protections:

- no market total, odds, price, sportsbook snapshot, or FanDuel object may be accepted by the Step-8 projection helper;
- routed football context may affect Step 8 only through the existing certified context fields;
- sportsbook projection weight remains `0.0`;
- Step 9 may later compare a finished model total to the market, downstream of Step 8.

## 14. Testing and certification

Implementation must use TDD and include at least:

- provider-adapter parsing tests using deterministic fixtures;
- canonical normalization tests;
- provider priority/fallback tests;
- HTTP error/timeout/schema-drift tests;
- ambiguity and invalid-range fail-closed tests;
- freshness/TTL tests;
- cache reuse and explicit invalidation tests;
- cross-source disagreement tests;
- Step 3–7 backward-contract tests;
- Step-8 projection firewall/signature tests;
- sportsbook 0.0% influence tests;
- targeted compile checks;
- exact changed-file/freeze guard;
- existing NFL critical/regression/permanent-contract suites;
- real Streamlit browser QA on the Game Totals page;
- protected-main final gate before merge.

A production-ready certification should demonstrate at least one forced provider failure where the page still obtains valid context from a fallback, plus one all-providers-fail case where the model correctly refuses to project.

## 15. Performance expectations

The router must reduce duplicate network work rather than add serial provider latency.

- Reuse team profiles within a slate render.
- Use bounded concurrency for independent provider/game fetches where already consistent with project patterns.
- Stop fallback immediately once a valid canonical metric is obtained.
- Do not query secondary providers merely for decoration unless performing a deliberate low-cost sanity check.
- Keep page rendering responsive on mobile.

## 16. Observability

Diagnostics should make it possible to answer, for any unavailable or fallback metric:

- what metric was requested;
- which providers were tried and in what order;
- why each failed validation or transport;
- which provider ultimately won;
- how fresh the accepted data is;
- what canonical fields were produced.

Provider errors must be visible to diagnostics without exposing secrets. This architecture introduces no paid-provider credentials or new secret requirement.

## 17. Rollback and isolation

The migration must remain additive and reversible.

- Existing certified Step-8 projection module remains untouched.
- Provider adapters and router are isolated modules.
- Step migrations are narrow and independently testable.
- If a migrated context causes production regression, that context can be rolled back to its prior direct-provider implementation without changing Step 8 or unrelated NFL surfaces.

## 18. Explicit out of scope

This project does not:

- implement Step 9 market/final-read logic;
- change Step-8 projection weights or thresholds;
- add betting/stake sizing or wager execution;
- introduce paid sports/weather data;
- rewrite Spread, Moneyline, Passing, Rushing, or Receiving pages;
- redesign the Game Totals UI beyond additive provenance/diagnostic indicators needed for this router;
- train a new machine-learning model.

## 19. Success criteria

The architecture is successful when:

1. Steps 3–7 request canonical data through the shared router rather than directly depending on ESPN.
2. At least one certified fallback exists for each critical context needed by Step 8, or the metric explicitly fails closed when no qualifying free/open fallback exists.
3. A single ESPN failure no longer disables the entire projection chain when equivalent trusted data is available elsewhere.
4. Step-8 projection math and helper signature remain unchanged.
5. Sportsbook influence on projection remains exactly `0.0%`.
6. Provenance, freshness, and diagnostics identify exactly how every accepted metric was sourced.
7. Mobile/browser certification shows the Game Totals page remains responsive and usable.
8. Protected-main regression and final-gate certification are green before merge.

## 20. Approved high-level rollout

This design belongs to the eight-step multi-source upgrade sequence:

1. Lock source hierarchy — approved.
2. Lock router/component data flow — approved.
3. Lock validation, freshness, caching, and quality rules — approved.
4. Write and review this architecture spec.
5. Build the shared NFL data router and provider adapters.
6. Reconnect Steps 3–7 without changing Step-8 math.
7. Run TDD, freeze protection, browser QA, NFL-critical, and permanent certification.
8. Merge to protected `main` and verify production behavior.

Implementation may be decomposed into smaller PRs by context/provider if the implementation plan determines that is safer. The frozen contracts and success criteria above do not change.
