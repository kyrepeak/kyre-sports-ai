# WNBA PRA Maximum-Speed Snapshot V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the WNBA PRA initial page and return navigation load at maximum practical speed by serving one render-ready Kyre Sports API snapshot while preserving exact sportsbook freshness, current model semantics, source policy, and GREEN + FROZEN controls.

**Architecture:** Keep the certified Vercel Kyre Sports API market board as the only live sportsbook boundary. Persist a slower-changing, source-clean WNBA PRA model artifact outside the first-paint path, then have a lightweight Vercel page-snapshot endpoint read that artifact once and overlay one fresh certified market-board read. Streamlit performs one page-snapshot GET on the healthy path and renders without importing the heavy preserved model stack. Model probability/final-card fields are line-bound: if the live sportsbook line differs from the artifact's certified line, the endpoint returns the fresh quote with `MODEL_REFRESH_REQUIRED` and never reuses the old probability as if it belonged to the new line. Model refresh is protected by a durable cross-process single-flight lease, not merely an in-process thread flag.

**Tech Stack:** Python 3.13, Streamlit, FastAPI/Pydantic 2, `httpx`/`requests`, existing pandas/NumPy WNBA model stack for out-of-band artifact generation only, existing Vercel Runless deployment, private Supabase `runless_v2` schema for durable artifacts/refresh leases, pytest, existing MONSTER scope lease/frozen-artifact/finalization controls.

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
- The Vercel GET endpoint may read persisted model artifacts and current market data, but it must never run the 5M/10M Monte Carlo stack on request.
- A model artifact is valid for probability/final-card reuse only for the exact certified `(game, player, PRA line)` it was generated against. A moved line is `MODEL_REFRESH_REQUIRED`, not permission to reuse an old probability.
- Existing Speed V3 player-detail endpoints are outside the initial-snapshot dependency graph; the new initial path must not call their ESPN-backed detail/history transport.
- A cold-performance measurement means a cold Streamlit process reading a valid durable artifact. A first-ever empty/hard-stale artifact may use the explicit correctness fallback, but that degraded path does not count as speed-green.
- `runless_v2/app.py` is frozen by `MONSTER_WNBA_PRA_LIVE_PROPS_REPAIR_V1_FROZEN`; modifying its router mount requires exact-head thaw authorization. Keep `runless_v2/requirements.txt`, `runless_v2/wnba_pra_market_v1.py`, `runless_v2/wnba_schedule_v1.py`, `wnba_api_client_v1.py`, and the prior market bridge/context unchanged unless a new evidenced root cause makes a broader thaw unavoidable.
- Frozen-path sequencing is fail-closed: construct the candidate Git objects without advancing the authoritative branch, derive the exact replacement blob and target commit SHA, authorize/read back the exact thaw on the separate authority, and only then CAS-advance the branch to that candidate. Never move the authoritative product branch to an unauthorized frozen-file head.
- No proof or merge may start until exact scope lease and thaw state are read back as authoritative.
- GREEN requires live Streamlit proof on the exact merged deployment, not merely unit tests or API health.

## Review Focus

1. **Fresh quote + stale model mismatch:** a moved live line cannot inherit old model probability, edge, EV, or final-card certification.
2. **Forbidden-source resurrection:** artifact generation cannot reach legacy SGO/ESPN fallbacks even though historical modules still contain those routes.
3. **First-paint regression:** healthy Streamlit path must not import/call heavy projection, matchup, market-grade, Monte Carlo, or final-card builders before rendering.
4. **Duplicate refreshes:** single-flight must work across Streamlit processes/instances, not only inside one Python process.
5. **Frozen mountpoint:** `runless_v2/app.py` cannot become authoritative at a changed head until exact target-head/target-blob thaw authorization exists and is read back.
6. **Supabase security:** artifacts/refresh leases remain private server-side state; no service-role credential or publish token is exposed to clients.
7. **Performance proof quality:** benchmarks report exact SHA, cache state, network-read count, backend timing, Streamlit read/render timing, and schema version. No target is GREEN without measured production evidence.
8. **Source-clean equivalence:** exact-equivalence fixtures use the approved primary data path. If a legacy fixture would have required ESPN fallback, the new path must remain source-clean and explicitly degraded rather than pretending byte-for-byte equivalence.

