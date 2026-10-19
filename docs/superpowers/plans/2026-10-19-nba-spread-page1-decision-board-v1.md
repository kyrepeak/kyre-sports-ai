# NBA Spread Page 1 Professional Decision Board V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn NBA Spread Page 1 into a professional, launch-ready decision board that shows truthful verified market data, sportsbook-independent Kyre Fair Spread, market-conditioned cover probability/edge, exact team injuries/logos, and an exact-game analysis handoff without changing the frozen Step-9/Step-10 model contracts.

**Architecture:** Build additive successors around the frozen NBA Spread stack. Keep schedule/model/decision ownership in existing certified layers; add a richer verified sportsbook observation transport, a pure decision-board adapter, exact identity/handoff helpers, then render them through Page V8. Integrate only after shared runtime ownership is free, using the next available Universal Runtime loader and preserving every intervening main-branch route.

**Tech Stack:** Python 3, Streamlit, pytest, requests, Universal Runtime V5, Runless exact-head proof, scope-aware execution leases, frozen-artifact registry, Finalization Ledger V2.

**Spec:** `docs/superpowers/specs/2026-10-19-nba-spread-page1-decision-board-v1-design.md`

## Global Constraints

- Preserve `SPORTSBOOK_PROJECTION_INFLUENCE = 0.0` everywhere.
- Do not change `nba_spread_fair_spread_probability_v1.py` model math, `MIN_TEAM_GAMES`, Step-9 probability math, or `nba_spread_decision_v1.py` thresholds/ranking.
- Do not redesign Page 2. Only bind exact selected-game identity into an existing downstream consumer. If no such consumer exists, classify `PAGE2_CONSUMER_MISSING` and stop rather than inventing Page 2 here.
- Do not rewrite frozen V1/V6/V7 modules for convenience. Prefer additive V2/V8 modules.
- No screenshot/manual line becomes production data.
- No provider fetch per card. Load schedule, market, injury, public-betting, and performance/model payloads at most once per freshness-valid slate refresh and partition in memory.
- `Consensus` requires at least two independent verified sportsbooks. One verified book may display as limited coverage but must never be called consensus or weaken frozen Step-10 rules.
- Human unavailable states stay compact; technical diagnostics stay collapsed.
- Historical failures must be baseline-checked before being classified as regressions.
- Step 2A is mandatory before proof/merge/finalization: one authoritative branch, PR, exact candidate, proof path, and scope lease.
- **Shared-runtime collision gate:** at plan-writing time another isolated workstream owns `app.py` and `universal_runtime_v5_loader_v23.py`. Tasks 1–5 remain NBA-only. Before Task 6, inspect that authoritative holder once. If it is still active, wait for its terminal result; do not steal V23 or overwrite `app.py`. If V23 lands, forward-port latest main and integrate NBA through expected `universal_runtime_v5_loader_v24.py` plus the next NBA terminal overlay, expected `streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v7.py`.

## Planned Files

**Create**
- `tests/test_nba_spread_sportsbook_observations_v2.py`
- `tests/test_nba_spread_decision_board_data_v1.py`
- `tests/test_nba_spread_page1_handoff_v1.py`
- `tests/test_api2_nba_spread_page1_decision_board_v1.py`
- `nba_spread_sportsbook_observations_v2.py`
- `nba_spread_live_data_repair_v2.py`
- `nba_spread_decision_board_data_v1.py`
- `nba_spread_team_identity_v1.py`
- `nba_spread_page1_handoff_v1.py`
- `nba_spread_page_v8.py`
- `devsystem/verify_nba_spread_market_transport_v1.py`
- `devsystem/verify_nba_spread_page1_opener_v1.py`
- `devsystem/runless_proof_plans/api2-nba-spread-page1-decision-board-v1.json`
- `devsystem/task_ledgers/api2-nba-spread-page1-decision-board-v1.json`
- next-free runtime loader/terminal resolved in Task 6 after shared-runtime reconciliation; if V23 lands as expected, use `universal_runtime_v5_loader_v24.py` and `streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v7.py`

**Modify only in Task 6 after the shared-runtime lease is free**
- `app.py`

