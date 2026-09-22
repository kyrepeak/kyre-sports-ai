# NFL Game Totals Multi-Source Data Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace direct ESPN-only acquisition under NFL Game Totals Steps 3–7 with a shared free/open multi-source router that preserves the certified Step-8 projection contract and keeps sportsbook influence at exactly `0.0%`.

**Architecture:** Add one shared router that requests canonical football metrics and delegates to focused provider adapters. nflverse supplies free/open completed-game and play-by-play-derived football data; National Weather Service supplies outdoor U.S. weather; the current verified slate path remains the primary exact game identity path; ESPN remains a last fallback instead of a single point of failure. Steps 3–7 keep their existing public context shapes and classifiers while receiving normalized data plus additive provenance.

**Tech Stack:** Python 3, `requests`, `pandas`, Streamlit cache primitives already present in the repo, pytest, GitHub Actions. No paid provider, no API-key subscription, and no new required secret.

**Spec:** `docs/superpowers/specs/2026-09-15-nfl-game-totals-multisource-data-router-design.md`

## Global Constraints

- No paid data provider, API-key subscription, or metered commercial data dependency.
- Existing certified Step-8 projection math and helper signature remain unchanged.
- FanDuel/sportsbook data remains outside the football-statistics router and retains exactly `0.0%` projection influence.
- Steps 3–7 preserve their existing public output contracts; provenance additions are additive only.
- Fail closed rather than fabricate, guess, average contradictory values, or accept ambiguous provider semantics.
- Provider-specific metrics are eligible only when they match or can be transformed exactly into the canonical definition.
- Adjacent NFL Spread, Moneyline, Passing, Rushing, and Receiving surfaces remain frozen.
- Step 9 market/final-read work is out of scope.

---

## File Structure

### Create

- `sports_api/nfl_data_router_v1.py` — shared metric router, provider priority, validation gate, provenance, cache invalidation registry.
- `sports_api/nfl_data_nflverse_v1.py` — free/open nflverse schedule/team-stat/play-by-play fetch and canonical football metric derivation.
- `sports_api/nfl_data_nws_v1.py` — NWS point/grid weather fetch and exact kickoff-time canonical weather extraction.
- `sports_api/nfl_data_espn_fallback_v1.py` — isolates the existing ESPN transport/extraction behavior so ESPN is a fallback adapter rather than embedded inside Steps 3–7.
- `sports_api/nfl_stadium_coordinates_v1.py` — static canonical NFL stadium coordinate/roof lookup used only when exact slate/venue metadata does not already provide coordinates.
- `tests/test_nfl_data_router_v1.py` — router priority, provenance, validation, all-provider-fail, cache invalidation tests.
- `tests/test_nfl_data_nflverse_v1.py` — deterministic nflverse parsing and metric-derivation tests.
- `tests/test_nfl_data_nws_v1.py` — deterministic NWS points/grid/kickoff extraction tests.
- `tests/test_nfl_game_totals_multisource_step3_7.py` — backward-contract tests for Steps 3–7 and forced fallback behavior.
- `.github/workflows/nfl-game-totals-multisource-router.yml` — targeted tests, compile, exact-scope freeze guard.

### Modify

- `sports_api/nfl_game_totals_scoring_context_v1.py` — replace direct HTTP fetch with router scoring-game request; preserve blending/classifier logic.
- `sports_api/nfl_game_totals_pace_context_v1.py` — replace direct HTTP fetch with router pace metric request; preserve pace classifier.
- `sports_api/nfl_game_totals_explosive_context_v1.py` — replace direct HTTP fetch with router explosive metric request; preserve explosive thresholds.
- `sports_api/nfl_game_totals_red_zone_drive_context_v1.py` — replace direct HTTP fetch with router sustainability metric request; preserve existing thresholds and add optional real drive provenance only.
- `sports_api/nfl_game_totals_environment_context_v1.py` — replace ESPN-only scoreboard/summary transport with router environment request while preserving `classify_weather_pressure` and indoor neutralization.
- `nfl_game_totals_hub_v8_1.py` — extend targeted `Reload Data` cache clearing to router/provider caches only; no projection/UI model change.

### Must remain byte-for-byte unchanged during implementation

