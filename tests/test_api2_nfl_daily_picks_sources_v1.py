from datetime import date, datetime, timedelta, timezone

import nfl_daily_picks_sources_v1 as sources

NOW = datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc)
DAY = date(2026, 10, 18)


def row(market_id="passing-yards", **changes):
    base = {
        "game_id": "401772345",
        "game_date": DAY,
        "kickoff_at": NOW + timedelta(hours=3),
        "team_id": "HOU",
        "opponent_team_id": "JAX",
        "athlete_id": "4431611" if market_id in {"passing-yards", "rushing-yards", "receiving-yards"} else None,
        "subject_label": "C.J. Stroud" if market_id == "passing-yards" else "Houston Texans",
        "matchup_label": "HOU at JAX",
        "side": "OVER" if market_id in {"passing-yards", "rushing-yards", "receiving-yards", "game-total"} else "AWAY",
        "market_line": 247.5 if market_id != "moneyline" else None,
        "model_projection": 263.2,
        "model_probability": 0.61,
        "edge_value": 7.8,
        "source_ready": True,
        "source_fresh_at": NOW - timedelta(seconds=20),
        "source_age_seconds": 20.0,
        "data_quality": 0.93,
        "uncertainty": 0.18,
        "reason_components": ("source-owned final read",),
        "source_grade": "A",
        "source_state": "READY",
        "freshness_limit_seconds": 120.0,
        "actionable": True,
        "fanduel_line_ready": True,
    }
    base.update(changes)
    return base


def envelope(market_id, *rows, status="READY", version=None, diagnostic=""):
    return {
        "status": status,
        "source_version": version or f"{market_id}-source-v1",
        "fresh_at": NOW,
        "diagnostic": diagnostic,
        "rows": list(rows),
    }


def install(monkeypatch, market_id, payload):
    monkeypatch.setitem(sources._SOURCE_PROVIDERS, market_id, lambda day, now_utc: payload)


def test_each_adapter_preserves_market_and_source_version(monkeypatch):
    cases = [
        ("moneyline", sources.load_moneyline_candidates),
        ("spread", sources.load_spread_candidates),
        ("game-total", sources.load_game_total_candidates),
        ("passing-yards", sources.load_passing_yards_candidates),
        ("rushing-yards", sources.load_rushing_yards_candidates),
        ("receiving-yards", sources.load_receiving_yards_candidates),
    ]
    for market_id, loader in cases:
        install(monkeypatch, market_id, envelope(market_id, row(market_id), version=f"{market_id}-cert"))
        result = loader(DAY, now_utc=NOW)
        assert result.market_id == market_id
        assert result.source_version == f"{market_id}-cert"


def test_source_values_are_copied_unchanged(monkeypatch):
    source = row("passing-yards", model_probability=0.638, model_projection=271.25, market_line=252.5, edge_value=6.4, source_grade="B")
    install(monkeypatch, "passing-yards", envelope("passing-yards", source, version="nfl_passing_yards_market_v1"))
    result = sources.load_passing_yards_candidates(DAY, now_utc=NOW)
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.model_probability == 0.638
    assert candidate.model_projection == 271.25
    assert candidate.market_line == 252.5
    assert candidate.edge_value == 6.4
    assert candidate.source_grade == "B"


def test_actionable_source_row_becomes_candidate(monkeypatch):
    install(monkeypatch, "moneyline", envelope("moneyline", row("moneyline", source_grade="QUALIFIED", model_probability=0.59, market_line=None)))
    result = sources.load_moneyline_candidates(DAY, now_utc=NOW)
    assert result.status == "READY"
    assert len(result.candidates) == 1


def test_gated_no_play_projection_only_missing_market_and_stale_rows_fail_closed(monkeypatch):
    blocked = [
        row("passing-yards", source_state="GATED"),
        row("passing-yards", source_state="NO PLAY"),
        row("passing-yards", actionable=False, source_grade="PROJECTION ONLY"),
        row("passing-yards", market_line=None),
        row("passing-yards", source_age_seconds=121.0, freshness_limit_seconds=120.0),
    ]
    install(monkeypatch, "passing-yards", envelope("passing-yards", *blocked))
    result = sources.load_passing_yards_candidates(DAY, now_utc=NOW)
    assert result.candidates == ()


def test_rushing_requires_current_fanduel_line(monkeypatch):
    install(monkeypatch, "rushing-yards", envelope(
        "rushing-yards",
        row("rushing-yards", athlete_id="1", subject_label="Runner A", fanduel_line_ready=False),
        row("rushing-yards", athlete_id="2", subject_label="Runner B", fanduel_line_ready=True),
    ))
    result = sources.load_rushing_yards_candidates(DAY, now_utc=NOW)
    assert [candidate.athlete_id for candidate in result.candidates] == ["2"]


