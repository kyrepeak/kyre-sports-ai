# CFB Player Props Page 1 V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Page 1 of the three-page CFB Player Props experience as a game-first next-slate hub with verified multi-book player-prop coverage, model-ready Kyre signal previews, and an exact selected-game handoff for future Page 2.

**Architecture:** Reuse the existing CFB official schedule + next-active-slate resolver, add one additive canonical `player-props` route, and render a new Page-1-only module through the current Universal Runtime V5 destination loader. Keep sportsbook transport, player identity/history, model preview, and presentation in focused modules so Pages 2 and 3 can reuse the same contracts later without changing Page 1 routing.

**Tech Stack:** Python 3, Streamlit, existing Universal Runtime V5 navigation, existing CFB schedule/identity modules, SportsGameOdds `/v2/events` for `leagueID=NCAAF`, existing FanDuel anonymous CFB transport as a verified secondary source when compatible player-prop rows are exposed, pytest, Runless V2 / Finalization Ledger V2.

**Spec:** `docs/superpowers/specs/2026-10-19-cfb-player-props-page1-v1-design.md`

## Global Constraints

- Page 1 only. Do not implement the future Page-2 roster screen or Page-3 Line Lab beyond the stable selected-game handoff contract.
- Add canonical CFB market route `player-props` / `Player Props` with page params `date`, `game_id`.
- Reuse `cfb_universal_next_slate_navigation_v1.resolve_runtime_cfb_slate_date` and `cfb_schedule_v1.games_for_date`; do not create a second schedule owner.
- Canonical navigation identity is official CFB game identity; provider event/player IDs are aliases only.
- Display a Kyre prop probability only with at least **4 verified completed-game observations** for that player/market and a finite projection/uncertainty result.
- Sportsbook data supplies threshold/price context only and has **0.0 direct influence** on the underlying Kyre projection.
- Never fabricate games, players, sportsbook quotes, injuries, rankings, probabilities, logos, or line movement.
- A real game remains on Page 1 even when no verified player props exist.
- Multi-source merge is field-driven; a weaker/staler fallback may not overwrite a fresher verified observation.
- Inherit Universal Atomic Navigation V1; no non-selected route prefetch/background render.
- Do not touch `app.py` or any NFL Daily Picks V4-owned file.
- Final freeze token: `MONSTER_CFB_PLAYER_PROPS_PAGE1_V1_FROZEN`.

## Review Focus

1. **Sportsbook row with player name but no safe identity mapping:** row must be rejected from display/model instead of fuzzy-bound to the wrong player. Task 3 pins this.
2. **Real next-slate game with zero props:** game card must still render with `No verified player props posted yet`. Task 5 pins this.
3. **Three-game player sample:** quote may display, but Kyre probability/edge must remain unavailable until sample count is at least 4. Task 4 pins this.
4. **Two providers report the same market at different timestamps:** newest verified row wins per sportsbook/side; provenance is retained and no fallback clobbers a fresher row. Task 3 pins this.
5. **Tap Game A then quickly navigate elsewhere:** Page-1 handoff must carry only Game A's official ID for the current route generation and must not commit after generation drift. Task 2/Task 6 pin this.

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

Add tests asserting:
- `get_market("cfb", "player-props")` exists;
- label and legacy market are `Player Props`;
- page params are exactly `("date", "game_id")`;
- the previous CFB market IDs remain exactly `moneyline`, `over-under`, `game-total`, `top-picks` plus the additive `player-props` route;
- `resolve_destination(RuntimeRoute("cfb", "player-props", ...))` returns a lazy adapter whose source version names `cfb_player_props_page1_v1`;
- non-CFB/non-player-props routes delegate unchanged to the existing upstream loader.

- [ ] **Step 2: Run test to verify RED**

Run: `pytest --noconftest -q tests/test_cfb_player_props_page1_route_v1.py`

Expected: FAIL because `player-props` and its destination adapter do not exist yet.

