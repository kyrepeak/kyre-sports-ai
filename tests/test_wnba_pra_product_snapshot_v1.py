from __future__ import annotations

import pandas as pd


def test_build_product_snapshot_delegates_without_mutating(monkeypatch):
    import wnba_pra_product_snapshot_v1 as product

    schedule = pd.DataFrame([{"game_id": "g1"}])
    projections = pd.DataFrame([{"game_id": "g1", "player_key": "p1", "PROJ_PRA": 31.5}])
    market_rows = pd.DataFrame([{"game_id": "g1", "player_key": "p1", "line": 29.5}])
    matchup_rows = pd.DataFrame([{"game_id": "g1", "player_key": "p1", "PROJ_PRA": 32.0}])
    stored_rows = pd.DataFrame([{"game_id": "g1", "player_key": "p1", "model_over": .62}])
    final_rows = pd.DataFrame([{"game_id": "g1", "player_key": "p1", "decision_label": "STRONG"}])
    calls = []

    monkeypatch.setattr(product.market, "_projection_frame", lambda day: (projections, schedule))
    monkeypatch.setattr(product.market, "grade_pra_markets", lambda day: (market_rows, {"market": "ok"}))
    monkeypatch.setattr(product.matchup, "grade_matchup_pra", lambda day: (matchup_rows, {"matchup": "ok"}))
    monkeypatch.setattr(product.final, "_stored_rows", lambda day: (stored_rows, {"source": "5M"}))
    def select(rows, limit):
        calls.append((rows.copy(), limit))
        return final_rows
    monkeypatch.setattr(product.final, "select_master_card", select)
    monkeypatch.setattr(product.schedule, "schedule_diagnostics", lambda day: {"state": "VERIFIED"})
    monkeypatch.setattr(product.v27.availability, "availability_diagnostics", lambda day: {"state": "VERIFIED"})
    monkeypatch.setattr(product.role, "role_diagnostics", lambda day: {"state": "VERIFIED"})

    snap = product.build_product_snapshot("2026-10-19")

    assert snap.day == "2026-10-19"
    pd.testing.assert_frame_equal(snap.schedule, schedule)
    pd.testing.assert_frame_equal(snap.projections, projections)
    pd.testing.assert_frame_equal(snap.market_rows, market_rows)
    pd.testing.assert_frame_equal(snap.matchup_rows, matchup_rows)
    pd.testing.assert_frame_equal(snap.stored_mc_rows, stored_rows)
    pd.testing.assert_frame_equal(snap.final_card, final_rows)
    assert snap.market_meta == {"market": "ok"}
    assert snap.matchup_meta == {"matchup": "ok"}
    assert snap.stored_mc_meta == {"source": "5M"}
    assert snap.availability_diag["state"] == "VERIFIED"
    assert snap.role_diag["state"] == "VERIFIED"
    assert len(calls) == 1
    pd.testing.assert_frame_equal(calls[0][0], stored_rows)
    assert calls[0][1] == product.final.MAX_CARD
    # returned frames are defensive copies: downstream view code cannot mutate engine frames.
    assert snap.projections is not projections
    assert snap.market_rows is not market_rows


def test_build_product_snapshot_normalizes_none_to_safe_empty(monkeypatch):
    import wnba_pra_product_snapshot_v1 as product

    monkeypatch.setattr(product.market, "_projection_frame", lambda day: (None, None))
    monkeypatch.setattr(product.market, "grade_pra_markets", lambda day: (None, None))
    monkeypatch.setattr(product.matchup, "grade_matchup_pra", lambda day: (None, None))
    monkeypatch.setattr(product.final, "_stored_rows", lambda day: (None, None))
    monkeypatch.setattr(product.final, "select_master_card", lambda rows, limit: None)
    monkeypatch.setattr(product.schedule, "schedule_diagnostics", lambda day: None)
    monkeypatch.setattr(product.v27.availability, "availability_diagnostics", lambda day: None)
    monkeypatch.setattr(product.role, "role_diagnostics", lambda day: None)

    snap = product.build_product_snapshot("2026-10-18")
    assert snap.schedule.empty and snap.projections.empty and snap.market_rows.empty
    assert snap.matchup_rows.empty and snap.stored_mc_rows.empty and snap.final_card.empty
    assert snap.schedule_diag == {} and snap.market_meta == {} and snap.matchup_meta == {}