def test_player_adapters_require_exact_athlete_ids(monkeypatch):
    install(monkeypatch, "receiving-yards", envelope("receiving-yards", row("receiving-yards", athlete_id=None)))
    result = sources.load_receiving_yards_candidates(DAY, now_utc=NOW)
    assert result.candidates == ()


def test_game_total_cannot_manufacture_pick_from_projection_minus_line(monkeypatch):
    projection_only = row(
        "game-total",
        athlete_id=None,
        subject_label="HOU at JAX total",
        side="OVER",
        model_probability=None,
        model_projection=47.8,
        market_line=44.5,
        edge_value=3.3,
        actionable=False,
        source_grade="FINAL READ WITHOUT PROBABILITY",
    )
    install(monkeypatch, "game-total", envelope("game-total", projection_only, status="GATED"))
    result = sources.load_game_total_candidates(DAY, now_utc=NOW)
    assert result.status == "GATED"
    assert result.candidates == ()


def test_one_provider_exception_does_not_break_other_markets(monkeypatch):
    for market_id in sources.MARKET_ORDER:
        install(monkeypatch, market_id, envelope(market_id, row(market_id)))
    monkeypatch.setitem(sources._SOURCE_PROVIDERS, "game-total", lambda day, now_utc: (_ for _ in ()).throw(RuntimeError("boom")))

    results = sources.load_all_market_candidates(DAY, now_utc=NOW)
    assert len(results) == 6
    by_market = {result.market_id: result for result in results}
    assert by_market["game-total"].status == "ERROR"
    assert by_market["game-total"].candidates == ()
    assert all(by_market[m].status == "READY" for m in sources.MARKET_ORDER if m != "game-total")


def _install_moneyline_runtime(monkeypatch, *, quote_age_seconds=10.0, selected_day=DAY):
    import sys
    from types import SimpleNamespace

    quote_at = NOW - timedelta(seconds=quote_age_seconds)
    fake_state = {
        "nfl_v1_date": selected_day,
        "nfl_moneyline_v8_final_outputs": {
            "G1": {
                "state": "QUALIFIED",
                "leader_side": "away",
                "leader_grade": {"grade": "QUALIFIED", "reason": "full thresholds"},
                "prerequisites": {"eligible": True, "reasons": ["calibration MEDIUM+", "market MEDIUM+"]},
            }
        },
        "nfl_moneyline_v7_edge_outputs": {
            "G1": {
                "ready": True,
                "market_quality": "HIGH",
                "away": {
                    "ready": True,
                    "model_p": 0.62,
                    "conservative_p": 0.58,
                    "edge": 0.07,
                    "conservative_edge": 0.03,
                },
            }
        },
        "nfl_moneyline_v5_market_snapshots": {
            "G1": {
                "ready": True,
                "rows": [
                    {
                        "usable": True,
                        "updated_at": quote_at.isoformat().replace("+00:00", "Z"),
                        "age_seconds": quote_age_seconds,
                    }
                ],
            }
        },
    }

    class Series:
        def to_dict(self):
            return {
                "game_id": "G1",
                "state": "pre",
                "kickoff_at": NOW + timedelta(hours=3),
                "away_abbr": "HOU",
                "home_abbr": "JAX",
                "away_team": "Houston Texans",
                "home_team": "Jacksonville Jaguars",
            }

    class Games:
        def iterrows(self):
            yield 0, Series()

    fake_streamlit = SimpleNamespace(session_state=fake_state)
    fake_nfl = SimpleNamespace(load_nfl_slate=lambda day: (Games(), {"request_ok": True}))
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    monkeypatch.setitem(sys.modules, "nfl_hub_v1", fake_nfl)
    return fake_state


def test_moneyline_provider_reads_active_v9_v8_state_without_v12_hot_key(monkeypatch):
    _install_moneyline_runtime(monkeypatch, quote_age_seconds=10.0)

    payload = sources._moneyline_provider(DAY, NOW)

    assert payload["status"] == "READY"
    assert len(payload["rows"]) == 1
    normalized = payload["rows"][0]
    assert normalized["source_grade"] == "QUALIFIED"
    assert normalized["reason_components"] == ("calibration MEDIUM+", "market MEDIUM+")
    assert normalized["source_age_seconds"] == 10.0
    assert normalized["freshness_limit_seconds"] == 180.0


def test_moneyline_provider_fails_closed_when_active_v9_market_snapshot_aged_out(monkeypatch):
    _install_moneyline_runtime(monkeypatch, quote_age_seconds=181.0)

    payload = sources._moneyline_provider(DAY, NOW)

    assert payload["status"] == "STALE"
    assert payload["rows"] == []


def test_moneyline_provider_rejects_state_from_another_selected_date(monkeypatch):
    _install_moneyline_runtime(monkeypatch, quote_age_seconds=10.0, selected_day=date(2026, 10, 19))

    payload = sources._moneyline_provider(DAY, NOW)

    assert payload["status"] == "GATED"
    assert payload["rows"] == []
