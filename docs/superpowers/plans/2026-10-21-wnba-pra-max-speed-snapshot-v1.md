# WNBA PRA Maximum-Speed Snapshot V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the WNBA PRA initial page and return navigation load at maximum practical speed by serving one render-ready Kyre Sports API snapshot while preserving exact sportsbook freshness, current model semantics, source policy, and GREEN + FROZEN controls.

**Architecture:** Keep the certified Vercel Kyre Sports API market board as the only live sportsbook boundary. Persist a slower-changing, source-clean WNBA PRA model artifact outside the first-paint path, then have a lightweight Vercel page-snapshot endpoint read that artifact once and overlay one fresh certified market-board read. Streamlit performs one page-snapshot GET on the healthy path and renders without importing the heavy preserved model stack. Model probability/final-card fields are line-bound: if the live sportsbook line differs from the artifact's certified line, the endpoint returns the fresh quote with `MODEL_REFRESH_REQUIRED` and does not reuse the old probability as if it belonged to the new line.

**Tech Stack:** Python 3.13, Streamlit, FastAPI/Pydantic 2, `httpx`/`requests`, existing pandas/NumPy WNBA model stack for out-of-band artifact generation only, existing Vercel Runless deployment, private Supabase `runless_v2` schema for durable artifacts, pytest, existing MONSTER scope lease/frozen-artifact/finalization controls.

**Spec:** `docs/superpowers/specs/2026-10-21-wnba-pra-max-speed-snapshot-v1-design.md`

## Global Constraints

- Workstream: `monster-wnba-pra-max-speed-snapshot-v1`.
- One authoritative branch, one PR, one scope lease, one proof identity, one Vercel deployment chain. Reconcile base drift on the same branch/PR; never create a duplicate speed lane.
- Kyre Sports API remains the only application-facing WNBA gateway.
- No SGO, ESPN, ESPN BET, or Render in the new active page-snapshot read/generation/publish path.
- Do not modify the certified sportsbook selection policy: FanDuel primary; DraftKings lazy fallback when FanDuel is unusable.
- Never average conflicting sportsbook lines. Preserve sportsbook, event/market/outcome identity, line, side, American price, and capture timestamp exactly.
- Do not change projection math, matchup math, Monte Carlo counts/semantics, qualification thresholds, final-card rules, or sportsbook influence merely for speed.
- Do not add pandas, NumPy, or Streamlit to `runless_v2/requirements.txt`; keep the Vercel read path lightweight.
- The new Vercel endpoint may read persisted model artifacts and current market data, but it must not run the 5M/10M Monte Carlo stack on request.
- A model artifact is valid for probability/final-card reuse only for the exact certified `(game, player, PRA line)` it was generated against. A moved line is `MODEL_REFRESH_REQUIRED`, not permission to reuse an old probability.
- Existing Speed V3 player-detail endpoints are outside the initial-snapshot dependency graph; the new initial path must not call the ESPN-backed detail/history transport.
- A cold-performance measurement means a cold Streamlit process reading a valid durable artifact. A first-ever empty/hard-stale artifact may use the explicit correctness fallback, but that degraded path does not count as speed-green.
- `runless_v2/app.py` is frozen by `MONSTER_WNBA_PRA_LIVE_PROPS_REPAIR_V1_FROZEN`; modifying its router mount requires an exact scoped thaw and re-freeze. Keep `runless_v2/requirements.txt`, `runless_v2/wnba_pra_market_v1.py`, `runless_v2/wnba_schedule_v1.py`, `wnba_api_client_v1.py`, and the prior market bridge/context unchanged unless a new evidenced root cause makes a broader thaw unavoidable.
- No production code mutation starts until the scope lease and any required thaw are authorized.
- GREEN requires live Streamlit proof on the exact merged deployment, not merely unit tests or API health.

## Review Focus

1. **Fresh quote + stale model mismatch:** ensure a moved live line cannot inherit old model probability, edge, EV, or final-card certification.
2. **Forbidden-source resurrection:** ensure model artifact generation cannot reach legacy SGO/ESPN fallbacks even though historical modules still contain those imports/routes.
3. **First-paint regression:** healthy Streamlit path must not import/call heavy projection, matchup, market-grade, Monte Carlo, or final-card builders before rendering.
4. **Duplicate refreshes:** soft-stale/refresh-required states may start at most one bounded refresh per date/season key; no refresh storm on reruns.
5. **Frozen mountpoint:** any `runless_v2/app.py` change must have exact-head thaw authorization before proof and must be re-frozen during closeout.
6. **Supabase security:** model artifacts remain private server-side state; no service-role credential, publish token, or private table access is exposed to the browser/client.
7. **Performance proof quality:** benchmarks must report exact SHA, cache state, network-read count, backend timing, Streamlit read/render timing, and schema version. No target is GREEN without measured production evidence.

