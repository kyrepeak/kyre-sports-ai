# CFB Player Props Page 1 V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Page 1 of the three-page CFB Player Props experience as a game-first next-slate hub with verified multi-book player-prop coverage, model-ready Kyre signal previews, and an exact selected-game handoff for future Page 2.

**Architecture:** Reuse the existing CFB official schedule + next-active-slate resolver, add one additive canonical `player-props` route, and render a new Page-1-only module through the current Universal Runtime V5 destination loader. Keep sportsbook transport, player identity/history, model preview, and presentation in focused modules so Pages 2 and 3 can reuse the same contracts later without changing Page 1 routing.

**Tech Stack:** Python 3, Streamlit, existing Universal Runtime V5 navigation, existing CFB schedule/identity modules, ESPN public CFB roster + athlete gamelog data, SportsGameOdds `/v2/events` with `leagueID=NCAAF`, existing FanDuel anonymous CFB transport as a verified secondary source when compatible player-prop rows are exposed, pytest, Runless V2 / Finalization Ledger V2.

**Spec:** `docs/superpowers/specs/2026-10-19-cfb-player-props-page1-v1-design.md`

## Global Constraints

- Page 1 only. Do not implement the future Page-2 roster screen or Page-3 Line Lab beyond the stable selected-game handoff contract.
- Add canonical CFB market route `player-props` / `Player Props` with page params `date`, `game_id`.
- Reuse `cfb_universal_next_slate_navigation_v1.resolve_runtime_cfb_slate_date` and `cfb_schedule_v1.games_for_date`; do not create a second schedule owner.
- Canonical navigation identity is official CFB game identity; sportsbook event/player IDs are aliases only.
- Canonical official player identity uses the ESPN CFB team roster endpoint `https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{team_id}/roster` when an ESPN team ID is available.
- Player history uses ESPN's athlete gamelog pattern `https://site.web.api.espn.com/apis/common/v3/sports/football/college-football/athletes/{athlete_id}/gamelog?season={season}` and fails soft when the provider shape is unavailable.
- Display a Kyre prop probability only with at least **4 verified completed-game observations** for that player/market and a finite positive uncertainty result.
- Sportsbook data supplies threshold/price context only and has **0.0 direct influence** on the underlying Kyre projection.
- Never fabricate games, players, sportsbook quotes, injuries, rankings, probabilities, logos, or line movement.
- A real game remains on Page 1 even when no verified player props exist.
- Multi-source merge is field-driven; a weaker/staler fallback may not overwrite a fresher verified observation.
- Use the existing CFB logo owners (`cfb_over_under_logo_resolver_v3.resolve_visuals` first, then `cfb_over_under_logo_resolver_v2.resolve_team_logo`) rather than creating a third logo system.
- Inherit Universal Atomic Navigation V1; no non-selected route prefetch/background render.
- Do not touch `app.py` or any NFL Daily Picks V4-owned file.
- Final freeze token: `MONSTER_CFB_PLAYER_PROPS_PAGE1_V1_FROZEN`.

## Review Focus

1. **Sportsbook row with player name but no safe identity mapping:** reject it from display/model instead of fuzzy-binding it to the wrong player. Task 3 pins this.
2. **Real next-slate game with zero props:** render the game card with `No verified player props posted yet`. Task 5 pins this.
3. **Three-game player sample:** quote may display, but Kyre probability/edge stays unavailable until sample count is at least 4. Task 4 pins this.
4. **Two providers report the same market at different timestamps:** newest verified row wins per sportsbook/side; provenance is retained and fallback cannot clobber a fresher row. Task 3 pins this.
5. **Tap Game A then navigate elsewhere:** Page-1 handoff carries only Game A's official ID for the current route generation and cannot commit after generation drift. Task 2/Task 6 pin this.

---

### Task 0: Step-2A execution authority and non-overlapping scope lease

**Files:**
- Read/claim only: `devsystem/scope_aware_execution_lease_state_v1.json` on `monster-scope-aware-execution-leases`

**Interfaces:**
- Consumes: current `main`, current branch head, live scope-lease registry, current frozen/finalization ownership.
- Produces: exactly one narrow lease for `MONSTER-CFB-PLAYER-PROPS-PAGE1-V1` before any test/product mutation.

- [ ] **Step 1: Read current authority exactly once**

Confirm no existing matching PR/branch/proof chain beyond `monster-cfb-player-props-page1-v1`, record current `main`, current branch head, and current live holders.

- [ ] **Step 2: Build the exact scope**