- `sports_api/nfl_game_totals_total_projection_v1.py`
- `nfl_game_totals_hub_v8.py`
- NFL Spread, Moneyline, Passing, Rushing, Receiving model/page files.
- `nfl_hub_v18.py` unless a compatibility import is proven necessary; the target design does not require a router bump because V8.1 remains the page runtime.

---

### Task 1: Build the shared router contract and provenance gate

**Files:**
- Create: `sports_api/nfl_data_router_v1.py`
- Test: `tests/test_nfl_data_router_v1.py`

**Interfaces:**
- Produces:
  - `route_metric(metric: str, request: dict[str, Any], providers: tuple[Callable[..., dict[str, Any]], ...]) -> dict[str, Any]`
  - `validate_result(metric: str, result: dict[str, Any]) -> tuple[bool, list[str]]`
  - `register_cache_clearer(name: str, clearer: Callable[[], Any]) -> None`
  - `clear_router_caches() -> list[str]`
- Canonical routed result keys: `ready`, `metric`, `data`, `provider_used`, `fallback_rank`, `data_freshness`, `fields_verified`, `quality`, `diagnostics`, `provider_attempts`.

- [ ] **Step 1: Write failing router-priority and provenance tests**

```python
from sports_api.nfl_data_router_v1 import route_metric


def test_router_falls_back_after_primary_transport_failure():
    def primary(request):
        return {"ready": False, "provider": "primary", "diagnostics": ["403"]}

    def secondary(request):
        return {
            "ready": True,
            "provider": "secondary",
            "data": {"plays_per_game": 65.0, "possession_seconds_per_game": 1812.0},
            "fields_verified": ["plays_per_game", "possession_seconds_per_game"],
            "quality": "HIGH",
            "data_freshness": "2026-09-15T22:00:00Z",
            "diagnostics": [],
        }

    result = route_metric("pace", {"team_abbr": "BUF"}, (primary, secondary))
    assert result["ready"] is True
    assert result["provider_used"] == "secondary"
    assert result["fallback_rank"] == 2
    assert result["provider_attempts"][0]["provider"] == "primary"
```

- [ ] **Step 2: Write failing fail-closed and invalid-range tests**

```python
def test_router_rejects_invalid_metric_shape_instead_of_guessing():
    def bad(request):
        return {
            "ready": True,
            "provider": "bad",
            "data": {"plays_per_game": -4.0, "possession_seconds_per_game": 99999.0},
            "fields_verified": ["plays_per_game", "possession_seconds_per_game"],
            "quality": "HIGH",
            "data_freshness": "2026-09-15T22:00:00Z",
            "diagnostics": [],
        }

    result = route_metric("pace", {"team_abbr": "BUF"}, (bad,))
    assert result["ready"] is False
    assert result["provider_used"] == ""
    assert any("range" in item.lower() for item in result["diagnostics"])
```

- [ ] **Step 3: Run the tests and confirm RED**

Run:

```bash
pytest -q tests/test_nfl_data_router_v1.py
```

Expected: import/file failure because `nfl_data_router_v1.py` does not exist.

- [ ] **Step 4: Implement the minimal router and validation table**

```python
VALIDATORS = {
    "scoring_games": lambda data: isinstance(data.get("games"), list),
    "pace": lambda data: 20.0 <= float(data["plays_per_game"]) <= 100.0 and 600.0 <= float(data["possession_seconds_per_game"]) <= 3000.0,
    "explosive": lambda data: 0.0 <= float(data["explosive_plays_per_game"]) <= 20.0,
    "red_zone_drive": lambda data: 0.0 <= float(data["red_zone_td_pct"]) <= 100.0 and 0.0 <= float(data["third_down_conv_pct"]) <= 100.0 and 0.0 <= float(data["first_downs_per_game"]) <= 60.0,
    "environment": lambda data: bool(data.get("venue_name")) and isinstance(data.get("indoor"), bool),
}
```

`route_metric` must stop at the first valid normalized provider result, preserve every failed attempt in `provider_attempts`, reject `LOW` quality for projection use, and return a canonical fail-closed structure when all providers fail.

- [ ] **Step 5: Add cache registry and explicit invalidation test**