---

## Planned File Structure

- Create `wnba_pra_source_clean_guard_v1.py` — context/adapter that fails closed on SGO/ESPN transport use during snapshot artifact generation while permitting existing non-network mathematical fallbacks.
- Create `wnba_pra_page_model_artifact_v1.py` — build/validate/serialize the line-bound render model artifact outside first paint.
- Create `wnba_pra_page_snapshot_publish_v1.py` — authenticated server-side publisher to the Kyre Vercel snapshot API; no token logging.
- Create `runless_v2/wnba_pra_page_snapshot_store_v1.py` — private Supabase durable artifact store via existing server-side `httpx`/Settings pattern.
- Create `runless_v2/wnba_pra_page_snapshot_v1.py` — GET page snapshot + protected POST publish route.
- Modify `runless_v2/app.py` — mount exactly one new router under scoped thaw.
- Create `wnba_pra_page_snapshot_client_v1.py` — one-read Streamlit client using the certified Vercel Kyre API origin.
- Create `wnba_pra_page_snapshot_renderer_v1.py` — thin renderer/compatibility adapter for the returned snapshot.
- Modify `wnba_pra_hub_v3617.py` — healthy snapshot-first route with explicit bounded degraded fallback.
- Create `tests/test_wnba_pra_max_speed_snapshot_v1.py` — source, persistence, route, freshness, line-binding, exact-quote and single-flight contract.
- Create `tests/test_wnba_pra_max_speed_streamlit_v1.py` — one-read/no-heavy-import initial render and fallback behavior.
- Create `devsystem/wnba_pra_max_speed_profile_v1.py` — deterministic timing/network-call profiler.
- Create `devsystem/runless_proof_plans/monster-wnba-pra-max-speed-snapshot-v1.json` — immutable exact-head proof plan.
- Create one Supabase migration with `supabase migration new wnba_pra_page_snapshots_v1`; use the exact generated path returned by the CLI rather than inventing a timestamped filename.

### Task 1: Lock Step 2A scope, frozen ownership, and source-clean RED tests

**Files:**
- Create: `tests/test_wnba_pra_max_speed_snapshot_v1.py`
- Read only: `devsystem/finalization_ledger_v2/**`, `devsystem/frozen_artifact_registry_state_v1.json`, `devsystem/scope_aware_execution_lease_state_v1.json`

**Interfaces:**
- Consumes current `main`, current speed-branch head, Finalization Ledger V2, legacy frozen registry, scope-aware execution lease.
- Produces one exact write-scope declaration and one authoritative WNBA speed scope lease. If `runless_v2/app.py` is changed, produces exactly one thaw authorization bound to the eventual candidate head/blob pair before exact-head proof.

- [ ] Re-read `main`, speed branch, finalization ledger, frozen registry, and scope lease immediately before implementation. Confirm the only active external holder is disjoint; if not, stop at `PARALLEL CONFLICT DETECTED` and narrow/wait rather than overwriting it.
- [ ] Declare write scope for only the planned files above plus the generated Supabase migration and proof plan. Record `main` SHA as resource identity.
- [ ] Acquire exactly one scope lease using `devsystem/scope_aware_execution_lease_v1.py`; persist it through the authoritative lease ref with CAS. Do not create a second lease if transport/readback is ambiguous.
- [ ] Resolve exact frozen ownership. `runless_v2/app.py` is already ledger-frozen by the prior live-props repair; verify whether `wnba_pra_hub_v3617.py` has any newer ledger/frozen ownership before writing it.
- [ ] Write RED tests that statically fail if any new active speed module contains/imports/calls `sportsgameodds`, `sgo`, `espn`, `espn bet`, `onrender`, or the old Speed V3 detail-bundle endpoint.
- [ ] Write RED tests asserting one page-snapshot assembly calls the certified market-board builder exactly once, returns `consensus_averaging == false`, and preserves exact quote fields.
- [ ] Write RED tests asserting a live-line mismatch produces `MODEL_REFRESH_REQUIRED` and omits line-specific probability/edge/EV/final-card certification for that mismatched quote.
- [ ] Run: `python -m pytest --noconftest -q tests/test_wnba_pra_max_speed_snapshot_v1.py`
- [ ] Verify RED for missing new modules/behavior, not for unrelated harness debt.
- [ ] Commit: `test: lock WNBA PRA max-speed snapshot contract`.