Declare write paths for:
- `universal_sports_nav_registry_v1.py`
- `universal_runtime_v5_loader_nfl_daily_picks_command_v3.py`
- `cfb_player_props_page1_slate_v1.py`
- `cfb_player_props_page1_handoff_v1.py`
- `cfb_player_props_identity_v1.py`
- `cfb_player_props_sportsgameodds_v1.py`
- `cfb_player_props_fanduel_v1.py`
- `cfb_player_props_market_v1.py`
- `cfb_player_props_history_v1.py`
- `cfb_player_props_model_v1.py`
- `cfb_player_props_page1_v1.py`
- all `tests/test_cfb_player_props_*_v1.py`
- `devsystem/task_ledgers/monster-cfb-player-props-page1-v1.json`
- `devsystem/runless_proof_plans/monster-cfb-player-props-page1-v1.json`

Dependency/shared tokens: `domain:cfb`, `route:cfb:player-props`, `runtime:nfl-daily-picks-v3`.

- [ ] **Step 3: Claim once with CAS**

If the current live scope conflicts, do not create another lane: classify the overlap and continue only non-conflicting/read-only work until the authoritative holder is terminal. If disjoint, persist one lease and read it back once.

---

### Task 1: Canonical CFB Player Props route and lazy destination ownership

**Files:**
- Modify: `universal_sports_nav_registry_v1.py`
- Modify: `universal_runtime_v5_loader_nfl_daily_picks_command_v3.py`
- Test: `tests/test_cfb_player_props_page1_route_v1.py`

**Interfaces:**
- Consumes: `MarketRoute`, `RuntimeRoute`, `DestinationAdapter`, existing upstream `resolve_destination`.
- Produces: canonical route `cfb/player-props`; lazy destination adapter that imports `cfb_player_props_page1_v1` only for that route.

- [ ] **Step 1: Write the failing route tests**

Assert:
- `get_market("cfb", "player-props")` exists;
- label and legacy market are `Player Props`;
- page params are exactly `("date", "game_id")`;
- existing CFB market behavior remains unchanged except the additive route;
- `resolve_destination(RuntimeRoute("cfb", "player-props", ...))` returns an adapter whose source version names `cfb_player_props_page1_v1`;
- non-CFB/non-player-props routes delegate unchanged to upstream.

- [ ] **Step 2: Run RED**

Run: `pytest --noconftest -q tests/test_cfb_player_props_page1_route_v1.py`

Expected: FAIL because the route/adapter does not exist.

- [ ] **Step 3: Add the canonical route**

Append to CFB markets:

```python
_market("player-props", "Player Props", "Player Props", _CFB_KEY, page_params=("date", "game_id"))
```

Do not change the CFB default market.

- [ ] **Step 4: Add the lazy destination**

In `universal_runtime_v5_loader_nfl_daily_picks_command_v3.py`, add a `cfb/player-props` branch ahead of the NFL-specific branch. It returns `DestinationAdapter` with loader `importlib.import_module("cfb_player_props_page1_v1")`, renderer `page.render_cfb_player_props_page1()`, source version `CFB_PLAYER_PROPS_PAGE1_V1`, and TTL `30_000` ms. All other routes delegate unchanged.

- [ ] **Step 5: Run GREEN**

Run: `pytest --noconftest -q tests/test_cfb_player_props_page1_route_v1.py tests/test_universal_sports_nav_registry_v1.py tests/test_universal_sports_nav_url_v1.py`

Expected: PASS.

- [ ] **Step 6: Commit**

Commit: `feat: add CFB player props Page 1 route`

---

### Task 2: Next-active-slate board and exact selected-game handoff

**Files:**
- Create: `cfb_player_props_page1_slate_v1.py`
- Create: `cfb_player_props_page1_handoff_v1.py`
- Test: `tests/test_cfb_player_props_page1_slate_v1.py`
- Test: `tests/test_cfb_player_props_page1_handoff_v1.py`

**Interfaces:**
- Consumes: `cfb_schedule_v1.games_for_date`, `cfb_universal_next_slate_navigation_v1.resolve_runtime_cfb_slate_date`.
- Produces:
  - `load_next_player_prop_slate(*, now_provider: Callable[[], datetime] = ...) -> dict[str, Any]`
  - `normalize_page1_game(game: Mapping[str, Any], slate_date: date) -> dict[str, Any]`
  - `build_selected_game_handoff(game: Mapping[str, Any], *, slate_date: date, generation: int) -> dict[str, Any]`
  - `commit_selected_game_handoff(session: MutableMapping[str, Any], query: MutableMapping[str, Any], handoff: Mapping[str, Any]) -> None`

