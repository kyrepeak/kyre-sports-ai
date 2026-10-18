# WNBA PRA FanDuel + Multi-Source Product V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the WNBA PRA page display only exact current FanDuel PRA players/lines for the verified active game while preserving Kyre Sports API ownership and the existing validated projection/probability engine.

**Architecture:** Add a server-side WNBA FanDuel collector that emits the existing canonical prop-feed contract, harden the roster/identity boundary with a durable official-roster cache corroborated by a second live roster source, and integrate FanDuel as a first-class provider without replacing existing providers. Add a freshness-aware API bridge and a read-only FanDuel eligibility layer over the frozen WNBA PRA model, then activate a clean V3.6.16 product successor through the existing compatibility boundary.

**Tech Stack:** Python 3, FastAPI/Kyre Sports API modules, Streamlit, pandas, httpx/urllib, Supabase durable storage, pytest, existing WNBA PRA engine, Render, Runless proof plane.

**Spec:** `docs/superpowers/specs/2026-10-18-wnba-pra-fanduel-multisource-v2-design.md`

## Global Constraints

- Branch authority is exactly `monster-wnba-pra-fanduel-multisource-v2`, created from main `6cd1e17c57eb39cbb35946242f0f3bc604ac09d3`.
- FanDuel owns primary-board player eligibility and the displayed PRA threshold.
- Streamlit reads market truth only through Kyre Sports API; no FanDuel secret/cookie/provider credential is exposed to Streamlit.
- Official/Kyre game and player identity remains canonical. Fallback identity must preserve a previously verified canonical player ID and require independent live corroboration; fuzzy guessing is forbidden.
- Other books/providers are comparison/failover context only and do not override FanDuel visibility or move the model projection.
- Existing projection, Monte Carlo, qualification, ranking, and Final Card selection math remain unchanged.
- Sportsbook prices and consensus remain 0% projection influence.
- Stale, unresolved, conflicting, or unmatched market/player evidence fails closed.
- Universal Runtime V5 is not rewritten.
- No wager execution or stake sizing is added.
- Exactly one PR, one authoritative Runless proof path, one scope lease, and one exact candidate SHA are permitted.
- Do not modify the unrelated Supabase RLS findings in this workstream.
- Target freeze token is `MONSTER_WNBA_PRA_FANDUEL_MULTISOURCE_V2_FROZEN`.

## Review Focus

1. **FanDuel returns a player without a current PRA market:** the player must not appear on the primary PRA board. Task 1 and Task 6 tests pin this.
2. **Official WNBA roster lookup times out while the durable canonical roster is fresh but the corroborating roster disagrees:** the disputed player must fail closed without collapsing unrelated exact players. Task 2 tests pin this.
3. **The only persisted prop snapshot is historical (for example 2026-08-27) while the active slate is later:** the API bridge must report stale/unavailable and must not expose its lines as current. Task 4 tests pin this.
4. **FanDuel and another book publish different PRA thresholds:** FanDuel remains the displayed/evaluated threshold; the other line appears only in comparison diagnostics. Task 5 tests pin this.
5. **FanDuel removes a previously listed player after a refresh:** the next current snapshot must remove that player from the customer board rather than retaining a cached eligibility flag. Task 5 and Task 8 checks pin this.

---

### Task 1: Add the dedicated WNBA FanDuel collector

**Files:**
- Create: `sports_api/collectors/wnba_fanduel_direct.py`
- Create: `sports_api/tests/test_wnba_fanduel_direct.py`

**Interfaces:**
- Consumes:
  - FanDuel anonymous sportsbook JSON transport pattern established by `sports_api/collectors/mlb_fanduel_direct.py`.
  - Existing WNBA canonical feed contract consumed by `sports_api.wnba_prop_line_feed_adapter.build_prop_line_feed_board()`.