---

## Planned File Structure

- Create `wnba_pra_source_clean_guard_v1.py` — fail-closed guard/adapter preventing SGO/ESPN transport use during artifact generation.
- Create `wnba_pra_page_model_artifact_v1.py` — build/validate/serialize line-bound model artifacts outside first paint.
- Create `wnba_pra_page_snapshot_publish_v1.py` — authenticated server-side claim/publish/release client with token redaction.
- Create `runless_v2/wnba_pra_page_snapshot_store_v1.py` — private Supabase durable artifact + refresh-lease store.
- Create `runless_v2/wnba_pra_page_snapshot_v1.py` — GET page snapshot and protected refresh/publish endpoints.
- Modify `runless_v2/app.py` — mount one new router under exact scoped thaw.
- Create `wnba_pra_page_snapshot_client_v1.py` — one-read Streamlit client using the certified Vercel Kyre API origin.
- Create `wnba_pra_page_snapshot_renderer_v1.py` — thin render adapter for the returned snapshot.
- Modify `wnba_pra_hub_v3617.py` — snapshot-first page with explicit bounded degraded fallback.
- Create `tests/test_wnba_pra_max_speed_snapshot_v1.py` — source, persistence, freshness, line-binding, exact-quote, auth and durable single-flight tests.
- Create `tests/test_wnba_pra_max_speed_streamlit_v1.py` — one-read/no-heavy-import initial render and fallback tests.
- Create `devsystem/wnba_pra_max_speed_profile_v1.py` — deterministic timing/network-call profiler.
- Create `devsystem/runless_proof_plans/monster-wnba-pra-max-speed-snapshot-v1.json` — immutable exact-head proof plan.
- Create one Supabase migration with `supabase migration new wnba_pra_page_snapshots_v1`; use the exact generated path returned by the CLI instead of inventing a timestamped filename.

### Task 1: Lock Step 2A scope, frozen ownership, and RED contracts

**Files:** Create `tests/test_wnba_pra_max_speed_snapshot_v1.py`; read authoritative ledger/registry/lease state only.

- [ ] Re-read current `main`, speed branch, Finalization Ledger V2, legacy frozen registry, and scope-aware lease immediately before implementation. Detect any overlapping holder as `PARALLEL CONFLICT DETECTED`; narrow/wait rather than overwrite it.
- [ ] Declare exact planned write paths plus the generated migration/proof plan; record current `main` SHA as scope resource identity.
- [ ] Acquire exactly one WNBA speed scope lease using `devsystem/scope_aware_execution_lease_v1.py` and CAS-persist it on the authoritative lease ref. On ambiguous transport, read back before any retry.
- [ ] Resolve exact frozen ownership for every planned modified file. Confirm `runless_v2/app.py` is frozen by the live-props ledger record; verify whether `wnba_pra_hub_v3617.py` has any newer freeze ownership before writing it.
- [ ] Write RED static tests rejecting `sportsgameodds`, active `sgo`, `espn`, `espn bet`, `onrender`, and old Speed V3 detail-bundle dependencies from every new active speed module.
- [ ] Write RED tests requiring one certified market-board read per page-snapshot assembly, `consensus_averaging == false`, and exact quote preservation.
- [ ] Write RED tests requiring live-line mismatch => `MODEL_REFRESH_REQUIRED` with no old line-specific probability/edge/EV/final certification.
- [ ] Write RED concurrency tests requiring two simultaneous refresh claims for the same `(date, season, schema)` to yield exactly one winner.
- [ ] Run `python -m pytest --noconftest -q tests/test_wnba_pra_max_speed_snapshot_v1.py`; verify failures are the missing new behavior, not unrelated harness debt.
- [ ] Commit `test: lock WNBA PRA max-speed snapshot contract`.