### Task 2: Build a source-clean, line-bound model artifact outside first paint

**Files:**
- Create: `wnba_pra_source_clean_guard_v1.py`
- Create: `wnba_pra_page_model_artifact_v1.py`
- Create/extend: `tests/test_wnba_pra_max_speed_snapshot_v1.py`

**Interfaces:**
- `source_clean_generation()` context/adapter: prevents live SGO/ESPN transports from being reached during artifact generation.
- `build_model_artifact(day: str, season: int = 2026) -> dict[str, Any]`.
- `validate_model_artifact(payload: Mapping[str, Any]) -> dict[str, Any]`.
- Artifact schema version: `wnba_pra_page_model_artifact_v1`.

- [ ] Add tests proving the source-clean guard blocks/neutralizes legacy SGO and ESPN network fallbacks while leaving the preserved calculation path available through approved/current inputs or explicit degraded mathematical fallback.
- [ ] Add fixture tests that build the artifact once and count shared dependencies: one verified slate resolution, one certified market-board read, one base projection generation, and reused player/history inputs rather than per-layer rebuilds.
- [ ] Serialize only render/model state needed by the initial page: game/slate identity, player/team/opponent identity, projection fields, matchup fields, history/variance summaries, stored Monte Carlo result fields, final-card metadata, diagnostics, generation duration, model version, and the exact line each probability row is bound to.
- [ ] Do not serialize fresh sportsbook price as authoritative long-lived state; the Vercel GET route overlays current quotes at read time.
- [ ] Include `generated_at`, `date`, `season`, `schema_version`, `model_version`, `content_hash`, and a `line_bindings` section keyed by stable game/player identity.
- [ ] Run the focused artifact/source tests and verify GREEN.
- [ ] Commit: `feat: add source-clean WNBA PRA model artifact`.

### Task 3: Add private durable artifact storage and the lightweight Vercel snapshot route

**Files:**
- Create: generated Supabase migration from `supabase migration new wnba_pra_page_snapshots_v1`
- Create: `runless_v2/wnba_pra_page_snapshot_store_v1.py`
- Create: `runless_v2/wnba_pra_page_snapshot_v1.py`
- Modify: `runless_v2/app.py` under exact scoped thaw
- Extend: `tests/test_wnba_pra_max_speed_snapshot_v1.py`

**Interfaces:**
- Private table: `runless_v2.wnba_pra_page_snapshots` keyed by `(snapshot_date, season, schema_version)` with JSON artifact, content hash, generated timestamp, model metadata, and updated timestamp.
- `GET /api/v1/wnba/pra/page-snapshot?date=YYYY-MM-DD&season=2026`.
- Protected `POST /api/v1/wnba/pra/page-snapshot/publish` using a dedicated server-side `WNBA_PRA_SNAPSHOT_PUBLISH_TOKEN` and constant-time bearer validation.

- [ ] Before touching Supabase, verify current Supabase changelog/docs for private-schema PostgREST access, migrations, and security behavior. Do not rely on stale assumptions.
- [ ] Generate the migration with the Supabase CLI command above; keep the table in the private `runless_v2` schema. Do not grant `anon` or browser access. Do not use `SECURITY DEFINER` merely to bypass permissions.
- [ ] Implement store read/upsert using existing server-side Settings + service-role `httpx` pattern. Never return or log service-role credentials.
- [ ] Implement publish validation: exact schema/date/season, required line bindings, deterministic content hash, complete payload; reject malformed/partial artifacts.
- [ ] Implement GET assembly: read one durable model artifact, call existing `build_pra_market_board(date, season)` exactly once, then overlay each fresh quote by stable game/player identity and exact line.
- [ ] Set model freshness classes: `FRESH` for age <= 300 seconds; `STALE_SAFE` for 300 < age <= 900 seconds when exact live line still matches; `MODEL_UNAVAILABLE` for no artifact or age > 900 seconds. These TTLs govern slow model context only and do not loosen the market gateway's own freshness rules.
- [ ] For line mismatch, return fresh quote fields and `MODEL_REFRESH_REQUIRED`; do not attach the old line's probability/edge/EV/final-ready state.
- [ ] Return explicit metadata: `service`, `schema_version`, `snapshot_state`, `cache_state`, `model_age_seconds`, `market_capture_at`, `model_generated_at`, `market_board_reads=1`, `consensus_averaging=false`, `refresh_required`, and generation/read timing.
- [ ] Do not add CDN response caching that can outlive market quote freshness; V1 relies on durable model artifact reuse and the current market gateway's certified behavior.
- [ ] Mount only the new router in `runless_v2/app.py`; do not change market/schedule router semantics or `runless_v2/requirements.txt`.
- [ ] Run Supabase test query and security/advisor checks after schema change; prove the Vercel service path can read/write while public client access is absent.
- [ ] Run focused API/store tests and current `tests/test_monster_wnba_pra_vercel_gateway_v1.py`; all must pass.
- [ ] Create/update the exact-head thaw authorization for the changed `runless_v2/app.py` blob once the candidate blob is known; no wildcard thaw.
- [ ] Commit: `feat: add durable WNBA PRA page snapshot API`.