- Produces:
  - `FANDUEL_PROVIDER_ID = "fanduel"`
  - `collect_fanduel_wnba_feed(*, date: str | None = None, season: int = 2026, env: Mapping[str, str] | None = None, requester: Callable[..., Any] | None = None) -> dict[str, Any]`
  - Return object fields: `provider_id`, `feed_source`, `feed_format="canonical_offers_v1"`, `odds_format="american"`, `date`, `season`, `collected_at_utc`, `raw_feed={"offers": [...]}`.
  - Each canonical offer preserves `sportsbook="FanDuel"`, `player_name`, optional source `player_id`, `stat="pra"`, `side`, `line`, `american_odds`, `market_captured_at_utc`, `source_event_id`, `source_market_id`, `source_offer_id`, `home_team`, `away_team`.

- [ ] **Step 1: Write failing collector characterization tests**

Add tests named:
- `test_collect_fanduel_wnba_feed_emits_only_pregame_pra_offers`
- `test_collect_fanduel_wnba_feed_preserves_source_ids_and_timestamps`
- `test_collect_fanduel_wnba_feed_does_not_invent_missing_lines`
- `test_collect_fanduel_wnba_feed_handles_attachment_maps_and_lists`
- `test_collect_fanduel_wnba_feed_excludes_non_pra_player_markets`

Use deterministic captured FanDuel-shaped fixtures in the test module; network access is not required for the unit suite.

- [ ] **Step 2: Run collector tests and verify RED**

Run: `python -m pytest --noconftest -q sports_api/tests/test_wnba_fanduel_direct.py`
Expected: FAIL because `sports_api.collectors.wnba_fanduel_direct` does not exist.

- [ ] **Step 3: Implement `collect_fanduel_wnba_feed(...)`**

Use anonymous read-only GETs only. Discover the WNBA landing/event payload through the same public FanDuel sportsbook API family already used by the repository. Parse only pregame player PRA markets; never synthesize a line, player, side, source ID, or timestamp.

- [ ] **Step 4: Run collector tests and verify GREEN**

Run: `python -m pytest --noconftest -q sports_api/tests/test_wnba_fanduel_direct.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_api/collectors/wnba_fanduel_direct.py sports_api/tests/test_wnba_fanduel_direct.py
git commit -m "feat: add WNBA FanDuel PRA collector"
```

---

### Task 2: Add resilient canonical roster identity without weakening exactness

**Files:**
- Create: `sports_api/wnba_roster_identity_resolver_v1.py`
- Create: `sports_api/tests/test_wnba_roster_identity_resolver_v1.py`
- Modify: `sports_api/wnba_prop_line_feed_adapter.py`
- Modify: `sports_api/tests/test_wnba_prop_line_feed_adapter.py`

**Interfaces:**
- Consumes:
  - Primary official roster getter compatible with `sports_api.wnba_rosters.get_current_players_dataset(season, current_roster_only=True)`.
  - `sports_api.wnba_step6r_supabase_storage.SupabaseDurableStorage` byte-object contract (`read_bytes`, `write_bytes_atomic`).
  - Live ESPN WNBA team-roster endpoint as corroboration only.
  - `playable_games` from the already verified daily slate.
- Produces:
  - `ROSTER_CACHE_KEY = "wnba/fanduel/canonical-roster-v1.json"`
  - `resolve_verified_roster(season: int, playable_games: list[dict[str, Any]], *, primary_getter: Callable[..., dict[str, Any]], storage: WNBADurableStorageBackend | None = None, espn_roster_getter: Callable[..., list[dict[str, Any]]] | None = None, now_utc: datetime | None = None) -> dict[str, Any]`
  - Returned roster remains compatible with `_roster_indexes()` in `wnba_prop_line_feed_adapter.py` and contains canonical `player_id`, `full_name`, `team_key`, plus resolution audit metadata.

- [ ] **Step 1: Write failing resolver tests**

Add tests for:
- primary official roster success writes a durable canonical cache;
- primary timeout + fresh durable official cache + exact ESPN name/team agreement returns the cached canonical `player_id`;
- primary timeout + ESPN disagreement removes only the disputed player;
- ambiguous same-name/team mapping fails the player closed;
- stale durable canonical cache is rejected;
- missing durable cache after primary timeout raises a typed not-ready/upstream error.

- [ ] **Step 2: Run resolver tests and verify RED**

Run: `python -m pytest --noconftest -q sports_api/tests/test_wnba_roster_identity_resolver_v1.py`
Expected: FAIL because the resolver module does not exist.