### Task 2: Build source-clean, line-bound model artifacts outside first paint

**Files:** Create `wnba_pra_source_clean_guard_v1.py`, `wnba_pra_page_model_artifact_v1.py`; extend focused tests.

**Interfaces:** `source_clean_generation()`, `build_model_artifact(day, season=2026)`, `validate_model_artifact(payload)`; schema `wnba_pra_page_model_artifact_v1`.

- [ ] Test that source-clean generation blocks/neutralizes legacy SGO/ESPN network fallbacks while permitting approved current inputs and non-network mathematical degraded fallback.
- [ ] Characterize the current preserved MC/final-card flow. If exact-line stored MC output is absent, the refresh worker may run the preserved 5M/10M engines exactly as currently defined, but only outside request/first-paint execution.
- [ ] Build one shared generation context: verified slate once, certified market board once, base projection once, reusable approved history/profile inputs once, matchup/market derivations from the shared inputs, MC/final-card outputs once.
- [ ] Serialize game/slate identity, player/team/opponent identity, projection fields, matchup fields, approved history/variance summaries, MC fields, final-card metadata, diagnostics, model/generation metadata, and exact line bindings. Do not treat stored sportsbook price as long-lived authoritative quote data.
- [ ] Add `generated_at`, `date`, `season`, `schema_version`, `model_version`, `content_hash`, source/degradation status, and stable line bindings.
- [ ] Exact-equivalence tests must use fixtures where approved source inputs are available. Separately test forbidden-source fallback: it must mark `DEGRADED_SOURCE_CLEAN` or use the existing non-network fallback, never ESPN.
- [ ] Run focused artifact/source tests GREEN; commit `feat: add source-clean WNBA PRA model artifact`.

### Task 3: Add private durable artifacts, cross-process refresh lease, and lightweight Vercel route

**Files:** generated Supabase migration; create `runless_v2/wnba_pra_page_snapshot_store_v1.py`, `runless_v2/wnba_pra_page_snapshot_v1.py`; prepare frozen `runless_v2/app.py` replacement; extend tests.

**Interfaces:** private table `runless_v2.wnba_pra_page_snapshots`; GET `/api/v1/wnba/pra/page-snapshot`; protected POST `/api/v1/wnba/pra/page-snapshot/refresh/claim`, `/publish`, `/refresh/release` with dedicated `WNBA_PRA_SNAPSHOT_PUBLISH_TOKEN`.

- [ ] Before Supabase work, verify current Supabase changelog/docs for private-schema PostgREST, functions/RPC, migrations and privileges.
- [ ] Generate the migration via CLI. Keep artifacts/leases in private `runless_v2`; grant no `anon`/browser access; do not use `SECURITY DEFINER` merely to solve permissions.
- [ ] Store snapshot artifact/content hash/model metadata plus durable refresh lease fields keyed by `(snapshot_date, season, schema_version)`.
- [ ] Implement an atomic refresh claim in the private schema (prefer `SECURITY INVOKER` under service-role execution) that yields one winner, lease owner/token, fencing generation and expiry. Concurrent claim tests must prove one winner. Expired lease may be reclaimed; live lease may only be renewed/released by its owner/fence.
- [ ] Implement store read/upsert/claim/release using existing server-side Settings + service-role `httpx` pattern. Never return/log service-role credentials.
- [ ] Implement publish/claim/release auth with constant-time bearer validation; reject malformed artifact, wrong lease/fence, schema/date/season mismatch, or bad content hash.
- [ ] Implement GET assembly: one durable artifact read + exactly one existing `build_pra_market_board(date, season)` call; overlay fresh quotes only when stable game/player identity and exact line match.
- [ ] Model freshness: `FRESH` <= 300s; `STALE_SAFE` 300–900s when exact line matches; no artifact or >900s => `MODEL_UNAVAILABLE`. These model TTLs never loosen market quote freshness.
- [ ] Line mismatch => fresh quote + `MODEL_REFRESH_REQUIRED`; omit old line probability/edge/EV/final-ready fields.
- [ ] Response metadata includes schema/service, cache/model state, model age, market capture time, model generated time, `market_board_reads=1`, `consensus_averaging=false`, refresh hint and timing. Use response semantics that do not CDN-cache bookmaker data beyond certified freshness.
- [ ] Run Supabase test query + security/advisor checks; prove server service path can access private state while public client access cannot.
- [ ] Keep `runless_v2/requirements.txt`, market gateway and schedule router byte-identical. Focused API tests plus current live-props gateway regressions must pass.
- [ ] Prepare the new `runless_v2/app.py` blob/tree/commit **without advancing the speed branch ref**. From those Git objects, obtain exact old blob, new blob and target commit SHA. Create/read back the exact frozen-path thaw authorization on the separate authority for that target head/blob pair. Only after it is authoritative, CAS-advance the speed branch to the prepared commit. No wildcard thaw and no unauthorized frozen head.
- [ ] Commit message for the prepared candidate: `feat: add durable WNBA PRA page snapshot API`.

