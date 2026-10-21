from __future__ import annotations

from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "nba_pra_runtime_v2.py"
SYNC = ROOT / "nba_pra_page2_sync_v1.py"


def _nba_stats_payload(rows: list[list[object]]) -> dict:
    return {
        "resultSets": [
            {
                "name": "LeagueDashPlayerStats",
                "headers": ["PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION", "GP", "MIN", "USG_PCT"],
                "rowSet": rows,
            }
        ]
    }


def test_basketball_reference_game_log_preserves_verified_opponent() -> None:
    import runless_v2.nba_pra_player_context_v1 as ctx

    html = """
    <table><tbody><tr>
      <th data-stat="date_game">2026-02-28</th>
      <td data-stat="opp_id"><a href="/teams/CHA/2026.html">CHA</a></td>
      <td data-stat="mp">21:00</td><td data-stat="pts">5</td>
      <td data-stat="trb">2</td><td data-stat="ast">4</td>
    </tr></tbody></table>
    """
    rows = ctx._parse_game_log(html)
    assert rows[0]["opponent"] == "CHA"


def test_cbs_game_log_preserves_verified_opponent() -> None:
    import runless_v2.nba_pra_player_context_v1 as ctx

    headers = ["date", "opponent", "result", "fpts", "min", "pts", "reb", "ast", "stl"]
    head = "".join(f"<th>{h}</th>" for h in headers)
    values = ["Apr 12, 2026", "vs ATL", "W", "11", "26", "4", "2", "2", "1"]
    body = "".join(f"<td>{v}</td>" for v in values)
    html = f'<h4>2025-26 Regular Season Game Log</h4><table><thead><tr>{head}</tr></thead><tbody><tr>{body}</tr></tbody></table>'
    rows = ctx._parse_cbs_game_log_html(html)
    assert rows[0]["opponent"] == "ATL"


def test_usage_fills_rookie_from_current_preseason_before_prior_regular_season() -> None:
    from runless_v2.nba_pra_usage_v1 import load_nba_usage_context

    calls: list[tuple[str, str]] = []

    class Response:
        def __init__(self, payload: dict):
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    regular = _nba_stats_payload([[1, "Veteran", "BKN", 1, 20.0, 0.18]])
    preseason = _nba_stats_payload(
        [
            [10, "Mikel Brown Jr.", "BKN", 4, 29.0, 0.244],
            [11, "Teammate One", "BKN", 4, 31.0, 0.281],
            [12, "Teammate Two", "BKN", 4, 24.0, 0.201],
        ]
    )

    def fake_get(url: str, *, params: dict, headers: dict, timeout: float):
        del url, headers, timeout
        key = (str(params.get("Season")), str(params.get("SeasonType")))
        calls.append(key)
        if key == ("2026-27", "Regular Season"):
            return Response(regular)
        if key == ("2026-27", "Pre Season"):
            return Response(preseason)
        raise AssertionError(f"unexpected provider call: {key}")

    out = load_nba_usage_context(date(2026, 10, 21), ["Mikel Brown Jr."], request_get=fake_get)
    row = out["profiles"]["mikelbrownjr"]
    assert row["usage_pct"] == 24.4
    assert row["usage_rank"] == 2
    assert row["usage_team_size"] == 3
    assert row["usage_period"] == "2026-27 PRE SEASON"
    assert row["usage_source"] == "NBA Stats"
    assert calls == [("2026-27", "Regular Season"), ("2026-27", "Pre Season")]


def test_handoff_adds_same_kyre_score_page1_visually_displays() -> None:
    from nba_pra_page1_model_v1 import grade_market
    from nba_pra_runtime_v2 import SESSION_ANALYSIS_HANDOFF, select_player_for_analysis

    model = {"projection": 27.0, "sigma": 6.0}
    quote = {"sportsbook": "FanDuel", "line": 11.5, "over_price": -118, "under_price": -108}
    item = {
        "key": "mikelbrownjr",
        "player_name": "Mikel Brown Jr.",
        "team": "BKN",
        "position": "PG",
        "availability": "No verified injury flag",
        "featured_quote": quote,
        "model": model,
        "grade": grade_market(model["projection"], quote["line"], model["sigma"]),
    }
    state: dict = {}
    select_player_for_analysis(state, item)
    handed = state[SESSION_ANALYSIS_HANDOFF]
    assert handed["grade"]["score"] == 10.0
    assert handed["grade"]["tier"] == "ELITE"
    assert handed["availability"] == "No verified injury flag"


def test_page2_reuses_verified_handoff_availability_when_refresh_is_unverified() -> None:
    from nba_pra_page2_sync_v1 import apply_handoff_context

    context = {"availability": "UNVERIFIED"}
    handoff = {"player_key": "mikelbrownjr", "availability": "No verified injury flag"}
    out = apply_handoff_context(context, handoff, "mikelbrownjr")
    assert out["availability"] == "No verified injury flag"


def test_loading_overlay_covers_actual_page2_fetch_instead_of_flashing_before_it() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    sync = SYNC.read_text(encoding="utf-8")

    assert "sleep(" not in runtime
    loading_block = runtime.split('if nav_phase == "loading_page2"', 1)[1].split("player_key =", 1)[0]
    assert "render_nba_pra_page2_sync_v1(show_loading_overlay=True)" in loading_block
    assert "st.rerun()" not in loading_block

    assert "show_loading_overlay: bool = False" in sync
    assert "render_page2_loading_screen" in sync
    assert "loading_placeholder = st.empty()" in sync
    assert sync.index("loading_placeholder = st.empty()") < sync.index("load_page2_snapshot_v1(")
    assert sync.index("load_kyre_sports_api_nba_pra_matchup(") < sync.index("loading_placeholder.empty()")


def test_repair_active_path_keeps_prohibited_sources_out() -> None:
    paths = [
        ROOT / "nba_pra_runtime_v2.py",
        ROOT / "nba_pra_page2_sync_v1.py",
        ROOT / "nba_pra_page2_v1.py",
        ROOT / "nba_pra_page2_context_v1.py",
        ROOT / "runless_v2" / "nba_pra_player_context_enrichment_v2.py",
        ROOT / "runless_v2" / "nba_pra_usage_v1.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8").casefold() for path in paths)
    assert "sportsgameodds" not in combined
    assert "espn bet" not in combined
    assert "espn" not in combined