### Task 4: Make Streamlit a one-read thin renderer with bounded degraded fallback

**Files:**
- Create: `wnba_pra_page_snapshot_client_v1.py`
- Create: `wnba_pra_page_snapshot_renderer_v1.py`
- Create: `wnba_pra_page_snapshot_publish_v1.py`
- Modify: `wnba_pra_hub_v3617.py`
- Create: `tests/test_wnba_pra_max_speed_streamlit_v1.py`

**Interfaces:**
- `fetch_page_snapshot(day: str, season: int = 2026) -> dict[str, Any]` uses `https://kyre-runless-proof.vercel.app` only.
- `render_page_snapshot(payload) -> None` renders the board/final-card view without importing the heavy model graph.
- `publish_model_artifact(payload) -> dict[str, Any]` is server-side only; token sourced from environment/Streamlit secrets and never emitted.

- [ ] Write RED tests using import/call sentinels proving the healthy initial path performs exactly one page-snapshot GET and zero calls/imports of `build_product_snapshot`, market-grade, matchup-grade, Monte Carlo, or final-card builders before the initial render.
- [ ] Implement the lightweight GET client with a short bounded timeout and no retry storm. Preserve Kyre API host allow-list behavior; do not call vendors directly.
- [ ] Implement the thin renderer so the healthy page uses the response payload directly. Keep player-detail interaction hooks compatible with the existing Speed V3 path after the board is visible, but do not call that path during initial render.
- [ ] Refactor `wnba_pra_hub_v3617.render_wnba_pra_hub()` into snapshot-first logic. Heavy legacy imports must move inside the explicit degraded-generation function so they are not imported on the healthy first-paint path.
- [ ] `FRESH`: render immediately; no refresh.
- [ ] `STALE_SAFE`: render immediately and start at most one per-date/season background model refresh after first paint.
- [ ] `MODEL_REFRESH_REQUIRED`: render the fresh market quote and safe non-line-bound context immediately; hide/mark line-bound probability/final-card fields as refresh-required; start at most one background refresh.
- [ ] `MODEL_UNAVAILABLE`/snapshot transport failure: display an explicit degraded marker, run the existing correctness-preserving heavy generation exactly once under current Kyre market bridge + source-clean guard, render it, and publish the new artifact. This path is allowed for correctness but is not speed-green.
- [ ] Use an in-process single-flight key for background refresh so Streamlit reruns do not create duplicate refresh threads for the same date/season. Background work must not create another PR/proof/deployment/lease authority.
- [ ] Run Streamlit snapshot tests and relevant existing PRA UI/detail regressions. Confirm healthy initial path has one network read.
- [ ] Commit: `feat: render WNBA PRA from one fast snapshot`.

### Task 5: Prove equivalence, source policy, single-flight behavior, and latency

**Files:**
- Create: `devsystem/wnba_pra_max_speed_profile_v1.py`
- Extend: both new test files

**Interfaces:**
- Deterministic profiler returns JSON with `candidate_sha`, `schema_version`, `cache_state`, `cold_or_warm`, `network_reads`, `market_board_reads`, `backend_ms`, `client_read_ms`, `render_ms`, `total_ms`, and duplicate-refresh count.

