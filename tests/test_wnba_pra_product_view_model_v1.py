from __future__ import annotations
import pandas as pd
from wnba_pra_product_snapshot_v1 import PRAProductSnapshot
from wnba_pra_playoff_context_v1 import PlayoffContext


def snap(*, projections=None, matchup=None, market=None, stored=None, final=None):
    return PRAProductSnapshot(
        day="2026-10-19", schedule=pd.DataFrame(), schedule_diag={},
        projections=pd.DataFrame(projections or []), market_rows=pd.DataFrame(market or []), market_meta={},
        matchup_rows=pd.DataFrame(matchup or []), matchup_meta={}, stored_mc_rows=pd.DataFrame(stored or []), stored_mc_meta={},
        final_card=pd.DataFrame(final or []), availability_diag={}, role_diag={},
    )


def context():
    return PlayoffContext("2026-10-19", "2026-10-19", True, pd.DataFrame(), None, "WNBA Finals • Game 2", "GSV leads 1-0", "VERIFIED_MULTI_SOURCE", ("WNBA", "ESPN"), "")


def base_projection(**updates):
    row = {
        "game_id":"g1", "player_key":"p1", "PLAYER_NAME":"A Player", "TEAM_NAME":"Atlanta Dream", "OPPONENT":"Golden State Valkyries",
        "PROJ_MIN":34.0, "PROJ_PTS":20.0, "PROJ_REB":7.0, "PROJ_AST":5.0, "PROJ_PRA":32.0,
        "DESIGNATION":"ACTIVE", "ROLE_LABEL":"STARTER", "HEADSHOT_URL":"https://img/p1.png", "TEAM_LOGO_URL":"https://img/team.png",
    }
    row.update(updates)
    return row


def test_projection_without_market_still_creates_player_card():
    from wnba_pra_product_view_model_v1 import build_player_views
    views = build_player_views(snap(projections=[base_projection()]), context(), pd.DataFrame())
    assert len(views) == 1
    v = views[0]
    assert v.player == "A Player" and v.proj_pra == 32.0
    assert v.market_line is None and v.book_count == 0
    assert v.final_card_selected is False


def test_matchup_adjusted_preserved_values_are_preferred_without_recalculation():
    from wnba_pra_product_view_model_v1 import build_player_views
    raw = base_projection(PROJ_PTS=20.0, PROJ_REB=7.0, PROJ_AST=5.0, PROJ_PRA=32.0)
    adj = base_projection(PROJ_PTS=19.4, PROJ_REB=7.6, PROJ_AST=5.3, PROJ_PRA=32.7)
    v = build_player_views(snap(projections=[raw], matchup=[adj]), context(), pd.DataFrame())[0]
    assert (v.proj_pts, v.proj_reb, v.proj_ast, v.proj_pra) == (19.4, 7.6, 5.3, 32.7)
    assert v.proj_pra != v.proj_pts + v.proj_reb + v.proj_ast  # preserved value, not recomputed


def test_mc_decision_fields_and_final_membership_come_from_preserved_rows_only():
    from wnba_pra_product_view_model_v1 import build_player_views
    stored = [{"game_id":"g1", "player_key":"p1", "model_over":.64, "edge":.075, "role_label":"ACTIVE"}]
    final = [{"game_id":"g1", "player_key":"p1", "decision_label":"🔥 BEST BET", "decision_strength":84.2}]
    consensus = pd.DataFrame([{"player_key":"p1", "player":"A Player", "book_count":3, "consensus_line":29.5, "evidence_state":"VERIFIED_MULTI_SOURCE"}])
    v = build_player_views(snap(projections=[base_projection()], stored=stored, final=final), context(), consensus)[0]
    assert v.over_probability == .64 and v.under_probability == .36
    assert v.edge == .075 and v.decision_label == "🔥 BEST BET" and v.decision_strength == 84.2
    assert v.final_card_selected is True


def test_unresolved_availability_keeps_projection_but_marks_unresolved():
    from wnba_pra_product_view_model_v1 import build_player_views
    v = build_player_views(snap(projections=[base_projection(DESIGNATION="QUESTIONABLE")]), context(), pd.DataFrame())[0]
    assert v.proj_pra == 32.0
    assert v.availability_label == "UNRESOLVED"
    assert v.evidence_state == "UNRESOLVED"


def test_out_player_cannot_be_final_selected_from_stale_final_data():
    from wnba_pra_product_view_model_v1 import build_player_views
    final = [{"game_id":"g1", "player_key":"p1", "decision_label":"🔥 BEST BET"}]
    v = build_player_views(snap(projections=[base_projection(DESIGNATION="OUT")], final=final), context(), pd.DataFrame())[0]
    assert v.availability_label == "OUT / INACTIVE"
    assert v.final_card_selected is False