```python
def test_router_cache_registry_clears_only_registered_functions():
    calls = []
    register_cache_clearer("nflverse", lambda: calls.append("nflverse"))
    register_cache_clearer("nws", lambda: calls.append("nws"))
    cleared = clear_router_caches()
    assert cleared == ["nflverse", "nws"]
    assert calls == ["nflverse", "nws"]
```

- [ ] **Step 6: Run tests GREEN and commit**

```bash
pytest -q tests/test_nfl_data_router_v1.py
git add sports_api/nfl_data_router_v1.py tests/test_nfl_data_router_v1.py
git commit -m "feat: add NFL multi-source data router contract"
```

---

### Task 2: Add the nflverse free/open football adapter

**Files:**
- Create: `sports_api/nfl_data_nflverse_v1.py`
- Test: `tests/test_nfl_data_nflverse_v1.py`

**Interfaces:**
- Consumes `requests`/`pandas` only; no new package requirement.
- Produces:
  - `fetch_scoring_games(request: dict[str, Any]) -> dict[str, Any]`
  - `fetch_pace(request: dict[str, Any]) -> dict[str, Any]`
  - `fetch_explosive(request: dict[str, Any]) -> dict[str, Any]`
  - `fetch_red_zone_drive(request: dict[str, Any]) -> dict[str, Any]`
  - cached loaders `_load_games_csv()` and `_load_pbp_csv(season: int)` with `.clear()` compatibility.

**Source URLs:**

```python
NFLVERSE_GAMES_CSV = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
NFLVERSE_PBP_CSV = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz"
```

nflverse documents direct release URLs for season PBP and supports CSV downloads. The adapter must request only the columns it needs when pandas supports `usecols`.

- [ ] **Step 1: Write deterministic parsing tests using in-memory DataFrames**

The test fixture rows must include two completed BUF games and exercise canonical abbreviation cleanup, regular-season filtering, and cutoff-date filtering.

```python
def test_extract_scoring_games_returns_only_completed_regular_games_before_cutoff():
    frame = pd.DataFrame([
        {"season": 2026, "game_type": "REG", "gameday": "2026-09-10", "away_team": "BUF", "home_team": "NYJ", "away_score": 27, "home_score": 17},
        {"season": 2026, "game_type": "REG", "gameday": "2026-09-20", "away_team": "BUF", "home_team": "MIA", "away_score": 0, "home_score": 0},
    ])
    rows = extract_scoring_games(frame, "BUF", 2026, "2026-09-15")
    assert rows == [{"date": "2026-09-10", "pf": 27.0, "pa": 17.0, "opponent_abbr": "NYJ"}]
```

- [ ] **Step 2: Write pace derivation tests**

Canonical offensive play count is `rush + pass + sack` with no-play/penalty-only rows excluded. Possession seconds are derived from unique offensive drives by summing each drive's elapsed possession interval, not by summing play clocks.

```python
def test_derive_pace_counts_offensive_plays_and_unique_drive_possession():
    metrics = derive_pace_metrics(sample_pbp, team_abbr="BUF")
    assert metrics["ready"] is True
    assert metrics["games_played"] == 1
    assert metrics["plays_per_game"] == 6.0
    assert metrics["possession_seconds_per_game"] == 1800.0
```

- [ ] **Step 3: Write explosive derivation tests**

Canonical explosive play for this project: an offensive rush or completed pass with `yards_gained >= 20`, excluding nullified/no-play rows. One play counts once even if multiple indicator fields are set.

```python
def test_derive_explosive_metrics_uses_20_plus_yard_canonical_definition():
    metrics = derive_explosive_metrics(sample_pbp, "BUF")
    assert metrics["ready"] is True
    assert metrics["rushing_big_plays"] == 1.0
    assert metrics["receiving_big_plays"] == 2.0
    assert metrics["explosive_plays_per_game"] == 3.0
```

- [ ] **Step 4: Write red-zone/drive sustainability derivation tests**

Definitions:
- red-zone trip: unique offensive drive with at least one valid play at `yardline_100 <= 20`;
- red-zone TD: that same drive contains an offensive touchdown;
- red-zone TD % = TD red-zone drives / red-zone drives × 100;
- third-down conversion % = valid third-down conversions / valid third-down attempts × 100;
- first downs/game = offensive `first_down == 1` plays per completed game, excluding no-play rows;
- drive count/game = count of unique offensive drives per completed game; additive provenance only, not a Step-8 formula change.

