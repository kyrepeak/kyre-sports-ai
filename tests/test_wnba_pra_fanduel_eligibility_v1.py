from __future__ import annotations

import pandas as pd

from wnba_pra_playoff_context_v1 import PlayoffContext
from wnba_pra_product_snapshot_v1 import PRAProductSnapshot


def snapshot(*, projections=None, market=None, stored=None, final=None):
    return PRAProductSnapshot(
        day="2026-10-19",
        schedule=pd.DataFrame(),
        schedule_diag={},
        projections=pd.DataFrame(projections or []),
        market_rows=pd.DataFrame(market or []),
        market_meta={},
        matchup_rows=pd.DataFrame(),
        matchup_meta={},
        stored_mc_rows=pd.DataFrame(stored or []),
        stored_mc_meta={},
        final_card=pd.DataFrame(final or []),
        availability_diag={},
        role_diag={},
    )


def context():
    return PlayoffContext(
        "2026-10-19", "2026-10-19", True, pd.DataFrame(), None,
        "WNBA Finals • Game 2", "Series context", "VERIFIED_MULTI_SOURCE",
        ("WNBA", "ESPN"), "",
    )


def projection(*, game_id="g1", player_key="allisha gray", name="Allisha Gray", designation="ACTIVE"):
    return {
        "game_id": game_id,
        "player_key": player_key,
        "PLAYER_NAME": name,
        "TEAM_NAME": "Atlanta Dream",
        "OPPONENT": "Golden State Valkyries",
        "PROJ_MIN": 35.0,
        "PROJ_PTS": 20.0,
        "PROJ_REB": 6.0,
        "PROJ_AST": 5.0,
        "PROJ_PRA": 31.0,
        "DESIGNATION": designation,
        "ROLE_LABEL": "STARTER",
    }


def market(*, game_id="g1", player="Allisha Gray", book="FanDuel", line=31.5, freshness="FRESH", over=-108, under=-112):
    return {
        "game_id": game_id,
        "player": player,
        "book": book,
        "line": line,
        "over_odds": over,
        "under_odds": under,
        "freshness": freshness,
        "over_updated": "2026-10-18T18:58:00+00:00",
        "under_updated": "2026-10-18T18:58:00+00:00",
        "source_event_id": "fd-event-1" if book == "FanDuel" else "other-event-1",
    }


def consensus(*, line=32.5, books=("FanDuel", "DraftKings")):
    return pd.DataFrame([{
        "player_key": "allisha gray",
        "player": "Allisha Gray",
        "book_count": len(books),
        "books": books,
        "consensus_line": line,
        "min_line": 31.5,
        "max_line": 32.5,
        "best_over_odds": 100,
        "evidence_state": "VERIFIED_MULTI_SOURCE",
        "current_quote_count": len(books),
    }])


def stored_row():
    return {
        "game_id": "g1", "player_key": "allisha gray",
        "model_over": 0.61, "model_under": 0.39, "edge": 0.06,
        "decision_label": "OVER", "decision_strength": 82.0,
    }


def final_row():
    return {
        "game_id": "g1", "player_key": "allisha gray",
        "decision_label": "OVER", "decision_strength": 82.0,
    }


def test_current_fanduel_offer_uses_exact_game_player_and_fanduel_line():
    from wnba_pra_fanduel_eligibility_v1 import current_fanduel_pra_offers

    rows = pd.DataFrame([
        market(game_id="g1", line=31.5),
        market(game_id="g1", book="DraftKings", line=32.5),
        market(game_id="g2", player="Allisha Gray", line=29.5),
    ])
    offers = current_fanduel_pra_offers(rows)

    assert set(offers) == {("g1", "allisha gray"), ("g2", "allisha gray")}
    offer = offers[("g1", "allisha gray")]
    assert offer.line == 31.5
    assert offer.over_odds == -108
    assert offer.under_odds == -112
    assert offer.source_event_id == "fd-event-1"
    assert offer.evidence_state == "FANDUEL_CURRENT"


def test_model_projection_without_fanduel_pra_is_excluded_from_v2_board():
    from wnba_pra_product_view_model_v1 import build_player_views

    snap = snapshot(
        projections=[projection()],
        market=[market(book="DraftKings", line=32.5)],
        stored=[stored_row()],
    )
    views = build_player_views(snap, context(), consensus(books=("DraftKings",)), require_fanduel=True)

    assert views == ()


def test_exact_fanduel_player_game_is_included_and_fanduel_line_wins_over_consensus():
    from wnba_pra_product_view_model_v1 import build_player_views

    snap = snapshot(
        projections=[projection()],
        market=[market(line=31.5), market(book="DraftKings", line=32.5)],
        stored=[stored_row()],
    )
    views = build_player_views(snap, context(), consensus(line=32.5), require_fanduel=True)

    assert len(views) == 1
    view = views[0]
    assert view.fanduel_eligible is True
    assert view.fanduel_line == 31.5
    assert view.market_line == 31.5
    assert view.fanduel_over_odds == -108
    assert view.fanduel_under_odds == -112
    assert view.book_count == 2
    assert view.evidence_state == "VERIFIED_MULTI_SOURCE"
    assert view.market_freshness == "CURRENT"


def test_same_player_name_in_different_game_does_not_create_eligibility():
    from wnba_pra_product_view_model_v1 import build_player_views

    snap = snapshot(
        projections=[projection(game_id="g1")],
        market=[market(game_id="g2")],
        stored=[stored_row()],
    )
    views = build_player_views(snap, context(), consensus(), require_fanduel=True)

    assert views == ()


def test_unresolved_availability_keeps_research_view_but_blocks_final_card():
    from wnba_pra_product_view_model_v1 import build_player_views

    snap = snapshot(
        projections=[projection(designation="QUESTIONABLE")],
        market=[market()],
        stored=[stored_row()],
        final=[final_row()],
    )
    views = build_player_views(snap, context(), consensus(books=("FanDuel",)), require_fanduel=True)

    assert len(views) == 1
    assert views[0].availability_label == "UNRESOLVED"
    assert views[0].final_card_selected is False


def test_refresh_without_player_removes_fanduel_eligibility():
    from wnba_pra_fanduel_eligibility_v1 import current_fanduel_pra_offers

    first = current_fanduel_pra_offers(pd.DataFrame([market()]))
    refreshed = current_fanduel_pra_offers(pd.DataFrame([market(player="Rhyne Howard")]))

    assert ("g1", "allisha gray") in first
    assert ("g1", "allisha gray") not in refreshed
