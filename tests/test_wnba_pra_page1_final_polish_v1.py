from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _row(**overrides):
    row={"player_name":"Kaitlyn Chen","sportsbook":"DraftKings","line":6.5,"team":"Golden State Valkyries","opponent":"Atlanta Dream","model_state":"LINE_BOUND_READY","p_over":.7182342,"p_under":.2817658,"model_probability":.7182342,"edge":.219225398,"model_edge":.219225398,"projection_pra":8.5445,"over_odds":-116,"under_odds":-117,"lean":"OVER"}
    row.update(overrides); return row


def test_model_artifact_successor_emits_images_only_from_verified_numeric_ids():
    import wnba_pra_page_model_artifact_final_polish_v1 as artifact
    source={"player":"Kaitlyn Chen","player_key":"kaitlyn chen","line":6.5,"model_over":.71,"model_under":.29,"team":"Golden State Valkyries","opponent":"Atlanta Dream"}
    out=artifact._model_row(source,{"kaitlyn chen":{"PLAYER_ID":1642289,"TEAM_ID":1611661326,"PROJ_PRA":8.5,"PROJ_MIN":12.0}})
    assert out["player_id"]==1642289 and out["team_id"]==1611661326
    assert out["headshot_url"]=="https://cdn.wnba.com/headshots/wnba/latest/1040x760/1642289.png"
    assert out["team_logo_url"]=="https://cdn.nba.com/logos/wnba/1611661326/global/L/logo.svg"
    missing=artifact._model_row(source,{"kaitlyn chen":{"PROJ_PRA":8.5}})
    assert missing["headshot_url"]=="" and missing["team_logo_url"]==""


def test_runless_runtime_preserves_frozen_snapshot_and_adds_verified_identity_only():
    import runless_v2.wnba_pra_page1_final_polish_runtime_v1 as runtime
    fields=runtime._safe_model_fields({"p_over":.71,"projection_pra":8.5,"player_id":1642289,"team_id":1611661326,"headshot_url":"https://evil.invalid/x","team_logo_url":"https://evil.invalid/y","untrusted_extra":"drop"})
    assert fields["player_id"]==1642289 and fields["team_id"]==1611661326
    assert fields["headshot_url"]=="https://cdn.wnba.com/headshots/wnba/latest/1040x760/1642289.png"
    assert fields["team_logo_url"]=="https://cdn.nba.com/logos/wnba/1611661326/global/L/logo.svg"
    assert "untrusted_extra" not in fields
    runtime_source=(ROOT/"runless_v2/wnba_pra_page1_final_polish_runtime_v1.py").read_text()
    assert "wnba_pra_page_model_artifact_final_polish_v1" in runtime_source


def test_card_collapses_missing_optional_context():
    import wnba_pra_page1_final_polish_v1 as page
    html=page._card(_row())
    assert "Not verified on Page 1" not in html and "Exact provider quote" not in html
    assert html.count("More trends in Player Analysis")==1
    assert "<span>L5</span><b>—</b>" in html and "<span>L10</span><b>—</b>" in html and "<span>Season</span><b>—</b>" in html


def test_verified_images_keep_initials_as_failure_fallback():
    import wnba_pra_page1_final_polish_v1 as page
    html=page._card(_row(headshot_url="https://cdn.wnba.com/headshots/wnba/latest/1040x760/1642289.png",team_logo_url="https://cdn.nba.com/logos/wnba/1611661326/global/L/logo.svg"))
    assert "cdn.wnba.com/headshots/wnba/latest/1040x760/1642289.png" in html and "cdn.nba.com/logos/wnba/1611661326/global/L/logo.svg" in html
    assert 'loading="lazy"' in html and 'decoding="async"' in html and "onerror=" in html
    assert "KC" in html and "GS" in html


def test_final_pick_is_premium_hero_with_decision_metrics():
    import wnba_pra_page1_final_polish_v1 as page
    html=page._final_pick_html({"player_name":"Kaitlyn Chen","line":6.5,"side":"over"},_row(),rank=1)
    for token in ("KYRE MODEL — TOP PRA PICK","Kaitlyn Chen","OVER 6.5 PRA","71.8%","8.5 PRA","21.9%","DraftKings","-116"):
        assert token in html


def test_polish_is_additive_network_free_and_keeps_frozen_files_untouched():
    ui=(ROOT/"wnba_pra_page1_final_polish_v1.py").read_text()
    runtime=(ROOT/"runless_v2/wnba_pra_page1_final_polish_runtime_v1.py").read_text()
    compat=(ROOT/"wnba_pra_hub_v3612.py").read_text()
    assert "font-size:10px" in ui and "font-size:9px" in ui and "Analyze Pick" in ui
    assert "import requests" not in ui and "import httpx" not in ui and "espn" not in ui.casefold() and "sportsgameodds" not in ui.casefold()
    assert "wnba_pra_page_model_artifact_final_polish_v1" in runtime
    assert "import wnba_pra_hub_v3617 as active" in compat
    assert "active.render_page_snapshot = _page1_final_polish.render_page_snapshot" in compat