```python
def test_derive_red_zone_drive_metrics_uses_unique_drives():
    metrics = derive_red_zone_drive_metrics(sample_pbp, "BUF")
    assert metrics["ready"] is True
    assert metrics["red_zone_td_pct"] == 50.0
    assert metrics["third_down_conv_pct"] == 40.0
    assert metrics["first_downs_per_game"] == 21.0
    assert metrics["drives_per_game"] == 10.0
```

- [ ] **Step 5: Run RED, implement fetch/load/derive functions, then run GREEN**

```bash
pytest -q tests/test_nfl_data_nflverse_v1.py
```

Implementation requirements:
- regular season only for the current Game Totals contexts;
- cutoff by game date/week so future games never contaminate metrics;
- canonical abbreviations (`JAX`, `LAR`, `LV`, `WAS`, etc.);
- transport timeout of 12 seconds;
- explicit source timestamp/fetch timestamp in provenance;
- `HIGH` quality only when required fields are complete and at least one completed game exists for current-season rate metrics;
- current-year empty data returns unavailable so router can fall back rather than inventing a prior value at adapter level.

- [ ] **Step 6: Commit**

```bash
git add sports_api/nfl_data_nflverse_v1.py tests/test_nfl_data_nflverse_v1.py
git commit -m "feat: add nflverse Game Totals data adapter"
```

---

### Task 3: Add NWS environment adapter and canonical stadium coordinates

**Files:**
- Create: `sports_api/nfl_data_nws_v1.py`
- Create: `sports_api/nfl_stadium_coordinates_v1.py`
- Test: `tests/test_nfl_data_nws_v1.py`

**Interfaces:**
- Produces:
  - `lookup_stadium(venue_name: str, home_abbr: str) -> dict[str, Any] | None`
  - `fetch_environment(request: dict[str, Any]) -> dict[str, Any]`
  - `_points(lat: float, lon: float) -> dict[str, Any]`
  - `_grid_data(url: str) -> dict[str, Any]`
  - `extract_grid_weather(payload: dict[str, Any], kickoff_utc: datetime) -> dict[str, Any]`

**NWS flow:**
1. static canonical stadium lookup supplies `latitude`, `longitude`, `venue_name`, `indoor`;
2. indoor => return ready immediately with `weather_pressure` inputs neutralized;
3. outdoor => `GET https://api.weather.gov/points/{lat},{lon}`;
4. follow `properties.forecastGridData`;
5. select grid values whose ISO-8601 `validTime` interval contains kickoff;
6. convert temperature to Fahrenheit and wind gust to mph when required;
7. output canonical `temperature`, `precipitation`, `gust` fields.

- [ ] **Step 1: Write stadium lookup and indoor-neutralization tests**

```python
def test_indoor_stadium_skips_nws_transport():
    result = fetch_environment({
        "event_id": "x",
        "home_abbr": "DAL",
        "venue_name": "AT&T Stadium",
        "kickoff_utc": "2026-09-20T20:25:00Z",
    }, get_json=forbidden_network_call)
    assert result["ready"] is True
    assert result["data"]["indoor"] is True
    assert result["data"]["weather_applies"] is False
```

- [ ] **Step 2: Write exact kickoff-window NWS extraction test**

```python
def test_nws_grid_values_are_selected_for_kickoff_interval():
    result = extract_grid_weather(grid_payload, datetime(2026, 9, 20, 20, 25, tzinfo=timezone.utc))
    assert result["temperature"] == 72.0
    assert result["precipitation"] == 20.0
    assert result["gust"] == 18.0
```

- [ ] **Step 3: Write missing/ambiguous weather fail-closed test**

If any required outdoor field cannot be resolved for the kickoff interval, return `ready: false` so the router can attempt ESPN fallback; do not substitute zero wind/precipitation.

- [ ] **Step 4: Implement full 32-team home venue coverage**

`nfl_stadium_coordinates_v1.py` must contain one canonical current home venue entry per NFL club, with aliases for shared/alternate naming. Shared stadiums (NYG/NYJ and LAC/LAR) must resolve to the same coordinates. Roof/indoor status must be explicit rather than inferred from venue text.