### Task 4: Make Streamlit a one-read renderer with durable single-flight refresh

**Files:** Create `wnba_pra_page_snapshot_client_v1.py`, `wnba_pra_page_snapshot_renderer_v1.py`, `wnba_pra_page_snapshot_publish_v1.py`, `tests/test_wnba_pra_max_speed_streamlit_v1.py`; modify `wnba_pra_hub_v3617.py` (with thaw only if authoritative state proves it frozen).

- [ ] Write RED import/call sentinel tests proving healthy initial render makes exactly one page-snapshot GET and zero calls/imports of product snapshot, market grade, matchup grade, MC or final-card builders before rendering.
- [ ] Implement a lightweight certified-Vercel GET client with bounded timeout/no retry storm and no vendor calls.
- [ ] Implement thin renderer using returned payload directly. Existing player-detail hooks remain compatible after user interaction but are not invoked during initial render.
- [ ] Refactor hub snapshot-first; move heavy legacy imports inside explicit degraded/refresh generation so they are absent from healthy first paint.
- [ ] `FRESH`: render immediately; no refresh.
- [ ] `STALE_SAFE`: render immediately, call protected durable refresh-claim endpoint, and only the winning claim starts one background generation.
- [ ] `MODEL_REFRESH_REQUIRED`: render fresh quote + safe non-line-bound context, hide/mark line-bound probability/final-card fields, claim durable refresh, only winner computes.
- [ ] Background winner runs source-clean artifact generation, publishes with matching lease/fence, then releases/completes. Losers exit without computation. Process death is recovered by lease expiry/fencing.
- [ ] `MODEL_UNAVAILABLE`/snapshot transport failure: show explicit degraded marker, run correctness-preserving heavy generation exactly once under the current Kyre market bridge + source-clean guard, render/publish it. This path is correctness fallback and is not speed-green.
- [ ] Add tests for refresh winner/loser behavior, expired lease recovery, publish fence mismatch, healthy one-read path, and degraded fallback observability.
- [ ] Run focused Streamlit tests and relevant existing PRA UI/detail regressions; commit `feat: render WNBA PRA from one fast snapshot`.

### Task 5: Prove equivalence, source policy, single-flight and latency

**Files:** Create `devsystem/wnba_pra_max_speed_profile_v1.py`; extend new tests.

