# CFB Game Total — Page 1 Daily Slate V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current human-facing CFB Game Total Page 1 with a mobile-first all-games FBS+FCS Daily Slate for one Phoenix calendar day, while preserving frozen analytics and leaving future Page 2/Page 3 redesign out of scope.

**Architecture:** Build one new Page-1 data/API owner, one pure market-consensus layer, one Streamlit Page-1 owner, and one CFB-only activation context. Reuse the existing exact ESPN FBS/FCS identity foundation, Universal Sports field routing for supported semantic categories, current Kyre Sports API identities/odds, existing team-logo identities, and the current selected-game downstream route; bypass the old two-page presentation context without deleting frozen artifacts. For betting markets, collect only exact-game observations actually present in the existing Kyre/FanDuel feed and in verified ESPN-scoreboard market payloads (including the payload's actual sportsbook/provider identity); treat them as independent only when their provider/book identities differ. Page 1 remains descriptive/contextual only and never changes model/projection/probability/ranking/selection behavior.

**Tech Stack:** Python 3, FastAPI, Streamlit, `zoneinfo`, `httpx`/existing requests patterns, pytest, existing Universal Sports Source Intelligence contracts, existing Runless exact-head proof and Finalization Ledger V2.

**Spec:** `docs/superpowers/specs/2026-10-16-cfb-game-total-page1-daily-slate-v1-design.md`

## Global Constraints

- Workstream: `monster-cfb-game-total-page1-daily-slate-v1`.
- One authoritative mutation chain only; no duplicate branch/PR/proof/deployment/lease path.
- Begin implementation with RED tests before any product/runtime mutation.
- Page 1 includes every discoverable FBS + FCS game whose actual kickoff normalizes to the selected `America/Phoenix` date.
- Missing sportsbook/weather/TV/injury fields render `Unavailable` or `—`; never fabricate.
- `All Games` is the default; filters are presentation-only.
- Strict ordering is by Phoenix kickoff time only.
- Live/current/opening market states remain separate; live data may not overwrite pregame history.
- Sportsbook projection influence remains `0.0`.
- Do not mutate Game Total model/projection/probability/ranking/selection logic.
- Do not redesign selected-game downstream Page 2/Page 3 in this workstream.
- Do not delete frozen old Page-1/Page-2 presentation artifacts; only remove them from the active routing path where required.
- Do not add a page-wide master provider. Use field/category ownership and fail closed on ambiguous identity.
- Do not modify unrelated CFB markets or NFL/NBA/WNBA/MLB product behavior.
- Existing Universal Sports registry/router contracts remain authoritative for supported fields. Weather/venue/broadcast metadata may be attached to verified schedule observations with explicit provenance; this Page-1 mission must not fork a competing global source-router architecture.
- `injuries`/availability must use the existing Universal Sports route semantics when verified observations exist; route readiness alone is not evidence, so no observation means `Unavailable`.
- Live refresh must be bounded and cached; no request storm or repeated blind polling.

## Review Focus

- **Phoenix-day boundary:** games near midnight must be assigned by `America/Phoenix`, not by ESPN/Eastern schedule date; the loader must query enough upstream dates to cover the full Phoenix day and then filter by normalized kickoff.
- **Cross-division games:** FBS-vs-FCS games must survive dedupe and be discoverable through both FBS and FCS filters without being duplicated in `All Games`.
- **Selected-game handoff:** only `View Game` may write downstream selected-event route state; expanding `More`, searching, filtering, or opening/collapsing sections must never navigate.
- **Market disagreement:** multiple sportsbook observations for the same semantic field must not be averaged into a synthetic line; displayed consensus must always be one actually observed verified quote, with explicit `Strong consensus` / `Mixed market` / `Limited coverage` confidence.
- **Live-state mutation:** a live quote/status refresh must not overwrite the stored opening or latest verified pregame market snapshot for that game.

---

## File Structure

### New files

- `sports_api/api/cfb_daily_slate_v1.py` — read-only Page-1 API contract; exact Phoenix-day FBS/FCS slate, game-state/logistics metadata, source provenance, and raw verified market observations.
- `cfb_game_total_page1_daily_slate_market_v1.py` — pure market observation normalization + deterministic observed-quote consensus; no network calls.
- `cfb_game_total_page1_daily_slate_v1.py` — canonical Streamlit Page-1 owner: date/search/filter controls, sections, cards, `More`, bounded refresh, and `View Game` handoff.
- `streamlit_memory_lazy_router_cfb_game_total_page1_daily_slate_v1.py` — temporary CFB-only route context that activates the new Page-1 owner and leaves the selected-game downstream runtime untouched.
- `tests/test_cfb_daily_slate_api_v1.py` — API/data contract tests.
- `tests/test_monster_cfb_game_total_page1_daily_slate_v1.py` — Page-1 presentation/routing regression tests.
- `devsystem/runless_proof_plans/monster-cfb-game-total-page1-daily-slate-v1.json` — exact proof commands/artifacts.
- `devsystem/task_ledgers/monster-cfb-game-total-page1-daily-slate-v1.json` — RED/GREEN/finalization ledger.

### Existing files allowed to change

- `sports_api/api/health.py` — register the new additive CFB Daily Slate router only.
- `streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py` — replace the old active CFB page-order context with the new Daily-Slate context while preserving every NFL Spread seam exactly.

### Protected files

Do not rewrite `cfb_game_total_clean_page_v45.py`, `cfb_game_total_page1_selected_analysis_v1.py`, `cfb_game_total_page2_clean_slate_v1.py`, Game Total model/projection/probability files, or the selected-game runtime solely to build Page 1.

---

### Task 1: RED Contract + Daily-Slate API Data Model

**Files:**
- Create: `tests/test_cfb_daily_slate_api_v1.py`
- Create: `sports_api/api/cfb_daily_slate_v1.py`
- Modify: `sports_api/api/health.py`

**Interfaces:**
- Consumes: existing CFB ESPN FBS/FCS exact-date identity behavior, current Kyre Sports API market feed, market observations exposed inside verified ESPN scoreboard competitions, current team identity conventions, Universal Sports `route_field(...)` for supported fields.
- Produces: `build_daily_slate_payload(selected_phoenix_date: date, *, now_utc: datetime | None = None, scoreboard_payloads: Mapping[tuple[str, int], Mapping[str, Any]] | None = None, market_rows: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]` and `GET /api/v1/cfb/daily-slate?game_date=YYYY-MM-DD`.

- [ ] **Step 1: Write the failing API tests first**

Tests must pin these exact behaviors:
- query FBS group `80` and FCS group `81` for every upstream calendar date needed to cover one complete Phoenix day;
- normalize each kickoff to `America/Phoenix` and exclude games that fall outside the selected Phoenix date;
- dedupe only by verified official event ID;
- preserve one cross-division FBS/FCS matchup as one game with both subdivision tags;
- expose away/home names, exact IDs when available, logo URLs when exact team IDs exist, records/ranks when present, kickoff UTC + Phoenix, venue/city, broadcast, status, scores, quarter/clock, and provider-supplied weather fields when present;
- attach explicit provenance and `fabrication=False`;
- accept partial logistics fields instead of dropping a game;
- fail closed on rows with no authoritative event identity;
- parse raw sportsbook observations from an ESPN competition only when the event ID is exact and the payload includes an actual provider/book identity;
- ingest the current Kyre/FanDuel market row as a separate observation only when it reconciles to the same exact game ID;
- never count two transports of the same sportsbook/provider as two independent sources;
- register `/api/v1/cfb/daily-slate` in the shared API router.

- [ ] **Step 2: Run focused tests and prove RED**

Run: `python -m pytest -q tests/test_cfb_daily_slate_api_v1.py`

Expected: FAIL because `cfb_daily_slate_v1.py` and the route do not exist yet.

- [ ] **Step 3: Implement the minimal API owner**

Implement these named helpers in `sports_api/api/cfb_daily_slate_v1.py`:
- `phoenix_day_utc_bounds(selected_day: date) -> tuple[datetime, datetime]`
- `upstream_scoreboard_dates_for_phoenix_day(selected_day: date) -> tuple[str, ...]`
- `normalize_scoreboard_event(event: Mapping[str, Any], *, subdivision: str) -> dict[str, Any] | None`
- `scoreboard_market_observations(event: Mapping[str, Any]) -> list[dict[str, Any]]`
- `merge_scoreboard_games(rows: Iterable[Mapping[str, Any]], *, selected_day: date) -> list[dict[str, Any]]`
- `build_daily_slate_payload(...) -> dict[str, Any]`
- FastAPI handler `daily_slate(game_date: str = Query(...))`.

Implementation rules:
- use official event ID as the only accepted game identity;
- query/parse both ESPN subdivision groups but do not label ESPN as page-wide authority;
- use current Kyre market feed only as one market-observation source; no model influence;
- accept scoreboard market data only as exact-game observations and preserve the sportsbook/provider identity from the payload rather than labeling the transport itself as the sportsbook;
- return raw market observations keyed to exact game ID rather than forcing consensus in the API;
- preserve provider metadata so the Streamlit market layer can distinguish independent sources;
- if the only verified market evidence is one source, return it as one observation and let the UI label it `Limited coverage`;
- no live refresh loop inside the API handler.

- [ ] **Step 4: Register only the additive router**

In `sports_api/api/health.py`, import the new router and append only its route table beside the existing CFB routers. Do not change startup/lifespan behavior.

- [ ] **Step 5: Run API tests GREEN**

Run: `python -m pytest -q tests/test_cfb_daily_slate_api_v1.py tests/test_render_main_reconciliation_v1.py tests/test_cfb_game_total_v163_server_identity.py`

Expected: PASS.

---

### Task 2: Deterministic Multi-Source Market Context

**Files:**
- Create: `cfb_game_total_page1_daily_slate_market_v1.py`
- Extend test: `tests/test_monster_cfb_game_total_page1_daily_slate_v1.py`

**Interfaces:**
- Consumes: a sequence of exact-game market observations shaped as mappings with `provider_id`, `sportsbook`, `market_type` (`moneyline`, `spread`, `game_total`), `phase` (`opening`, `pregame`, `live`), side/value fields, timestamp, and identity/provenance flags.
- Produces: `build_game_market_context(game_id: str, observations: Sequence[Mapping[str, Any]]) -> dict[str, Any]`.

- [ ] **Step 1: Write failing market tests**

Tests must require:
- no observation without exact game identity is accepted;
- duplicate quotes from the same provider/book do not count as independent consensus even if they arrived through different transports;
- `opening`, latest verified `pregame`, and `live` remain separate buckets;
- displayed current quote is always one observed quote, never an arithmetic synthetic line;
- nearest-to-median observed quote is selected deterministically; ties break by freshest timestamp then stable provider ID;
- `Strong consensus` requires at least two independent verified observations within tolerance;
- `Mixed market` requires at least two independent observations outside tolerance;
- exactly one verified observation yields `Limited coverage`;
- no verified observation yields `Unavailable`;
- sportsbook context declares `SPORTSBOOK_PROJECTION_INFLUENCE = 0.0`.

Pinned tolerances:
- spread disagreement tolerance: `0.5` points;
- game-total disagreement tolerance: `0.5` points;
- moneyline disagreement tolerance: `15` American-odds points on the same side.

- [ ] **Step 2: Run the market tests RED**

Run the exact market test node(s) from `tests/test_monster_cfb_game_total_page1_daily_slate_v1.py`.

Expected: FAIL because the market module does not exist.

- [ ] **Step 3: Implement the pure market functions**

Create:
- `normalize_market_observation(row: Mapping[str, Any]) -> dict[str, Any] | None`
- `select_observed_consensus(rows: Sequence[Mapping[str, Any]], *, tolerance: float) -> dict[str, Any]`
- `build_game_market_context(game_id: str, observations: Sequence[Mapping[str, Any]]) -> dict[str, Any]`

No network calls and no model imports are allowed in this module.

- [ ] **Step 4: Run market tests GREEN**

Expected: PASS with opening/pregame/live preservation and no fabricated line.

---

### Task 3: Canonical Page-1 Daily Slate Owner

**Files:**
- Create: `cfb_game_total_page1_daily_slate_v1.py`
- Create/extend: `tests/test_monster_cfb_game_total_page1_daily_slate_v1.py`

**Interfaces:**
- Consumes: `GET /api/v1/cfb/daily-slate`, exact game rows, `build_game_market_context(...)`, existing Streamlit query/session-state conventions, current selected-event query key `ks_cfb_game_total_event_id`, and existing Universal Sports `injuries` route semantics for availability labels when actual verified observations are present.
- Produces: `render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None)` and `render_cfb_hub(market: str, ...)` for the new Page-1 owner.

- [ ] **Step 1: Write failing Page-1 behavior tests**

Tests must prove:
- page title/subtitle identify `CFB Game Total` and Phoenix time;
- date navigation uses Phoenix dates;
- if the requested day returns zero games, `resolve_effective_slate_date(...)` advances to the next date with games using a bounded forward search and exposes the new date explicitly;
- default filter is `All Games`;
- search and `Live | Upcoming | Ranked | FBS | FCS | Conference` filters only change visibility;
- cross-division games appear in both FBS and FCS filtered views but only once in All Games;
- strict chronological ordering uses Phoenix kickoff only;
- `Live Games` renders first and open;
- next upcoming kickoff window renders open;
- remaining future windows render collapsed;
- `Completed Games` renders collapsed at the bottom;
- compact cards contain teams/logos/records/ranks/kickoff-or-status/score if applicable/TV/weather/ML/spread/total plus separate `More` and `View Game` controls;
- missing fields render `—`/`Unavailable` without removing the card;
- an availability route with no verified injury observation still renders `Unavailable` rather than implying health;
- `More` changes only expansion state;
- only `View Game` emits selected-event route state;
- deep analytics/projection/probability/pace/red-zone/matchup-reasoning surfaces are absent from this owner;
- mobile CSS contains no forced tiny multi-column team-card grid.

Pinned kickoff-window constants in Phoenix time:
- `Early`: before 12:00;
- `Afternoon`: 12:00–16:59;
- `Evening`: 17:00–20:59;
- `Late`: 21:00 and later.

Pinned bounded next-date search: `MAX_FORWARD_SEARCH_DAYS = 21`. If no game date is found within that bound, remain on the requested date and show a truthful `No upcoming games found` state; do not loop indefinitely.

- [ ] **Step 2: Run Page-1 tests RED**

Run: `python -m pytest -q tests/test_monster_cfb_game_total_page1_daily_slate_v1.py`

Expected: FAIL because the canonical Page-1 owner does not exist.

- [ ] **Step 3: Implement Page-1 pure helpers first**

Create these signatures:
- `resolve_effective_slate_date(requested_day: date, loader: Callable[[date], Mapping[str, Any]], *, max_forward_days: int = 21) -> tuple[date, dict[str, Any]]`
- `filter_slate_games(games: Sequence[Mapping[str, Any]], *, search: str = "", filter_name: str = "All Games", conference: str = "") -> list[dict[str, Any]]`
- `kickoff_window(game: Mapping[str, Any]) -> str`
- `group_slate_games(games: Sequence[Mapping[str, Any]], *, now_phoenix: datetime) -> dict[str, list[dict[str, Any]]]`
- `view_game_href(game: Mapping[str, Any], selected_day: date) -> str`

- [ ] **Step 4: Implement the Streamlit presentation**

Requirements:
- one readable vertical card per game on narrow screens;
- no tap-anywhere navigation;
- `More` uses page-local expansion state only;
- `View Game` builds the exact selected-event handoff and preserves sport/market/date query identity;
- quick weather displays provider-supplied weather summary when verified, otherwise `—`;
- detailed weather fields remain `Unavailable` when no verified observation exists;
- availability/injury context is displayed only from actual verified observations from the existing source architecture; route availability alone is not treated as player availability evidence;
- bounded live refresh: cache scheduled slate data for 60 seconds, live-state payload for 20 seconds, and do not introduce a background polling loop; refresh only on Streamlit rerun/user activity or existing bounded rerun mechanism if already present.

- [ ] **Step 5: Run Page-1 tests GREEN**

Expected: PASS.

---

### Task 4: Activate New Page 1 and Retire Old Two-Page Presentation Context from the Live Route

**Files:**
- Create: `streamlit_memory_lazy_router_cfb_game_total_page1_daily_slate_v1.py`
- Modify: `streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py`
- Extend: `tests/test_monster_cfb_game_total_page1_daily_slate_v1.py`

**Interfaces:**
- Consumes: `streamlit_memory_lazy_router_cfb_game_total_page1_unified_repair_v1.PAGE1_REPAIR_ROUTE`, current selected-game router/runtime ownership, existing outer production router.
- Produces: `install_daily_slate_page1()` context manager that sets only the unselected Page-1 owner and restores it in `finally`.

- [ ] **Step 1: Write failing activation tests**

Require:
- new context sets `PAGE1_REPAIR_ROUTE = "cfb_game_total_page1_daily_slate_v1"`;
- new context does **not** mutate the selected-game `SAME_PAGE_RUNTIME` pointer;
- all seams restore in `finally`;
- production outer router imports/uses the new context instead of `install_page_order_cleanup()`;
- current NFL Spread V7 mutations remain byte-for-byte semantically intact;
- old page-order/clean-slate artifacts remain in the repo but are no longer the active unselected CFB Game Total Page-1 authority.

- [ ] **Step 2: Run activation tests RED**

Expected: FAIL because production still wraps with `cfb_page_order.install_page_order_cleanup()`.

- [ ] **Step 3: Implement the minimal activation context**

Create `install_daily_slate_page1()` with one `RLock`, one saved original Page-1 route, one temporary assignment, and one `finally` restoration. Do not patch selected-game runtime, models, providers, or any other sport/market.

Modify `streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py` only to replace the CFB context import/call. Preserve its NFL Spread code unchanged.

- [ ] **Step 4: Run activation + protected routing regressions GREEN**

At minimum:
`python -m pytest -q tests/test_monster_cfb_game_total_page1_daily_slate_v1.py tests/test_monster_cfb_game_total_page_order_cleanup_v1.py tests/test_api2_nfl_spread_v7_live_activation_repair_v1.py tests/test_api2_nfl_spread_autodate_mobile_nav_repair_v1.py`

Where the old page-order regression asserts old active semantics, update/replace only the assertions whose authority is intentionally superseded; retain protection of frozen artifact existence and unrelated behavior.

---

### Task 5: Full Regression, Proof Packet, and GREEN + FROZEN Finalization

**Files:**
- Create: `devsystem/runless_proof_plans/monster-cfb-game-total-page1-daily-slate-v1.json`
- Create: `devsystem/task_ledgers/monster-cfb-game-total-page1-daily-slate-v1.json`
- Include all Page-1/API/activation files as proof artifacts.

**Interfaces:**
- Consumes: exact branch head, focused tests, protected routing regressions, existing Runless transport/finalization path.
- Produces: one exact-head proof, one PR, one merge, one freeze token, canonical read-back, and released scope lease.

- [ ] **Step 1: Record Step 2A + RED evidence before final candidate proof**

Task ledger must record:
- active problem;
- base main SHA;
- authoritative branch/PR/proof path;
- exact allowed mutation scope;
- protected frozen systems;
- RED test candidate/evidence;
- failure classification if any;
- no product code before RED;
- sportsbook projection influence `0.0`.

- [ ] **Step 2: Build the exact proof plan**

Required commands include:
- `python -m py_compile` for every new/modified Python file;
- focused API tests;
- focused Page-1/market/activation tests;
- CFB selected-game route protection tests;
- NFL Spread outer-router protection tests;
- any shared API router reconciliation test affected by `health.py`.

- [ ] **Step 3: Run/obtain one authoritative exact-head Runless proof**

Do not create a second proof request while the first is active. On terminal failure, classify once, patch the root cause on the same branch, then submit only the new exact candidate for proof.

- [ ] **Step 4: Merge only the certified exact head**

Require protected `runless-final-gate`; verify PR head equals certified candidate immediately before merge.

- [ ] **Step 5: Verify merged-main and freeze**

Verify:
- merged main contains the new Daily Slate API/Page-1/router artifacts;
- selected-game downstream runtime remains untouched;
- protected analytics/model files are unchanged;
- unrelated outer-router behavior is unchanged;
- Finalization Ledger V2 records the Page-1 freeze token and exact merged-main SHA;
- unrelated frozen/thaw state is preserved;
- scope lease is released;
- canonical read-back proves terminal GREEN + FROZEN.

Suggested freeze token: `MONSTER_CFB_GAME_TOTAL_PAGE1_DAILY_SLATE_V1_FROZEN`.

---

## Execution Shape

This is **one user-visible product step** even though the plan contains internal TDD tasks. Do not ask the user to re-approve between Tasks 1–5 unless implementation discovery reveals a new architectural dependency that would widen scope beyond this approved Page-1 mission. Internal checkpoints exist only to preserve RED -> GREEN discipline and proof quality.