- [ ] **Step 3: Add the canonical route**

In `universal_sports_nav_registry_v1.py`, append:

```python
_market("player-props", "Player Props", "Player Props", _CFB_KEY, page_params=("date", "game_id"))
```

Do not change the CFB default market.

- [ ] **Step 4: Add the lazy Page-1 destination**

In `universal_runtime_v5_loader_nfl_daily_picks_command_v3.py`, add a CFB `player-props` branch ahead of the NFL-specific branch:

```python
def resolve_destination(route: RuntimeRoute):
```

For `route.sport_id == "cfb" and route.market_id == "player-props"`, return `DestinationAdapter` with:
- loader: `importlib.import_module("cfb_player_props_page1_v1")`;
- renderer: `page.render_cfb_player_props_page1()`;
- route key: `("cfb", "player-props")`;
- source version: `CFB_PLAYER_PROPS_PAGE1_V1`;
- TTL: `30_000` ms.

All other routes return the existing upstream result unchanged.

- [ ] **Step 5: Run focused tests GREEN**

Run: `pytest --noconftest -q tests/test_cfb_player_props_page1_route_v1.py tests/test_universal_sports_nav_registry_v1.py tests/test_universal_sports_nav_url_v1.py`

Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `feat: add CFB player props Page 1 route`

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

Assert:
- next date comes from the existing resolver using `cfb_schedule_v1.games_for_date`;
- every verified game on that resolved date survives normalization;
- kickoff identity and official game ID are preserved;
- Phoenix display time is derived from canonical kickoff time without replacing canonical timestamp;
- provider failure does not synthesize a schedule.

- [ ] **Step 2: Write failing handoff tests**

Assert:
- payload includes route version, slate date, official game ID, away/home canonical identity, kickoff timestamp, `market_id="player-props"`, and generation;
- provider IDs are absent as the navigation key;
- committing Game B replaces Game A atomically;
- a stale generation cannot overwrite a newer selected-game handoff.

- [ ] **Step 3: Run RED**

Run: `pytest --noconftest -q tests/test_cfb_player_props_page1_slate_v1.py tests/test_cfb_player_props_page1_handoff_v1.py`

Expected: FAIL because modules are missing.

- [ ] **Step 4: Implement slate + handoff modules**

Implement the signatures above. Cache only provider/schedule reads with deliberate short TTLs; keep normalization and handoff functions pure.

- [ ] **Step 5: Run GREEN**

Run the same two files; expected PASS.

- [ ] **Step 6: Commit**

Commit message: `feat: add CFB player props slate and game handoff`

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
- Consumes: official CFB team/game identity, SportsGameOdds configured secret path, existing read-only FanDuel CFB fetch helpers where compatible.
- Produces:
  - `CanonicalPlayerIdentity`
  - `PropObservation`
  - `canonical_market_key(stat_id: str) -> str | None`
  - `fetch_sgo_cfb_player_props(slate_date: date) -> list[dict[str, Any]]`
  - `fetch_fanduel_cfb_player_props(slate_games: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]`
  - `normalize_prop_observation(raw: Mapping[str, Any], identity_index: Mapping[str, CanonicalPlayerIdentity]) -> PropObservation | None`
  - `merge_prop_observations(*sources: Sequence[PropObservation]) -> list[PropObservation]`

- [ ] **Step 1: Write failing identity tests**

Assert:
- official athlete ID is preferred when available;
- provider player ID is stored only as an alias;
- ambiguous same-name players without safe team/player identity are rejected;
- fuzzy name-only matching cannot certify a player.

- [ ] **Step 2: Write failing market tests**

Use fixtures for canonical football markets:
- `passing_yards`
- `rushing_yards`
- `receiving_yards`
- `receiving_receptions`
- `passing_touchdowns`
- `touchdowns`

Assert Over/Under sides normalize to one market/line observation, line is finite, prices are optional but validated when present, freshness/provenance are retained, and stale fallback cannot overwrite a fresher verified row.