- [ ] Exact-line deterministic fixtures: compare preserved product outputs against snapshot outputs for projection/matchup/probability/final-card fields except documented cache/presentation metadata.
- [ ] Exact quote tests: sportsbook, line, side, American price, market/outcome IDs, capture time; assert no averaging.
- [ ] Forbidden-source scan across all new active speed files plus runtime sentinels proving SGO/ESPN/ESPN BET/Render are unreachable in the speed generation/read path.
- [ ] Cache/failure matrix: fresh, soft stale, hard stale, no artifact, moved line, provider degradation, malformed artifact, publish auth failure, two concurrent claims, expired claim, stale fence.
- [ ] Prove initial page does not depend on Speed V3 detail endpoint; player detail still works after explicit interaction without becoming part of first-paint timing.
- [ ] Profiler emits `candidate_sha`, schema, cache state, cold/warm class, initial network reads, market-board reads, backend/client/render/total ms, and duplicate-refresh count.
- [ ] Candidate targets: warm <0.50s; normal fresh <1.00s; cold Streamlit process with valid durable artifact <2.00s; return/switch near-instant; initial network reads=1; market-board reads=1; duplicate refresh generations=0.
- [ ] Any miss is classified before patching the same lane; never lower target or create another optimization branch.
- [ ] Run focused tests and `py_compile` for changed Python. Keep unrelated full-suite harness debt outside candidate failure ownership unless this work caused it.
- [ ] Commit `test: certify WNBA PRA max-speed equivalence and latency`.

### Task 6: Exact-head Runless proof, one PR, production proof, GREEN + FROZEN

**Files:** Create `devsystem/runless_proof_plans/monster-wnba-pra-max-speed-snapshot-v1.json`; finalization artifacts only after production proof.

**Freeze token:** `MONSTER_WNBA_PRA_MAX_SPEED_SNAPSHOT_V1_FROZEN`.

- [ ] Proof plan includes only focused tests, forbidden-source/runtime scans, `py_compile`, exact scope/diff/thaw checks, Supabase security checks and performance profiler gates.
- [ ] Re-read `main` before proof. Reconcile base drift on the same branch/PR and re-prove; never create a second PR.
- [ ] Verify candidate net diff exactly equals declared scope and every changed frozen path has exact-head/exact-blob thaw authorization. Remove any foreign concurrent net mutation before proof.
- [ ] Execute one authoritative Runless proof bound to exact candidate/main SHA, scope lease, authorization and plan. Do not repeatedly poll/resubmit unfinished proof.
- [ ] Require terminal `MERGE_AUTHORIZED`, failure `NONE`, immutable receipt digest, and exact-head `runless-final-gate` success.
- [ ] Maintain exactly one PR; merge only the proven head. Verify merged main ancestry and Vercel READY deployment on exact merged SHA. No Render path.
- [ ] Live API proof on current WNBA slate: HTTP 200, current exact quote fields, `market_board_reads=1`, no averaging, valid model/refresh state, moved-line safety, measured timing.
- [ ] Live Streamlit proof: cold app/session with valid durable artifact and return navigation both use the snapshot path; healthy case has no degraded fallback, one initial network read, and accepted latency. If UI proof cannot be obtained, remain below 100%.
- [ ] Finalize through Finalization Ledger V2 with exact merged artifact blobs, proof receipt, migration identity, performance/API/UI evidence and freeze token.
- [ ] Re-freeze every thawed product path. Retire the scoped thaw through its authoritative CAS mechanism after the replacement is durably frozen; preserve unrelated active thaws.
- [ ] Run Runless closeout to canonical `GREEN_FROZEN`, independently read back proof/ledger/merged-main/deployment/freeze identities, then release the WNBA scope lease. Verify parallel NBA holder remains intact.
- [ ] Only then report **🟢🧊 100% — WNBA PRA Maximum-Speed Snapshot V1 GREEN + FROZEN**.

## Definition of Done

Production WNBA PRA loads through one Kyre Sports API page-snapshot request on the healthy initial path; exact live sportsbook quotes remain provider-specific and fresh; model probabilities are reused only for their exact certified line; durable refresh claims prevent cross-process duplicate generation; no active speed path uses SGO/ESPN/ESPN BET/Render; latency targets are measured on the exact merged deployment; all thawed artifacts are re-frozen and thaw authority retired; Finalization Ledger V2 and Runless read back GREEN_FROZEN; and the WNBA scope lease is released without disturbing parallel work.