**Read/reuse, do not rewrite**
- `nba_spread_page_v7.py`, `nba_spread_page_v6.py`
- `nba_spread_live_data_repair_v1.py`, `nba_spread_sportsbook_observations_v1.py`, `nba_spread_market_lines_v1.py`
- `nba_spread_page_v4.py`, `nba_spread_fair_spread_probability_v1.py`
- `nba_spread_page_v5.py`, `nba_spread_decision_v1.py`
- `nba_spread_injury_availability_v1.py`, `nba_spread_public_betting_observations_v1.py`
- Universal Runtime V5 state/nav modules

## Review Focus

Explicitly test these high-risk cases before final review:

1. stale/clock-skewed market snapshot -> marked/gated, never presented as fresh;
2. conflicting duplicate quote from the same sportsbook/game -> fail closed, never average;
3. one-book coverage -> limited coverage, never fake consensus or pick upgrade;
4. fair-ready/market-missing -> Kyre Fair Spread remains visible while cover/edge are gated;
5. repeated handoff -> latest tapped `game_id` wins with no stale prior matchup/cross-sport bleed.

---

## Task 1: Establish RED contract and baseline authority

**Files:** create the four new test files listed above; test existing launch-ready, Step-9, and Step-10 suites.

**Interfaces to lock in RED:**

```python
# nba_spread_sportsbook_observations_v2.py
normalize_sportsgameodds_spread_observations_v2(events, schedule_games, *, retrieved_at_utc) -> list[dict]
load_verified_sportsbook_observations_v2(schedule_games, *, secret_getter, request_get, now_utc=None, timeout=12.0) -> dict

# nba_spread_decision_board_data_v1.py
build_market_by_game(games, payload, *, now_utc) -> dict[str, dict]
build_decision_board_state(games, market_payload, injury_payload, public_payload, *, now_utc, market_history=None) -> dict

# nba_spread_team_identity_v1.py
resolve_nba_team_logo(tricode: str) -> str | None

# nba_spread_page1_handoff_v1.py
build_analysis_params(game) -> dict[str, str]
apply_analysis_handoff(session, query, game) -> dict[str, str]
```

- [ ] Record current `main` SHA, branch head, and current scope holders. Do not claim shared `app.py` scope yet.
- [ ] Run the existing NBA behavioral baseline on untouched main:

```bash
python -m pytest --noconftest -q \
  tests/test_api2_nba_spread_page1_launch_ready_v1.py \
  tests/test_nba_spread_live_data_repair_v1.py \
  tests/test_nba_spread_public_betting_observations_step2_v1.py \
  tests/test_nba_spread_step9_fair_spread_probability_v1.py \
  tests/test_nba_spread_step10_decision_v1.py \
  tests/test_nba_spread_step8_live_final_behavior_v1.py \
  tests/test_nba_spread_step7_injury_availability_v1.py \
  tests/test_nba_spread_provider_resilience_step2_r1.py \
  tests/test_nba_spread_provider_resilience_step3_r1.py
```

Expected: record baseline; do not patch unrelated historical debt.

- [ ] Write RED tests for all four fair/market states, stale data, duplicate conflicts, one-book limited coverage, deterministic two-book median, price validation, injury separation, hidden unavailable public betting, verified-only movement, exact logos, Best Opportunities safety, and opener handoffs.
- [ ] Run:

```bash
python -m pytest --noconftest -q \
  tests/test_nba_spread_sportsbook_observations_v2.py \
  tests/test_nba_spread_decision_board_data_v1.py \
  tests/test_nba_spread_page1_handoff_v1.py \
  tests/test_api2_nba_spread_page1_decision_board_v1.py
```

Expected: RED because the new modules do not exist, not because collection/setup is broken.

- [ ] Commit tests only: `test: define NBA Spread decision board contract`.

## Task 2: Repair and verify the production market transport

**Files:** create `nba_spread_sportsbook_observations_v2.py`, `nba_spread_live_data_repair_v2.py`, `devsystem/verify_nba_spread_market_transport_v1.py`; test `tests/test_nba_spread_sportsbook_observations_v2.py`.

**Accepted row contract:**