- [ ] **Step 3: Implement `resolve_verified_roster(...)`**

On primary success, validate and atomically cache the official roster. On primary failure, load only a fresh prior official roster and intersect it with exact current ESPN player-name + team membership for teams on `playable_games`; preserve the cached official `player_id`. No fuzzy matching and no ESPN ID substitution for the canonical ID.

- [ ] **Step 4: Integrate the resolver into `build_prop_line_feed_board()` without breaking test injection**

Add an injectable `roster_resolver` parameter while retaining `roster_getter` as the primary getter. The default production path uses `resolve_verified_roster`; existing tests that inject a direct `roster_getter` must remain deterministic.

- [ ] **Step 5: Run identity + existing adapter tests**

Run: `python -m pytest --noconftest -q sports_api/tests/test_wnba_roster_identity_resolver_v1.py sports_api/tests/test_wnba_prop_line_feed_adapter.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sports_api/wnba_roster_identity_resolver_v1.py sports_api/wnba_prop_line_feed_adapter.py sports_api/tests/test_wnba_roster_identity_resolver_v1.py sports_api/tests/test_wnba_prop_line_feed_adapter.py
git commit -m "feat: harden WNBA prop player identity fallback"
```

---

### Task 3: Register FanDuel in provider failover and durable snapshot storage

**Files:**
- Modify: `sports_api/wnba_prop_feed_failover.py`
- Create or modify: `sports_api/tests/test_wnba_prop_feed_failover_fanduel_v1.py`
- Modify only if required by existing status output: the narrow WNBA provider-status/onboarding module that already reports `describe_provider_onboarding()`.

**Interfaces:**
- Consumes:
  - Task 1 `FANDUEL_PROVIDER_ID` and `collect_fanduel_wnba_feed()`.
  - Existing `collect_failover_line_board(...)` and snapshot persister contract.
- Produces:
  - Explicit provider id `fanduel` accepted in `WNBA_PROP_FEED_FAILOVER_ORDER`.
  - `_collect_candidate()` route for `fanduel` returning the same collection contract as existing providers.
  - FanDuel success persists a normal `wnba_step7g_prop_feed_snapshots` row through the existing store; no parallel storage system.

- [ ] **Step 1: Write failing provider integration tests**

Tests assert:
- explicit order `fanduel,kyre` resolves exactly in that order;
- FanDuel collection passes through frozen Step 5M validation before success;
- HTTP success with zero normalized fresh lines is not considered provider success;
- FanDuel snapshot persists before market acceptance;
- FanDuel failure proceeds to the next configured provider without calling two providers concurrently.

- [ ] **Step 2: Run provider tests and verify RED**

Run: `python -m pytest --noconftest -q sports_api/tests/test_wnba_prop_feed_failover_fanduel_v1.py`
Expected: FAIL because `fanduel` is not yet a recognized built-in provider.

- [ ] **Step 3: Implement FanDuel provider registration**

Do not silently change historical default modes. Add first-class support for the explicit failover order and use deployment configuration later in Task 8 to make `fanduel` first for this product.

- [ ] **Step 4: Run provider + frozen failover regressions**

Run: `python -m pytest --noconftest -q sports_api/tests/test_wnba_prop_feed_failover_fanduel_v1.py sports_api/tests/test_wnba_prop_feed_failover.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sports_api/wnba_prop_feed_failover.py sports_api/tests/test_wnba_prop_feed_failover_fanduel_v1.py
git commit -m "feat: add FanDuel to WNBA provider failover"
```

---

### Task 4: Reject stale market snapshots at the Kyre Sports API bridge

**Files:**
- Modify: `wnba_pra_api_market_bridge_v1.py`
- Create: `tests/test_wnba_pra_api_market_bridge_freshness_v2.py`

**Interfaces:**
- Consumes:
  - Existing `/api/v1/wnba/markets/player-props/collection-store/snapshots` payload.
- Produces:
  - `_snapshot_offers(payload: Mapping[str, Any], day_str: str, *, now: datetime | None = None) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]` rejects wrong-date or over-age snapshots.
  - Bridge output adds `snapshot_date`, `collected_at_utc`, `snapshot_age_seconds`, `freshness_state`, `fanduel_offer_count`, and retains `api_owned=True`, `direct_provider_called=False`.
  - Stale active-slate result state is exactly `STALE_STORED_MARKETS`.