The implementation test must assert:

```python
assert len({entry["team"] for entry in STADIUMS}) == 32
assert all(-90 <= entry["latitude"] <= 90 for entry in STADIUMS)
assert all(-180 <= entry["longitude"] <= 180 for entry in STADIUMS)
```

- [ ] **Step 5: Run GREEN and commit**

```bash
pytest -q tests/test_nfl_data_nws_v1.py
git add sports_api/nfl_data_nws_v1.py sports_api/nfl_stadium_coordinates_v1.py tests/test_nfl_data_nws_v1.py
git commit -m "feat: add NWS Game Totals environment adapter"
```

---

### Task 4: Isolate ESPN as a fallback adapter

**Files:**
- Create: `sports_api/nfl_data_espn_fallback_v1.py`
- Modify: none of the Step 3–7 modules yet.
- Test: extend `tests/test_nfl_data_router_v1.py`

**Interfaces:**
- Produces `fetch_scoring_games`, `fetch_pace`, `fetch_explosive`, `fetch_red_zone_drive`, and `fetch_environment` functions matching the router provider callable contract.

- [ ] **Step 1: Write tests proving ESPN is rank > 1 and 403 is a recoverable provider failure**

```python
def test_espn_403_is_recorded_as_fallback_event_not_router_failure():
    result = route_metric("environment", request, (nws_provider, espn_provider))
    assert result["ready"] is True
    assert result["provider_used"] == "NWS"
```

And forced primary failure:

```python
def test_espn_can_win_only_after_primary_fails_validation():
    result = route_metric("pace", request, (broken_nflverse, valid_espn))
    assert result["ready"] is True
    assert result["provider_used"].startswith("ESPN")
    assert result["fallback_rank"] == 2
```

- [ ] **Step 2: Move existing ESPN HTTP/extraction logic into the adapter without changing its semantics**

The adapter may reuse private helper logic copied from the existing context modules, but it must return normalized provider results and never call Step-8 projection code.

- [ ] **Step 3: Run GREEN and commit**

```bash
pytest -q tests/test_nfl_data_router_v1.py
git add sports_api/nfl_data_espn_fallback_v1.py tests/test_nfl_data_router_v1.py
git commit -m "refactor: isolate ESPN as Game Totals fallback provider"
```

---

### Task 5: Migrate Step 3 scoring and Step 4 pace to the router

**Files:**
- Modify: `sports_api/nfl_game_totals_scoring_context_v1.py`
- Modify: `sports_api/nfl_game_totals_pace_context_v1.py`
- Test: `tests/test_nfl_game_totals_multisource_step3_7.py`

**Interfaces:**
- Step 3 calls router metric `scoring_games` separately for prior/current seasons, then keeps `_summarize_games`, `_blend`, and `classify_scoring_matchup` unchanged.
- Step 4 calls router metric `pace`, then keeps `classify_opportunity_pace` and `format_possession_clock` unchanged.

- [ ] **Step 1: Write backward-contract tests before modifications**

```python
def test_step3_router_result_preserves_projection_fields(monkeypatch):
    monkeypatch.setattr(scoring, "route_scoring_games", fake_scoring_route)
    result = scoring.build_matchup_scoring_context("BUF", "Buffalo Bills", "MIA", "Miami Dolphins", "2026-09-20")
    assert result["ready"] is True
    assert set(result["away"]) >= {"offense_ppg", "opponent_defense_papg", "signal", "quality"}
    assert result["sportsbook_projection_weight"] == 0.0


def test_step4_router_result_preserves_projection_fields(monkeypatch):
    monkeypatch.setattr(pace, "route_pace", fake_pace_route)
    result = pace.build_matchup_pace_context("BUF", "Buffalo Bills", "MIA", "Miami Dolphins", "2026-09-20")
    assert result["ready"] is True
    assert "average_plays_per_game" in result["matchup"]
    assert result["sportsbook_projection_weight"] == 0.0
```

- [ ] **Step 2: Run RED**

Expected failure because the context modules still perform direct ESPN requests.

- [ ] **Step 3: Replace only acquisition paths**