- [ ] Add exact-output fixture comparison for same deterministic input and same exact line: snapshot path must preserve projection/matchup/probability/final-card fields from the preserved product model except documented cache/presentation metadata.
- [ ] Add exact quote tests for sportsbook, line, side, American price, market/outcome IDs, and capture time; assert no averaging.
- [ ] Add source-policy scan over all new active speed files for SGO/ESPN/ESPN BET/Render and old detail-bundle dependencies.
- [ ] Add cache matrix tests: fresh, soft stale, hard stale, no artifact, line move, provider degradation, malformed artifact, publish auth failure, duplicate refresh attempt.
- [ ] Add regression proving the existing player-detail Speed V3 behavior remains reachable only after player interaction and is not a dependency of initial render.
- [ ] Benchmark candidate in isolation: warm initial board target < 0.50s; normal fresh < 1.00s; cold Streamlit process with valid durable artifact < 2.00s; return/switch near-instant; initial network reads = 1; market-board reads = 1; duplicate refresh = 0.
- [ ] If a target misses, classify the measured root cause before patching the same lane. Do not lower the target or spawn a second optimization branch.
- [ ] Run focused tests plus `py_compile` on all new/modified Python modules. Keep unrelated full-suite harness debt out of the failure classification unless the candidate caused it.
- [ ] Commit: `test: certify WNBA PRA max-speed equivalence and latency`.

### Task 6: Exact-head Runless proof, one PR, production verification, and GREEN + FROZEN closeout

**Files:**
- Create: `devsystem/runless_proof_plans/monster-wnba-pra-max-speed-snapshot-v1.json`
- Finalization artifacts are written only after production proof through existing Finalization Ledger V2 authority.

**Interfaces:**
- Freeze token: `MONSTER_WNBA_PRA_MAX_SPEED_SNAPSHOT_V1_FROZEN`.
- One exact candidate SHA, one proof ID/receipt, one PR, one merged-main SHA, one Vercel production deployment identity.

- [ ] Write immutable proof plan containing only this workstream's focused tests, static forbidden-source scan, `py_compile`, exact scope/diff checks, Supabase security verification, and performance profiler gates.
- [ ] Re-read `main` immediately before proof. If base drift occurred, reconcile it on the same branch/PR and re-run the same proof gates; do not create a second PR.
- [ ] Verify exact candidate diff contains only declared scope and exact thawed frozen paths. Verify no foreign concurrent mutation landed in net diff.
- [ ] Execute one authoritative Runless proof bound to exact candidate SHA, current main SHA, scope lease, authorization, and proof plan. Do not repeatedly poll or resubmit an unfinished proof.
- [ ] Require terminal `MERGE_AUTHORIZED`, failure class `NONE`, immutable receipt digest, and exact-head `runless-final-gate` success before merge.
- [ ] Open/maintain exactly one PR for `monster-wnba-pra-max-speed-snapshot-v1`; merge only the exact proven head.
- [ ] Verify merged `main` contains the proven candidate and Vercel production is READY on the exact merged SHA. No Render verification path.
- [ ] Live API proof on the current WNBA slate: page-snapshot HTTP 200; current exact sportsbook quote fields; `market_board_reads=1`; no averaging; valid model state; line-mismatch safety; measured endpoint timing.
- [ ] Live Streamlit proof: open WNBA PRA from a cold app/session and from a return navigation path; confirm initial board is produced by the snapshot path, no degraded banner on the healthy case, one initial network read, and accepted latency targets. If browser/UI proof is unavailable, remain below 100% rather than inferring success from API tests.
- [ ] Finalize through Finalization Ledger V2 with exact merged artifact blob hashes, proof receipt, Supabase migration identity, performance evidence, live API/UI evidence, and freeze token above.
- [ ] Re-freeze `runless_v2/app.py` and any other exact path that was thawed; retire the scoped thaw before lease release. Preserve unrelated active thaws/parallel leases.
- [ ] Use Runless closeout to reach canonical `GREEN_FROZEN`, then independently read back proof state, ledger state/hash, merged main, production deployment identity, and freeze token.
- [ ] Release the WNBA speed scope lease only after canonical GREEN_FROZEN readback; verify any parallel NBA holder remains intact.
- [ ] Only then report **🟢🧊 100% — WNBA PRA Maximum-Speed Snapshot V1 GREEN + FROZEN**.

## Definition of Done

The implementation is complete only when production WNBA PRA loads through one Kyre Sports API page-snapshot request on the healthy initial path; exact live sportsbook quotes remain fresh and provider-specific; the preserved model is reused only for its exact certified line; no active speed path uses SGO/ESPN/ESPN BET/Render; latency targets are measured on the exact merged deployment; the required thaw is retired/re-frozen; Finalization Ledger V2 and Runless both read back GREEN_FROZEN; and the scope lease is released without disturbing parallel work.