- [ ] **Step 1: Write failing freshness tests**

Tests assert:
- a 2026-08-27 snapshot cannot satisfy a 2026-10-19 read;
- a same-date but over-age snapshot is stale;
- a current same-date FanDuel snapshot is accepted;
- accepted rows retain `book="FanDuel"` and source timestamps;
- stale state exposes zero current player-prop rows.

- [ ] **Step 2: Run freshness tests and verify RED**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_api_market_bridge_freshness_v2.py`
Expected: FAIL because the bridge currently accepts dated snapshots without the V2 freshness contract.

- [ ] **Step 3: Implement the freshness gate and metadata**

Use the stored snapshot's own date and collection timestamp; never infer freshness from page load time alone. Historical snapshots remain auditable but cannot become current market truth.

- [ ] **Step 4: Run bridge regression tests**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_api_market_bridge_freshness_v2.py tests/test_wnba_pra_api_market_bridge_v1.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wnba_pra_api_market_bridge_v1.py tests/test_wnba_pra_api_market_bridge_freshness_v2.py
git commit -m "fix: reject stale WNBA API market snapshots"
```

---

### Task 5: Add FanDuel-authoritative eligibility over preserved model outputs

**Files:**
- Create: `wnba_pra_fanduel_eligibility_v1.py`
- Create: `tests/test_wnba_pra_fanduel_eligibility_v1.py`
- Modify: `wnba_pra_product_view_model_v1.py`
- Modify: `tests/test_wnba_pra_product_view_model_v1.py`

**Interfaces:**
- Consumes:
  - `PRAProductSnapshot` from `wnba_pra_product_snapshot_v1`.
  - Existing preserved projection/matchup/Monte Carlo/final-card outputs.
  - Current market rows from the API-owned snapshot path.
- Produces:
  - `FanDuelPRAOffer` dataclass with `game_id`, `player_key`, `player_name`, `line`, `over_odds`, `under_odds`, `captured_at`, `source_event_id`, `evidence_state`.
  - `current_fanduel_pra_offers(market_rows: pd.DataFrame) -> dict[tuple[str, str], FanDuelPRAOffer]`.
  - `PlayerDecisionView` gains `fanduel_eligible: bool`, `fanduel_line: float | None`, `fanduel_over_odds: int | None`, `fanduel_under_odds: int | None`, `market_freshness: str`.
  - `build_player_views(...)` primary output includes only exact FanDuel-eligible players when the V2 successor calls it with `require_fanduel=True`; the predecessor behavior remains available for regression compatibility.

- [ ] **Step 1: Write failing eligibility tests**

Tests assert:
- model projection + no FanDuel PRA offer => excluded from V2 customer board;
- exact FanDuel PRA player/game => included;
- same player name in a different game => excluded;
- FanDuel line wins when another book has a different line;
- other-book quote count/comparison may change evidence metadata but not `fanduel_line`;
- unresolved availability keeps research view but prevents `final_card_selected=True`;
- a second refreshed market frame without the player removes eligibility.

- [ ] **Step 2: Run eligibility tests and verify RED**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_fanduel_eligibility_v1.py`
Expected: FAIL because the eligibility module does not exist.

- [ ] **Step 3: Implement `current_fanduel_pra_offers()` and extend the view model**

Join by exact normalized `game_id + player_key`. FanDuel is the evaluated threshold; comparison books remain metadata only. Do not recompute model projection or Monte Carlo probability.

- [ ] **Step 4: Run eligibility + predecessor view-model tests**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_fanduel_eligibility_v1.py tests/test_wnba_pra_product_view_model_v1.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wnba_pra_fanduel_eligibility_v1.py wnba_pra_product_view_model_v1.py tests/test_wnba_pra_fanduel_eligibility_v1.py tests/test_wnba_pra_product_view_model_v1.py
git commit -m "feat: gate WNBA PRA board by FanDuel eligibility"
```

---

### Task 6: Activate the clean WNBA PRA V3.6.16 successor