Do not change Step-3 prior/current blending math, `PRIOR_GAMES`, `LEAGUE_PPG_REF`, or Step-4 `OPPORTUNITY_PACE_REF/BAND`. Add provenance to team/matchup output under `provenance` without removing existing keys.

Provider order:

```python
SCORING_PROVIDERS = (nflverse.fetch_scoring_games, espn.fetch_scoring_games)
PACE_PROVIDERS = (nflverse.fetch_pace, espn.fetch_pace)
```

- [ ] **Step 4: Run targeted + original Step 3/4 tests and commit**

```bash
pytest -q tests/test_nfl_game_totals_multisource_step3_7.py tests/test_nfl_game_totals_page_step3.py tests/test_nfl_game_totals_page_step4.py
git add sports_api/nfl_game_totals_scoring_context_v1.py sports_api/nfl_game_totals_pace_context_v1.py tests/test_nfl_game_totals_multisource_step3_7.py
git commit -m "feat: route Game Totals scoring and pace through multisource data"
```

---

### Task 6: Migrate Step 5 explosive and Step 6 red-zone/drive context

**Files:**
- Modify: `sports_api/nfl_game_totals_explosive_context_v1.py`
- Modify: `sports_api/nfl_game_totals_red_zone_drive_context_v1.py`
- Test: extend `tests/test_nfl_game_totals_multisource_step3_7.py`

**Interfaces:**
- Provider order: nflverse first, ESPN fallback.
- Preserve `EXPLOSIVE_HIGH_REF`, `EXPLOSIVE_LOW_REF`, `RZ_TD_HIGH/LOW`, `THIRD_DOWN_HIGH/LOW`, and `FIRST_DOWNS_HIGH/LOW` exactly.
- `drives_per_game` may be additive in provenance/display data; Step 8 must not consume it until separately approved.

- [ ] **Step 1: Write forced-fallback tests**

```python
def test_step5_survives_primary_failure_with_valid_fallback(monkeypatch):
    monkeypatch.setattr(explosive, "route_explosive", fallback_route)
    result = explosive.build_matchup_explosive_context("BUF", "Buffalo Bills", "MIA", "Miami Dolphins", "2026-09-20")
    assert result["ready"] is True
    assert result["provenance"]["away"]["fallback_rank"] == 2


def test_step6_all_providers_fail_closed(monkeypatch):
    monkeypatch.setattr(redzone, "route_red_zone_drive", unavailable_route)
    result = redzone.build_matchup_red_zone_drive_context("BUF", "Buffalo Bills", "MIA", "Miami Dolphins", "2026-09-20")
    assert result["ready"] is False
```

- [ ] **Step 2: Run RED, modify acquisition only, then run GREEN**

Do not change existing Step-5/6 classifiers or Step-8-consumed field names.

- [ ] **Step 3: Run original Step 5/6 suites and commit**

```bash
pytest -q tests/test_nfl_game_totals_multisource_step3_7.py tests/test_nfl_game_totals_page_step5.py tests/test_nfl_game_totals_page_step6.py
git add sports_api/nfl_game_totals_explosive_context_v1.py sports_api/nfl_game_totals_red_zone_drive_context_v1.py tests/test_nfl_game_totals_multisource_step3_7.py
git commit -m "feat: route explosive and red-zone contexts through multisource data"
```

---

### Task 7: Migrate Step 7 environment with NWS primary and ESPN fallback

**Files:**
- Modify: `sports_api/nfl_game_totals_environment_context_v1.py`
- Test: extend `tests/test_nfl_game_totals_multisource_step3_7.py`

**Interfaces:**
- Preserve `classify_weather_pressure(temperature, precipitation, gust, *, indoor)` exactly.
- `build_slate_environment_context(day_str, event_ids)` keeps its public signature so V7/V8 callers do not change.
- Existing exact slate/event metadata is used to resolve home team, venue, and kickoff before provider routing.

- [ ] **Step 1: Write NWS-primary and ESPN-403 fallback-resilience tests**