- [ ] **Step 1: Write failing slate tests**

Assert next date comes from the existing resolver, every verified game on the resolved date survives normalization, official game ID/kickoff are preserved, Phoenix display time is derived without replacing canonical timestamp, and provider failure cannot synthesize games.

- [ ] **Step 2: Write failing handoff tests**

Assert payload includes route version, slate date, official game ID, away/home canonical identity, kickoff timestamp, `market_id="player-props"`, and generation; provider IDs are not navigation keys; Game B replaces Game A atomically; stale generation cannot overwrite a newer handoff.

- [ ] **Step 3: Run RED**

Run: `pytest --noconftest -q tests/test_cfb_player_props_page1_slate_v1.py tests/test_cfb_player_props_page1_handoff_v1.py`

Expected: FAIL because modules are missing.

- [ ] **Step 4: Implement slate + handoff**

Keep normalization/handoff pure. Cache only external schedule reads. Normalize optional rank/team IDs from the existing CFB schedule/ESPN enrichment; absence remains `None`/empty rather than guessed.

- [ ] **Step 5: Run GREEN**

Run the same two files; expected PASS.

- [ ] **Step 6: Commit**

Commit: `feat: add CFB player props slate and game handoff`

---

### Task 3: Verified player identity and multi-book market observation layer

**Files:**
- Create: `cfb_player_props_identity_v1.py`
- Create: `cfb_player_props_sportsgameodds_v1.py`
- Create: `cfb_player_props_fanduel_v1.py`
- Create: `cfb_player_props_market_v1.py`
- Test: `tests/test_cfb_player_props_identity_v1.py`
- Test: `tests/test_cfb_player_props_market_v1.py`

**Interfaces:**
- Consumes: official game/team IDs, ESPN team roster endpoint, SportsGameOdds configured secret path, existing read-only FanDuel CFB fetch helpers.
- Produces:
  - `CanonicalPlayerIdentity`
  - `PropObservation`
  - `build_game_player_index(game: Mapping[str, Any]) -> dict[str, CanonicalPlayerIdentity]`
  - `canonical_market_key(stat_id: str) -> str | None`
  - `fetch_sgo_cfb_player_props(slate_date: date) -> list[dict[str, Any]]`
  - `fetch_fanduel_cfb_player_props(slate_games: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]`
  - `normalize_prop_observation(raw: Mapping[str, Any], identity_index: Mapping[str, CanonicalPlayerIdentity]) -> PropObservation | None`
  - `merge_prop_observations(*sources: Sequence[PropObservation]) -> list[PropObservation]`

- [ ] **Step 1: Write failing identity tests**

Assert ESPN athlete ID is canonical when available, sportsbook player ID is only an alias, team-scoped exact normalized name can bind only when unique, ambiguous same-name players are rejected, and fuzzy similarity never certifies identity.

- [ ] **Step 2: Write failing market tests**

Cover canonical stat IDs: `passing_yards`, `rushing_yards`, `receiving_yards`, `receiving_receptions`, `passing_touchdowns`, `touchdowns`. Assert line is finite, Over/Under pairing is consistent, prices are optional but validated, freshness/provenance survive normalization, and stale fallback cannot overwrite fresher verified rows.

- [ ] **Step 3: Run RED**

Run: `pytest --noconftest -q tests/test_cfb_player_props_identity_v1.py tests/test_cfb_player_props_market_v1.py`

Expected: FAIL because modules are missing.

- [ ] **Step 4: Implement ESPN roster identity**

Fetch each slate team's roster at most once per cache TTL. Build an index keyed by official athlete ID plus deterministic team-scoped normalized aliases. Bind a sportsbook player only when provider ID is already mapped or normalized name resolves to exactly one athlete on the correct team; otherwise reject.

- [ ] **Step 5: Implement SportsGameOdds transport**

Use `https://api.sportsgameodds.com/v2/events`, `leagueID=NCAAF`, `oddsAvailable=true`, bookmaker filter `draftkings,fanduel,betmgm,caesars`, and the six canonical stat IDs with `PLAYER_ID` wildcard and full-game Over/Under sides. Read credentials only through existing secret/env patterns; never log the key.

- [ ] **Step 6: Implement FanDuel secondary transport**

Reuse the existing anonymous CFB FanDuel fetch primitives. Accept only open/pregame player-prop rows that can be bound to an official game and canonical player. Return `[]` when that public surface does not expose compatible player props.

- [ ] **Step 7: Implement normalized merge**