```python
{
    "game_key": str,
    "game_date_phoenix": str,
    "away_tricode": str,
    "home_tricode": str,
    "sportsbook": str,
    "away_spread": float,
    "home_spread": float,
    "away_price": int | None,
    "home_price": int | None,
    "observed_at_utc": str | None,
    "retrieved_at_utc": str,
    "source_transport": "SportsGameOdds",
}
```

Use `MAX_MARKET_AGE_SECONDS = 300`. If upstream has no trustworthy observation timestamp, freshness uses the explicit retrieval timestamp; never invent an upstream time.

- [ ] Reuse V1 exact schedule identity and opposite-spread validation.
- [ ] Parse American price only from explicit provider fields verified in the live response. If absent/unvalidated, keep `None`; never assume `-110`.
- [ ] Reject non-finite values, wrong game/date, one-sided pairs, ambiguous identity, and conflicting same-book duplicates.
- [ ] Add retrieval/observation timestamps and stale gating.
- [ ] Build `nba_spread_live_data_repair_v2.py` additively: reuse V1 public-betting/secret discovery, bind the V2 sportsbook loader, edit no frozen V1 file.
- [ ] Build a safe transport verifier that reports credential resolved yes/no, provider result class, exact opener coverage/books/freshness/diagnostics, and never prints the secret.
- [ ] In execution, inspect the production credential path before altering it. If `SPORTSGAMEODDS_API_KEY` exists, probe BOS@DET, PHI@NYK, OKC@SAS. If not, inspect only already-supported/authorized repository market transports; do not add brittle sportsbook browser scraping.
- [ ] If the required credential is genuinely absent and no authorized fallback exists, stop as a launch blocker; do not call GREEN + FROZEN.
- [ ] Run:

```bash
python -m pytest --noconftest -q tests/test_nba_spread_sportsbook_observations_v2.py tests/test_nba_spread_live_data_repair_v1.py
```

Expected: GREEN and V1 regression intact.

- [ ] Commit: `feat: add verified NBA Spread market transport v2`.

## Task 3: Build the pure decision-board adapter

**Files:** create `nba_spread_decision_board_data_v1.py`; test `tests/test_nba_spread_decision_board_data_v1.py`; reuse market-lines + Step-10 modules.

```python
def build_decision_board_state(
    games,
    market_payload,
    injury_payload,
    public_payload,
    *,
    now_utc,
    market_history=None,
) -> dict:
    ...
```

- [ ] Partition market once in memory. >=2 books may use the frozen median consensus semantics. One book becomes `LIMITED`; never label it consensus. Preserve whatever one-book behavior frozen Step-9/10 already permits rather than silently tightening/loosening the model contract.
- [ ] Preserve a verified fair spread even when `cover_verification` is unavailable; fair readiness and cover readiness are independent.
- [ ] Compute a **display-only** point edge only when exact displayed market + verified fair spread exist. Magnitude must match Step-10 `abs(fair_home_spread - market_home_spread)` whenever Step 10 is verified; direction label derives from the selected/displayed side. Never rank or activate from this adapter.
- [ ] Translate raw diagnostics to concise consumer reasons while retaining technical codes separately.
- [ ] Split injuries by away/home team; at most 1–2 already-verified material names per side; no point deductions.
- [ ] Hide public-betting consumer state when unavailable; verified public betting remains non-model context.
- [ ] Render movement only from explicit provider opening/current evidence or time-ordered verified snapshots. Internally retained earliest snapshot is `First seen`, never falsely `Open`.
- [ ] Build Best Opportunities solely by filtering frozen Step-10 `verification=VERIFIED` + `decision_state=PLAY`; do not re-rank.
- [ ] Run:

```bash
python -m pytest --noconftest -q tests/test_nba_spread_decision_board_data_v1.py tests/test_nba_spread_step9_fair_spread_probability_v1.py tests/test_nba_spread_step10_decision_v1.py
```

Expected: GREEN and exact Step-9/10 parity.

- [ ] Commit: `feat: add NBA Spread decision board data adapter`.

## Task 4: Add exact team identity and exact-game handoff

**Files:** create `nba_spread_team_identity_v1.py`, `nba_spread_page1_handoff_v1.py`; test `tests/test_nba_spread_page1_handoff_v1.py`; read Universal Runtime nav/state/URL contracts.