```python
def test_step7_uses_nws_without_calling_espn_when_nws_is_valid(monkeypatch):
    result = environment.build_slate_environment_context("2026-09-20", ["event-1"])
    assert result["event-1"]["ready"] is True
    assert result["event-1"]["provider"] == "NWS"


def test_step7_espn_403_does_not_matter_when_nws_is_valid(monkeypatch):
    # ESPN fallback is wired to raise/return 403; NWS returns valid canonical weather.
    result = environment.build_slate_environment_context("2026-09-20", ["event-1"])
    assert result["event-1"]["ready"] is True
```

- [ ] **Step 2: Preserve indoor behavior exactly**

Indoor games must return `weather_applies=False` and pressure `INDOOR` without calling NWS or ESPN weather endpoints after venue/roof identity is certified.

- [ ] **Step 3: Run original Step-7 suite and commit**

```bash
pytest -q tests/test_nfl_game_totals_multisource_step3_7.py tests/test_nfl_game_totals_page_step7.py
git add sports_api/nfl_game_totals_environment_context_v1.py tests/test_nfl_game_totals_multisource_step3_7.py
git commit -m "feat: route Game Totals environment through NWS with fallback"
```

---

### Task 8: Preserve Step-8 firewall and integrate targeted reload/cache behavior

**Files:**
- Modify: `nfl_game_totals_hub_v8_1.py`
- Test: `tests/test_nfl_game_totals_multisource_step3_7.py`
- Test: existing `tests/test_nfl_game_totals_mobile_hotfix_v8_1.py`

**Interfaces:**
- `sports_api.nfl_game_totals_total_projection_v1.build_total_projection` signature must remain exactly five football-context parameters.
- `_clear_game_totals_caches()` adds `clear_router_caches` and must still avoid global `st.cache_data.clear()`.

- [ ] **Step 1: Write structural firewall test**

```python
def test_step8_projection_signature_is_unchanged_and_market_free():
    sig = inspect.signature(build_total_projection)
    assert list(sig.parameters) == [
        "scoring_context",
        "pace_context",
        "explosive_context",
        "red_zone_drive_context",
        "environment_context",
    ]
    assert not any(token in str(sig).lower() for token in ("market", "odds", "fanduel", "sportsbook"))
```

- [ ] **Step 2: Write V8.1 targeted-cache test**

Assert `clear_router_caches()` is invoked by `_clear_game_totals_caches()` and that no global Streamlit cache clear appears.

- [ ] **Step 3: Update V8.1 cache list only**

No hero, progress, projection, routing, date, market, or UI model changes.

- [ ] **Step 4: Run Step 8 + V8.1 suites and commit**

```bash
pytest -q tests/test_nfl_game_totals_page_step8.py tests/test_nfl_game_totals_mobile_hotfix_v8_1.py tests/test_nfl_game_totals_multisource_step3_7.py
git add nfl_game_totals_hub_v8_1.py tests/test_nfl_game_totals_multisource_step3_7.py
git commit -m "fix: connect Game Totals reload to multisource caches"
```

---

### Task 9: Add targeted CI, freeze guard, and production certification

**Files:**
- Create: `.github/workflows/nfl-game-totals-multisource-router.yml`
- No runtime file changes unless a test exposes a scoped defect.

**Interfaces:**
- Dedicated workflow must gate the exact approved implementation surface.

- [ ] **Step 1: Write workflow with targeted tests and compile checks**

Required test command:

```bash
pytest -q \
  tests/test_nfl_data_router_v1.py \
  tests/test_nfl_data_nflverse_v1.py \
  tests/test_nfl_data_nws_v1.py \
  tests/test_nfl_game_totals_multisource_step3_7.py \
  tests/test_nfl_game_totals_page_step3.py \
  tests/test_nfl_game_totals_page_step4.py \
  tests/test_nfl_game_totals_page_step5.py \
  tests/test_nfl_game_totals_page_step6.py \
  tests/test_nfl_game_totals_page_step7.py \
  tests/test_nfl_game_totals_page_step8.py \
  tests/test_nfl_game_totals_mobile_hotfix_v8_1.py
```

Compile command:

```bash
python -m py_compile \
  sports_api/nfl_data_router_v1.py \
  sports_api/nfl_data_nflverse_v1.py \
  sports_api/nfl_data_nws_v1.py \
  sports_api/nfl_data_espn_fallback_v1.py \
  sports_api/nfl_stadium_coordinates_v1.py \
  sports_api/nfl_game_totals_scoring_context_v1.py \
  sports_api/nfl_game_totals_pace_context_v1.py \
  sports_api/nfl_game_totals_explosive_context_v1.py \
  sports_api/nfl_game_totals_red_zone_drive_context_v1.py \
  sports_api/nfl_game_totals_environment_context_v1.py \
  nfl_game_totals_hub_v8_1.py
```

- [ ] **Step 2: Freeze guard exact implementation surface**

Allowed runtime/test/workflow files are exactly the files named in this plan. Explicitly fail if the diff contains:
- `sports_api/nfl_game_totals_total_projection_v1.py`
- `nfl_game_totals_hub_v8.py`
- NFL Spread/Moneyline/Passing/Rushing/Receiving files
- `nfl_hub_v18.py` unless the implementation stops and obtains separate approval for a proven compatibility need.

- [ ] **Step 3: Add one deterministic forced-fallback integration test**

The test must simulate primary nflverse/NWS transport failure and prove the routed context can succeed from the certified fallback. It must also simulate all providers failing and prove Step 8 remains unavailable rather than projecting fabricated data.

- [ ] **Step 4: Run full local/CI targeted suite GREEN**

```bash
pytest -q tests/test_nfl_data_router_v1.py tests/test_nfl_data_nflverse_v1.py tests/test_nfl_data_nws_v1.py tests/test_nfl_game_totals_multisource_step3_7.py
```

- [ ] **Step 5: Commit workflow**

```bash
git add .github/workflows/nfl-game-totals-multisource-router.yml
git commit -m "ci: certify NFL Game Totals multisource router"
```

- [ ] **Step 6: Open PR and run protected certification**

PR title:

```text
NFL Game Totals — Multi-Source Data Router
```

PR body must explicitly state:
- free/open providers only;
- ESPN is fallback, not backbone;
- Step-8 projection formula/signature untouched;
- FanDuel remains 0.0% projection influence;
- no Step-9 logic;
- one forced provider-failure fallback proof;
- one all-providers-fail closed proof.

Required gates before merge:
- dedicated multisource workflow GREEN;
- Regression Shield GREEN;
- Permanent Contract GREEN;
- real Streamlit Browser QA GREEN;
- NFL Critical GREEN;
- `devsystem-final-gate` GREEN.

- [ ] **Step 7: Verify exact diff before merge**

Use compare against the protected-main baseline. Any unexpected file is a stop condition.

- [ ] **Step 8: Merge only after final gate and verify new protected-main SHA**

After merge, fetch protected `main` and confirm required `devsystem-final-gate` protection remains active.

---

## Plan Self-Review

### Spec coverage

- Free/open-only policy: Tasks 2–4 and Global Constraints.
- Shared router and provider priority: Task 1.
- nflverse football data: Task 2.
- NWS weather: Task 3.
- ESPN fallback isolation: Task 4.
- Steps 3–7 migration: Tasks 5–7.
- Validation, provenance, quality, freshness, fallback diagnostics: Tasks 1–4.
- Cache reuse/invalidation: Tasks 1, 2, 3, 8.
- Cross-source conflict behavior: Task 1 validator and provider attempts; unresolved disagreement must fail closed rather than average.
- Step-8 projection firewall and sportsbook 0.0%: Task 8.
- Freeze protection, browser QA, NFL-critical, permanent final gate: Task 9.
- Rollback isolation: task boundaries keep provider adapters and each Step migration independently reviewable.

### Placeholder scan

No `TBD`, `TODO`, “implement later”, generic “add error handling”, or unnamed tests remain. Every task names its files, interfaces, test behavior, commands, and commit boundary.

### Type/interface consistency

All provider functions accept one request mapping and return normalized provider mappings. `route_metric` wraps those into the canonical routed result. Steps 3–7 consume routed `data` while preserving their existing public context output. Step 8 remains a consumer of the same five context objects and is not passed router/provider/market objects.

## Execution Rule

Do not implement multiple migration tasks in one unreviewed jump. Every task must complete RED → GREEN → targeted regression → commit before moving forward. If a provider's real schema differs from its certified documentation, stop that task, record the exact mismatch, and adjust the adapter/test contract without weakening the canonical metric definition.