**Files:**
- Create: `wnba_pra_product_view_v2.py`
- Create: `wnba_pra_hub_v3616.py`
- Modify: `wnba_pra_hub_v3612.py`
- Create: `tests/test_wnba_pra_fanduel_product_v2.py`
- Create: `tests/test_wnba_pra_fanduel_product_route_v2.py`

**Interfaces:**
- Consumes:
  - V3.6.15 playoff/off-day context and product snapshot.
  - Task 5 FanDuel-gated player views.
  - Existing `wnba_pra_market_consensus_v1` for comparison diagnostics only.
- Produces:
  - `wnba_pra_hub_v3616.render_wnba_pra_hub(...)`.
  - `wnba_pra_product_view_v2.render_pra_product(...)` showing only FanDuel-eligible primary cards.
  - `wnba_pra_hub_v3612` forwards to V3.6.16 and remains the historical application import boundary.

- [ ] **Step 1: Write failing page/route tests**

Tests assert the primary card shows:
- player/headshot/team logo when available;
- matchup;
- `FanDuel PRA` line;
- model PRA projection;
- Over/Under probability;
- edge;
- decision/confidence;
- freshness/evidence badge.

Also assert:
- projection-only players do not render;
- stale market state renders an honest pending message and no current FanDuel line;
- FanDuel absence is never substituted with another book;
- expandable detail includes P/R/A, minutes/role, recent-form/matchup/source sections when verified data exists;
- Advanced Diagnostics stays collapsed;
- compatibility route points V3.6.12 -> V3.6.16.

- [ ] **Step 2: Run page tests and verify RED**

Run: `python -m pytest --noconftest -q tests/test_wnba_pra_fanduel_product_v2.py tests/test_wnba_pra_fanduel_product_route_v2.py`
Expected: FAIL because the V2 page and V3.6.16 hub do not exist.

- [ ] **Step 3: Implement the V2 page and V3.6.16 orchestration**

Keep mobile-first cards compact. Do not expose internal Step numbers, provider machinery, or raw engine diagnostics in the normal customer flow.

- [ ] **Step 4: Advance only the compatibility boundary**

Change `wnba_pra_hub_v3612.py` from `wnba_pra_hub_v3615` to `wnba_pra_hub_v3616`; do not modify Universal Runtime V5.

- [ ] **Step 5: Run page, route, predecessor, and navigation regressions**

Run:
`python -m pytest --noconftest -q tests/test_wnba_pra_fanduel_product_v2.py tests/test_wnba_pra_fanduel_product_route_v2.py tests/test_wnba_pra_playoff_product_e2e_v1.py tests/test_wnba_pra_page_cleanup_v1.py tests/test_universal_sports_nav_controller_v1.py tests/test_universal_sports_nav_url_v1.py tests/test_universal_sports_nav_registry_v1.py tests/test_api2_route_transition_mask_v1.py tests/test_api2_universal_nav_single_owner_speed_v1.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add wnba_pra_product_view_v2.py wnba_pra_hub_v3616.py wnba_pra_hub_v3612.py tests/test_wnba_pra_fanduel_product_v2.py tests/test_wnba_pra_fanduel_product_route_v2.py
git commit -m "feat: activate WNBA PRA FanDuel product V2"
```

---

### Task 7: Build one exact Runless proof candidate and prove it

**Files:**
- Create: `devsystem/runless_proof_plans/monster-wnba-pra-fanduel-multisource-v2.json`
- Test all changed modules and the predecessor regression bundle.

**Interfaces:**
- Consumes: Tasks 1-6 exact branch head.
- Produces: exactly one candidate SHA eligible for merge after authoritative `runless-final-gate` success from App ID `5204253`.

- [ ] **Step 1: Add the Runless proof plan**

The plan must compile every changed Python module and run all Task 1-6 focused tests plus the predecessor WNBA PRA product and universal-navigation regression suites. Set `github_actions_fallback` to `0` and freeze token to `MONSTER_WNBA_PRA_FANDUEL_MULTISOURCE_V2_FROZEN`.

- [ ] **Step 2: Run the complete local/execution-environment verification once**