Deduplicate by `(official_game_id, canonical_player_id, market_key, sportsbook, side)` and choose the freshest verified observation. Preserve provider IDs, source, timestamp, and all book-specific lines/prices.

- [ ] **Step 8: Run GREEN**

Run Task-3 tests; expected PASS.

- [ ] **Step 9: Commit**

Commit: `feat: add verified CFB player prop market layer`

---

### Task 4: Official player-history readiness and sportsbook-independent Page-1 signal model

**Files:**
- Create: `cfb_player_props_history_v1.py`
- Create: `cfb_player_props_model_v1.py`
- Test: `tests/test_cfb_player_props_model_v1.py`

**Interfaces:**
- Consumes: canonical ESPN athlete ID, verified completed-game gamelog observations, merged current sportsbook observations.
- Produces:
  - `load_verified_player_history(player: CanonicalPlayerIdentity, market_key: str, *, season: int) -> list[dict[str, Any]]`
  - `build_prop_projection(history: Sequence[Mapping[str, Any]], market_key: str) -> dict[str, Any]`
  - `build_market_consensus(observations: Sequence[PropObservation]) -> dict[str, Any]`
  - `grade_market_line(projection: Mapping[str, Any], consensus: Mapping[str, Any]) -> dict[str, Any]`
  - `build_page1_signal(player, market_key, history, observations) -> dict[str, Any]`

- [ ] **Step 1: Write failing readiness/model tests**

Assert:
- 0–3 verified completed games => `model_ready=False`, no probability, no edge;
- history uses the most recent **8** verified completed games at most;
- projection is independent of sportsbook line/price;
- changing only the consensus line changes threshold probability but not projection;
- zero/non-finite uncertainty => signal unavailable;
- missing paired book prices => probability may exist but market edge is unavailable;
- no injury/status inference is fabricated.

- [ ] **Step 2: Run RED**

Run: `pytest --noconftest -q tests/test_cfb_player_props_model_v1.py`

Expected: FAIL because model/history modules are missing.

- [ ] **Step 3: Implement gamelog history normalization**

Fetch ESPN CFB athlete gamelog by official athlete ID and season with a 300-second cache. Map only completed games to the six canonical market values and keep event ID/source metadata. Return newest-first finite rows.

- [ ] **Step 4: Implement exact Page-1 projection math**

For the most recent `n=min(8, verified_count)` values `x[0..n-1]` newest-first, use weights `w[i]=0.85**i`.

- `projection = sum(w[i]*x[i]) / sum(w)`
- `uncertainty = sqrt(sum(w[i]*(x[i]-projection)**2) / sum(w))`
- Require `n >= 4` and `uncertainty > 0`.

For each player/market, consensus line is the median of current verified sportsbook lines. Model Over probability is `1 - NormalDist(mu=projection, sigma=uncertainty).cdf(consensus_line)`; Under is its complement.

For each sportsbook that has both Over and Under American prices, convert prices to implied probabilities and normalize the pair to no-vig probabilities. Consensus market probability is the arithmetic mean of available no-vig probabilities for the selected side. `edge = model_probability - consensus_market_probability`; when no paired prices exist, edge is `None`.

Select side as Over when Over probability is `>= 0.5`, otherwise Under. Keep projection, uncertainty, probability, consensus line, side, market probability, edge, sample count, and provenance as separate fields.

- [ ] **Step 5: Run GREEN**

Run Task-4 tests; expected PASS.

- [ ] **Step 6: Commit**

Commit: `feat: add CFB player props Page 1 signal model`

---

### Task 5: Professional game-first Page 1 UI

**Files:**
- Create: `cfb_player_props_page1_v1.py`
- Test: `tests/test_cfb_player_props_page1_v1.py`

**Interfaces:**
- Consumes: Task-2 slate/handoff, Task-3 observations, Task-4 signals, existing CFB logo resolvers.
- Produces: `render_cfb_player_props_page1() -> None`.

- [ ] **Step 1: Write failing Page-1 composition tests**

Assert markers prove one `CFB • PLAYER PROPS` owner, next-active-slate date/status, every verified game card, verified logos/names/rankings/kickoff, book count + market badges, at most one Top Kyre Signal per game, no signal when model readiness is false, truthful no-props state, exactly one `View Game Props` handoff action per game, no long roster list, tap-only/mobile-safe controls, and responsive cards.

- [ ] **Step 2: Run RED**

Run: `pytest --noconftest -q tests/test_cfb_player_props_page1_v1.py`

Expected: FAIL because Page 1 module is missing.