- [ ] Resolve logos only from an exact canonical NBA tricode whitelist to an established logo identity. Unknown/ambiguous code returns `None` so V8 uses a monogram. No fuzzy team matching.
- [ ] Test BOS, DET, PHI, NYK, OKC, SAS and an unknown code.
- [ ] `build_analysis_params(game)` returns exact `{"date": game_date_phoenix, "game_id": game_key}` only when both are valid.
- [ ] `apply_analysis_handoff(...)` replaces stale date/game_id with the latest tapped exact game while preserving `sport=nba`, `market=spread`; never writes another sport or player_id.
- [ ] Test BOS@DET -> PHI@NYK -> OKC@SAS repeated taps; latest identity wins.
- [ ] **Compatibility checkpoint:** identify an existing NBA Spread selected-game consumer of `game_id`. If present, bind to it without redesign. If none exists, stop with `PAGE2_CONSUMER_MISSING` and return for user review; do not build Page 2 here or pretend the button works.
- [ ] Run:

```bash
python -m pytest --noconftest -q tests/test_nba_spread_page1_handoff_v1.py tests/test_universal_sports_nav_url_v1.py
```

- [ ] Commit: `feat: add exact NBA Spread identity and analysis handoff`.

## Task 5: Render Professional Decision Board Page V8

**Files:** create `nba_spread_page_v8.py`; test `tests/test_api2_nba_spread_page1_decision_board_v1.py`; reuse V7, V2 live repair, and decision-board adapter.

- [ ] Build V8 additively. Preserve V7 next-active-slate behavior and frozen Step-9/10 ownership; bind V2 only as verified market transport.
- [ ] Load schedule once, market once, injury once, public betting once per freshness-valid render; partition per game in memory.
- [ ] Render human slate header (`NEXT NBA SLATE • TUE OCT 20`) and one thin freshness row. Public-betting status appears only if verified.
- [ ] Each card shows exact logos/monograms, matchup, Phoenix tip/date, venue, Market, Kyre Fair Spread, Cover Probability, Edge, separated injuries, frozen decision, optional verified movement, and explicit `View Analysis →`.
- [ ] Market rules: `Consensus` only >=2 books; one book says `1 book verified`; price only if verified; stale line explicitly `STALE` and excluded from current market display/decision-board freshness.
- [ ] Fair-ready/market-missing still shows fair spread. Market-ready/fair-missing still shows market while model/cover/edge/pick remain gated.
- [ ] Translate `NO PLAY` into human reasons, not raw diagnostic codes.
- [ ] Best Opportunities only from frozen verified Step-10 PLAY records.
- [ ] Technical diagnostics remain in one collapsed Sources & Diagnostics expander.
- [ ] Responsive layout: <=4 dense metrics desktop; 2x2/stacked mobile; large explicit analysis target; no tiny debug copy.
- [ ] Run focused tests:

```bash
python -m pytest --noconftest -q \
  tests/test_api2_nba_spread_page1_decision_board_v1.py \
  tests/test_nba_spread_decision_board_data_v1.py \
  tests/test_nba_spread_page1_handoff_v1.py
```

- [ ] Run broader NBA behavioral suite and compare only against the Task-1 baseline:

```bash
python -m pytest --noconftest -q \
  tests/test_api2_nba_spread_page1_launch_ready_v1.py \
  tests/test_nba_spread_live_data_repair_v1.py \
  tests/test_nba_spread_public_betting_observations_step2_v1.py \
  tests/test_nba_spread_step9_fair_spread_probability_v1.py \
  tests/test_nba_spread_step10_decision_v1.py \
  tests/test_nba_spread_step8_live_final_behavior_v1.py \
  tests/test_nba_spread_step7_injury_availability_v1.py \
  tests/test_nba_spread_provider_resilience_step2_r1.py \
  tests/test_nba_spread_provider_resilience_step3_r1.py
```

- [ ] Commit: `feat: build NBA Spread professional decision board v1`.

## Task 6: Reconcile shared runtime, wire NBA override, and run launch probes

**Files:** next-free Universal Runtime loader (expected V24 if V23 lands), next NBA terminal overlay (expected `streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v7.py`), `devsystem/verify_nba_spread_page1_opener_v1.py`, Runless proof plan, task ledger; modify `app.py` only here.