Expected: all focused + regression tests PASS, compile PASS, no diff outside approved WNBA/Runless-plan scope.

- [ ] **Step 3: Select the exact candidate SHA**

Record branch head SHA after all implementation commits. From this point, any code change invalidates the candidate and requires a new exact candidate; never accept stale-head proof.

- [ ] **Step 4: Request exactly one authoritative Runless proof for that SHA**

Do not create duplicate proof/run/deployment requests. If it fails, classify the terminal failure once, patch the root cause on the same branch, and then produce the next exact candidate sequentially.

- [ ] **Step 5: Verify proof receipt + required check**

Required terminal state: `MERGE_AUTHORIZED` / failure class `NONE`, with `runless-final-gate` successful on the exact candidate SHA.

- [ ] **Step 6: Open exactly one PR and merge only the proven head**

Use expected-head merge protection. Do not merge if PR head differs from the proven candidate.

---

### Task 8: Production market-truth activation, live verification, and GREEN + FROZEN closeout

**Files / systems:**
- Render service backing `https://kyre-sports-api.onrender.com`
- Supabase project `kyre-sports-ai-wnba`
- Frozen registry / Finalization Ledger V2 used by the current MONSTER closeout path

**Interfaces:**
- Consumes: merged main from Task 7.
- Produces: a fresh current-slate FanDuel snapshot, customer-page read-back using that snapshot, final registry transaction, freeze token, and released scope lease.

- [ ] **Step 1: Verify merged main exactly contains the proven candidate**

Read main head and merge parents/PR metadata. If the proven tree is not present exactly, stop; do not continue production activation.

- [ ] **Step 2: Verify Render deployment of merged main**

Reuse the existing Kyre Sports API service. Do not create a new service. Confirm the service is healthy and deployed from the merged main revision before changing provider order.

- [ ] **Step 3: Set the existing API service's explicit WNBA prop provider order to FanDuel first**

Set/merge `WNBA_PROP_FEED_FAILOVER_ORDER=fanduel,kyre` (or include existing additional configured providers after `kyre` if read-back proves they are intentionally active). Do not replace unrelated environment variables.

- [ ] **Step 4: Run exactly one current-slate provider collection through the existing scheduler/collection authority**

Do not manually fabricate/insert a Supabase market snapshot. The persisted row must be produced by the production provider -> validator -> snapshot store path.

- [ ] **Step 5: Read Supabase once for terminal current-slate truth**

Require:
- snapshot `date` equals the active verified WNBA slate date;
- `provider_id`/feed metadata identifies the FanDuel path;
- collection timestamp is current within the configured freshness window;
- normalized offer count > 0 when FanDuel currently offers PRA;
- no stale Aug. 27 snapshot is selected as current;
- unresolved/invalid offers remain excluded/auditable.

If FanDuel currently has no WNBA PRA market, this step must end in an honest `NO_CURRENT_FANDUEL_PRA`/pending customer state rather than fabricating rows; code proof may still be valid but runtime data availability must be reported distinctly.

- [ ] **Step 6: Verify the customer WNBA PRA page consumes the current API snapshot**

Check that only current FanDuel PRA players for the verified game render and that the displayed FanDuel line matches the API snapshot. Re-read after one refresh to prove a removed player is not retained from stale eligibility state.

- [ ] **Step 7: Forward-port/freeze the registry transactionally**

Write `MONSTER_WNBA_PRA_FANDUEL_MULTISOURCE_V2_FROZEN` only after merged-main and production market-truth verification succeed. Preserve predecessor freeze ownership; use an explicit thaw only if the current registry requires it.

- [ ] **Step 8: Canonical read-back + lease release**

Read back merged main, proof receipt, manifest/registry revision and state hash, freeze token, active thaws, and scope lease. Release the scope lease only after the canonical frozen read-back is correct.

- [ ] **Step 9: Declare GREEN + FROZEN**

Required terminal report includes: exact proven candidate SHA, PR, merged-main SHA, Runless proof ID/receipt/check, current FanDuel snapshot identity/timestamp/player count or explicit no-market state, freeze token, manifest revision/hash, active thaws=0, lease released, failure class `NONE`, and no duplicate authority chain.