- [ ] **Step 3: Implement visual/data composition**

Render order:
1. hero/status;
2. filters (`All Games`, `Live Props`, optional position/market, kickoff/edge sort);
3. cards in kickoff order by default;
4. one optional Top Kyre Signal;
5. exact Page-2 handoff button.

Resolve visuals with `cfb_over_under_logo_resolver_v3.resolve_visuals(game)` first and V2 `resolve_team_logo(...)` only for a missing side. Never replace canonical team/game identity with a logo-provider identity.

For each game, group observations by player/market. Build consensus/model signal only for model-ready groups. Rank Top Kyre Signal candidates by: finite positive edge first (largest edge), then higher model probability, then larger verified book count, then deterministic `(player_name, market_key)` tie-break. If no candidate is model-ready, show coverage without a Kyre signal.

Do not add a duplicate site header; Universal Runtime owns it.

- [ ] **Step 4: Run GREEN**

Run Task-5 test; expected PASS.

- [ ] **Step 5: Commit**

Commit: `feat: build CFB player props Page 1 hub`

---

### Task 6: Integration, atomic-navigation regression protection, and Runless proof artifacts

**Files:**
- Create: `devsystem/task_ledgers/monster-cfb-player-props-page1-v1.json`
- Create: `devsystem/runless_proof_plans/monster-cfb-player-props-page1-v1.json`
- Create: `tests/test_cfb_player_props_page1_integration_v1.py`

**Interfaces:**
- Consumes: all Page-1 modules and existing Step-2A / Runless V2 control plane.
- Produces: exact candidate proof plan and final `MONSTER_CFB_PLAYER_PROPS_PAGE1_V1_FROZEN` evidence.

- [ ] **Step 1: Write the failing integration contract**

Assert selected route is only `cfb/player-props`, non-selected destination loaders do not execute, Page 1 uses the existing next-slate owner, selected handoff has the exact official game ID, no `app.py` change is needed, sportsbook projection influence is `0.0`, and no Page-2/Page-3 product module is introduced.

- [ ] **Step 2: Run focused integration + regression gate**

Run:

```bash
pytest --noconftest -q \
  tests/test_cfb_player_props_page1_route_v1.py \
  tests/test_cfb_player_props_page1_slate_v1.py \
  tests/test_cfb_player_props_page1_handoff_v1.py \
  tests/test_cfb_player_props_identity_v1.py \
  tests/test_cfb_player_props_market_v1.py \
  tests/test_cfb_player_props_model_v1.py \
  tests/test_cfb_player_props_page1_v1.py \
  tests/test_cfb_player_props_page1_integration_v1.py \
  tests/test_api2_cfb_universal_next_slate_navigation_v1.py \
  tests/test_universal_sports_nav_registry_v1.py \
  tests/test_universal_sports_nav_controller_v1.py \
  tests/test_universal_sports_nav_url_v1.py \
  tests/test_universal_atomic_navigation_v1.py \
  tests/test_universal_atomic_navigation_terminal_inheritance_v1.py
```

Expected: PASS.

- [ ] **Step 3: Compile + current runtime certification**

Run `python -m py_compile` for every new/modified Python file, then:

```bash
PYTHONPATH=. python devsystem/api2_universal_runtime_v5_cert.py
```

Expected: compile success + `API2_UNIVERSAL_RUNTIME_V5_CERT_GREEN`.

- [ ] **Step 4: Write exact proof artifacts**

Task ledger and Runless proof plan must contain exact source-main SHA, exact candidate SHA, changed paths, no `app.py` ownership, Page-1-only scope, exact test results, and freeze token `MONSTER_CFB_PLAYER_PROPS_PAGE1_V1_FROZEN`.

- [ ] **Step 5: Final Step-2A authority recheck**

Read current `main`, live scope registry, and finalization/frozen ownership once before proof. If a parallel lane now overlaps a changed path, reconcile that authoritative lane first rather than creating another PR/proof path.

- [ ] **Step 6: Execute one authoritative finalization chain**

`exact candidate -> exact-head verification -> one Runless proof request -> immutable receipt -> App 5204253 runless-final-gate -> expected-head merge -> merged-main provenance -> Finalization Ledger V2 freeze/read-back -> Runless closeout GREEN_FROZEN -> scope-lease release/read-back`.

- [ ] **Step 7: Declare terminal status only from durable evidence**

Only after durable Runless state is `GREEN_FROZEN`, failure class is `NONE`, freeze token matches, merged-main SHA matches, and the lane's external scope lease is absent may the step be reported as **100% GREEN + FROZEN**.