- [ ] Inspect current main and scope lease once. If another holder still owns `app.py`/shared loader integration, do not poll/retry or create competing integration. Wait for its terminal state.
- [ ] After release, forward-port this same branch onto latest main and re-run Tasks 1–5 tests.
- [ ] Allocate the next free loader number from latest main. Import the latest prior loader and override **only** `route.sport_id == "nba" and route.market_id == "spread"` to Page V8. Delegate every other route unchanged.
- [ ] Create the matching NBA terminal overlay advancing only loader bindings; no second runtime owner.
- [ ] Update `app.py` only after shared-runtime lease is free, using exact frozen-registry thaw if required.
- [ ] Build opener verifier for BOS@DET, PHI@NYK, OKC@SAS. It reports truthful market/fair/cover/injury states, provider-call counters, and cold/warm timing without fabricating expected lines.
- [ ] Performance contract: market/injury/public provider calls <=1 each per slate refresh, zero provider calls per card, warm data assembly reuses cache. Record measured cold/warm times rather than inventing an unprovable target.
- [ ] Create Runless proof plan with compile, focused tests, NBA behavioral tests, universal nav/runtime tests, market transport probe, opener probe, and provider-call/performance assertions.
- [ ] Freeze token: `API2_NBA_SPREAD_PAGE1_DECISION_BOARD_V1_FROZEN`.
- [ ] Run universal gates:

```bash
python -m pytest --noconftest -q \
  tests/test_universal_sports_nav_controller_v1.py \
  tests/test_universal_sports_nav_url_v1.py \
  tests/test_universal_sports_nav_registry_v1.py \
  tests/test_api2_route_transition_mask_v1.py \
  tests/test_api2_universal_nav_single_owner_speed_v1.py
python -m devsystem.api2_universal_runtime_v5_cert
```

Expected: navigation GREEN and `API2_UNIVERSAL_RUNTIME_V5_CERT_GREEN`.

- [ ] Run live market/opener probes. If an external credential/provider blocker remains, stop per spec; no GREEN + FROZEN claim.
- [ ] Commit integration/proof metadata only after exact-head verification is green.

## Task 7: One exact-head proof, merge, merged-main verification, and freeze

**Systems:** authoritative branch `api2-nba-spread-page1-decision-board-v1`, one PR, Runless V2, frozen-artifact registry, Finalization Ledger V2, scope-aware lease.

- [ ] Re-read `main` once and lock `expected_main_sha`. If main drifted, inspect only intervening commits; forward-port the same branch if safe, then rerun proof commands on the new exact head.
- [ ] Establish/extend one scope lease for the exact write set without overwriting unrelated holders.
- [ ] Open one authoritative PR and bind PR/head, candidate, expected main, lease, authorization, proof plan, freeze token.
- [ ] If registry protection blocks `app.py`, authorize one exact path/blob thaw only.
- [ ] Request Runless proof once. On failure, classify that exact result before retrying; patch root cause on the same branch, then re-prove the new exact head.
- [ ] Mandatory whole-branch review: verify market identity/freshness, no projection contamination, no changed Step-10 thresholds, correct one-book semantics, exact handoff, NBA-only routing, and no shared-runtime regression.
- [ ] Merge only with expected-head SHA protection after `MERGE_AUTHORIZED` for the exact candidate.
- [ ] On the **actual merged-main SHA**, rerun compile, focused decision-board tests, NBA behavioral tests, universal nav/runtime certification, market transport probe, opener probe, and performance/provider-call checks.
- [ ] Forward-port/retire temporary thaw against the actual merged blob.
- [ ] Write immutable finalization record binding candidate SHA, merged SHA, proof digest, freeze token, and all changed blobs. Advance from latest shared ledger revision; never overwrite another workstream’s newer state.
- [ ] Read back record + manifest hash chain; require server closeout `GREEN_FROZEN` / `NONE` with matching manifest hash.
- [ ] Release only this NBA lease and verify zero NBA holders/Runless workstream leases while preserving unrelated holders.
- [ ] Confirm GitHub `main` still equals merged SHA before reporting **🟢 100% GREEN + ❄️ FROZEN**.