- [ ] **Step 3: Run RED**

Run: `pytest --noconftest -q tests/test_cfb_player_props_identity_v1.py tests/test_cfb_player_props_market_v1.py`

Expected: FAIL because modules are missing.

- [ ] **Step 4: Implement SportsGameOdds transport**

Use `https://api.sportsgameodds.com/v2/events`, `leagueID=NCAAF`, `oddsAvailable=true`, and bookmaker filter `draftkings,fanduel,betmgm,caesars` by default. Query only the six canonical player-prop stat IDs above with `PLAYER_ID` wildcard and full-game Over/Under sides. Read credentials only through the existing secret/env pattern; never log the key.

- [ ] **Step 5: Implement FanDuel secondary transport**

Reuse the repository's read-only FanDuel CFB transport primitives. Accept only event/player/market rows that can be bound to an official game + canonical player identity and that are open/pregame. Return an empty list rather than inventing coverage when the public surface does not expose player props.

- [ ] **Step 6: Implement normalized merge**

Deduplicate by `(official_game_id, canonical_player_id, market_key, sportsbook, side)` and choose the freshest verified observation. Preserve source/provider IDs and observed timestamp.

- [ ] **Step 7: Run GREEN**

Run the Task-3 tests; expected PASS.

- [ ] **Step 8: Commit**

Commit message: `feat: add verified CFB player prop market layer`

---

### Task 4: Official player-history readiness and sportsbook-independent Page-1 signal model

**Files:**
- Create: `cfb_player_props_history_v1.py`
- Create: `cfb_player_props_model_v1.py`
- Test: `tests/test_cfb_player_props_model_v1.py`

**Interfaces:**
- Consumes: canonical player/game identity and verified completed-game player-stat observations from official/ESPN-backed CFB data paths.
- Produces:
  - `load_verified_player_history(player: CanonicalPlayerIdentity, market_key: str, *, season: int) -> list[dict[str, Any]]`
  - `build_prop_projection(history: Sequence[Mapping[str, Any]], market_key: str) -> dict[str, Any]`
  - `grade_market_line(projection: Mapping[str, Any], line: float) -> dict[str, Any]`
  - `build_page1_signal(player, market, history, line) -> dict[str, Any]`

- [ ] **Step 1: Write failing readiness/model tests**

Assert:
- 0–3 verified completed games => `model_ready=False`, no probability, no edge;
- 4+ verified games => finite projection and uncertainty are required before a probability is returned;
- sportsbook line changes the threshold probability calculation but does not change the underlying projection value;
- malformed/non-finite history rows are excluded;
- no injury/status inference is fabricated from missing data.

- [ ] **Step 2: Run RED**

Run: `pytest --noconftest -q tests/test_cfb_player_props_model_v1.py`

Expected: FAIL because model/history modules are missing.

- [ ] **Step 3: Implement history normalization**

Map official completed-game stats to the six canonical markets. Keep raw source identity and game IDs in each normalized history row.

- [ ] **Step 4: Implement the Page-1 preview model**

Use a deterministic robust recent/season baseline from verified historical observations only. Return projection, uncertainty, sample count, line probability, side, and edge separately so the projection remains sportsbook-independent.

- [ ] **Step 5: Run GREEN**

Run the Task-4 tests; expected PASS.

- [ ] **Step 6: Commit**

Commit message: `feat: add CFB player props Page 1 signal model`

---

### Task 5: Professional game-first Page 1 UI

**Files:**
- Create: `cfb_player_props_page1_v1.py`
- Test: `tests/test_cfb_player_props_page1_v1.py`

**Interfaces:**
- Consumes: Task-2 slate/handoff, Task-3 observations, Task-4 signals.
- Produces: `render_cfb_player_props_page1() -> None`.

- [ ] **Step 1: Write failing Page-1 composition tests**

