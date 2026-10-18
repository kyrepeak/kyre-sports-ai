from __future__ import annotations
from pathlib import Path
import pandas as pd

from wnba_pra_product_snapshot_v1 import PRAProductSnapshot
from wnba_pra_playoff_context_v1 import PlayoffContext

ROOT=Path(__file__).resolve().parents[1]


def _projection():
    return pd.DataFrame([{
        "game_id":"g1","player_key":"p1","PLAYER_NAME":"A Player","TEAM_NAME":"Atlanta Dream","OPPONENT":"Golden State Valkyries",
        "PROJ_MIN":34.0,"PROJ_PTS":20.0,"PROJ_REB":7.0,"PROJ_AST":5.0,"PROJ_PRA":32.0,"DESIGNATION":"ACTIVE","ROLE_LABEL":"STARTER",
    }])


def _stored_mc():
    return pd.DataFrame([{
        "game_id":"g1","player_key":"p1","player":"A Player","team":"Atlanta Dream","opponent":"Golden State Valkyries",
        "line":29.5,"book":"Book A","over_odds":-105,"model_over":.64,"no_vig_over":.52,"edge":.12,
        "freshness":"FRESH","fresh_score":1.0,"converged":True,"role_label":"ACTIVE","data_quality":.95,"context_quality":.9,
        "model_qualified":True,"lineup_ready":True,"variance_source":"EMPIRICAL","final_ready":True,"projection":32.0,
    }])


def _context():
    return PlayoffContext("2026-10-19","2026-10-19",True,pd.DataFrame(),None,"WNBA Finals • Game 2","GSV leads 1-0","VERIFIED_MULTI_SOURCE",("WNBA","ESPN"),"")


def test_final_card_decision_fields_match_preserved_selector_output():
    import wnba_pra_final_v32 as final
    from wnba_pra_product_view_model_v1 import build_player_views
    from wnba_pra_market_consensus_v1 import build_market_consensus
    stored=_stored_mc()
    selected=final.select_master_card(stored,limit=final.MAX_CARD)
    assert len(selected)==1
    snap=PRAProductSnapshot("2026-10-19",pd.DataFrame(),{},_projection(),stored.copy(),{},pd.DataFrame(),{},stored.copy(),{"source":"5M"},selected.copy(),{}, {})
    consensus=build_market_consensus(stored)
    view=build_player_views(snap,_context(),consensus)[0]
    assert view.final_card_selected is True
    assert view.decision_label == selected.iloc[0]["decision_label"]
    assert view.decision_strength == selected.iloc[0]["decision_strength"]
    assert view.over_probability == selected.iloc[0]["model_over"]
    assert view.proj_pra == 32.0


def test_presentation_successor_does_not_replace_projection_market_or_matchup_functions():
    source=(ROOT/"wnba_pra_hub_v3615.py").read_text(encoding="utf-8")
    assert "grade_pra_markets =" not in source
    assert "grade_matchup_pra =" not in source
    assert "select_master_card =" not in source
    assert "previous.render_wnba_pra_hub" not in source


def test_wnba_pra_remains_on_existing_universal_runtime_route():
    from universal_runtime_v5_loader import resolve_destination
    from universal_runtime_v5_state import RuntimeRoute
    adapter=resolve_destination(RuntimeRoute("wnba","pra",{}))
    assert adapter.route_key == ("wnba","pra")
    assert adapter.source_version == "streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard"
    loader=(ROOT/"universal_runtime_v5_loader.py").read_text(encoding="utf-8")
    assert "wnba_pra_hub_v3615" not in loader


def test_product_view_has_no_route_escape_or_raw_pipeline_controls():
    source=(ROOT/"wnba_pra_product_view_v1.py").read_text(encoding="utf-8")
    assert "query_params" not in source
    assert "ks_sport" not in source and "ks_wnba_market" not in source
    for banned in ("RUN PRA 5,000,000 STANDARD SIMS","PRA production HOLD","Monte Carlo restore DISABLED"):
        assert banned not in source