Assert source/HTML markers prove:
- one `CFB • PLAYER PROPS` Page-1 owner;
- next-active-slate date/status;
- game cards for every verified slate game;
- logos/names/rankings/kickoff only when verified;
- verified book count + market badges;
- one `Top Kyre Signal` at most per game;
- no signal when model readiness is false;
- `No verified player props posted yet` state for a real game with zero props;
- exactly one `View Game Props` handoff action per game;
- no long roster/player list on Page 1;
- tap-only/mobile-safe controls and responsive card layout.

- [ ] **Step 2: Run RED**

Run: `pytest --noconftest -q tests/test_cfb_player_props_page1_v1.py`

Expected: FAIL because Page 1 module is missing.

- [ ] **Step 3: Implement `render_cfb_player_props_page1()`**

Render order:
1. compact hero/status;
2. filters (`All Games`, `Live Props`, position/market filter where available, kickoff/edge sort);
3. game cards in kickoff order by default;
4. optional top verified signal per game;
5. exact Page-2 handoff button.

Do not add a duplicate site header; Universal Runtime owns the global header/nav.

- [ ] **Step 4: Run GREEN**

Run Task-5 test; expected PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: build CFB player props Page 1 hub`

---

### Task 6: Integration, atomic-navigation regression protection, and Runless proof artifacts

**Files:**
- Create: `devsystem/task_ledgers/monster-cfb-player-props-page1-v1.json`
- Create: `devsystem/runless_proof_plans/monster-cfb-player-props-page1-v1.json`
- Test: `tests/test_cfb_player_props_page1_integration_v1.py`
- Existing regression tests: universal navigation/atomic/runtime + CFB schedule/markets

**Interfaces:**
- Consumes: all prior Page-1 modules and existing Step-2A / Runless V2 control plane.
- Produces: exact candidate proof plan and final `MONSTER_CFB_PLAYER_PROPS_PAGE1_V1_FROZEN` closeout evidence.

- [ ] **Step 1: Write the failing integration contract**

Assert:
- selected route is only `cfb/player-props`;
- non-selected CFB/NFL/NBA/MLB/WNBA destination loaders do not execute;
- Page 1 uses the existing next-slate schedule owner;
- selected game handoff contains the exact official game ID;
- no `app.py` change is required;
- sportsbook projection influence constant is `0.0`;
- Page-2/Page-3 modules are not introduced.

- [ ] **Step 2: Run the focused integration + regression gate**

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

Run `python -m py_compile` for every new/modified Python file, then run the repository's current Universal Runtime V5 certification command used by the active terminal.

Expected: compile success + `API2_UNIVERSAL_RUNTIME_V5_CERT_GREEN`.

- [ ] **Step 4: Write exact proof artifacts**

Task ledger and Runless proof plan must contain:
- exact source-main SHA;
- exact candidate SHA after all tests pass;
- changed paths only;
- no `app.py` ownership;
- Page-1-only scope;
- exact focused test commands/results;
- documented stale historical tests, if any, only after classification;
- freeze token `MONSTER_CFB_PLAYER_PROPS_PAGE1_V1_FROZEN`.

- [ ] **Step 5: Final Step-2A authority recheck**

Read current `main`, current scope-lease registry, frozen-registry/Finalization Ledger ownership, and any existing matching PR exactly once before proof. If a parallel lane now overlaps a changed path, classify and reconcile before proof rather than spawning a duplicate path.

- [ ] **Step 6: Execute one authoritative finalization chain**

`exact candidate -> exact-head verification -> one Runless proof request -> immutable receipt -> App 5204253 runless-final-gate -> expected-head merge -> merged-main provenance -> Finalization Ledger V2 freeze/read-back -> Runless closeout GREEN_FROZEN -> scope-lease release/read-back`.

- [ ] **Step 7: Declare terminal status only from durable evidence**

Only after durable Runless state is `GREEN_FROZEN`, failure class is `NONE`, freeze token matches, merged-main SHA matches, and the lane's external scope lease is absent may the step be reported as **100% GREEN + FROZEN**.
