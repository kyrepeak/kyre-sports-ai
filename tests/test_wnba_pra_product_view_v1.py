from __future__ import annotations
from contextlib import contextmanager
import pandas as pd
from wnba_pra_product_snapshot_v1 import PRAProductSnapshot
from wnba_pra_playoff_context_v1 import PlayoffContext
from wnba_pra_product_view_model_v1 import PlayerDecisionView

class FakeStreamlit:
    def __init__(self): self.visible=[]; self.expanders=[]; self.json_payloads=[]
    def markdown(self, value, **kwargs): self.visible.append(str(value))
    def caption(self, value, **kwargs): self.visible.append(str(value))
    def info(self, value, **kwargs): self.visible.append(str(value))
    def warning(self, value, **kwargs): self.visible.append(str(value))
    @contextmanager
    def expander(self, label, expanded=False):
        self.expanders.append((label, expanded)); yield self
    def json(self, value, **kwargs): self.json_payloads.append(value)


def snapshot(final=None, market=None):
    return PRAProductSnapshot("2026-10-19", pd.DataFrame(), {"state":"VERIFIED"}, pd.DataFrame(), pd.DataFrame(market or []), {}, pd.DataFrame(), {}, pd.DataFrame(), {"source":"5M"}, pd.DataFrame(final or []), {"state":"VERIFIED"}, {"state":"VERIFIED"})


def ctx(off=False):
    ng={"game_id":"g1","away":{"full_name":"Atlanta Dream"},"home":{"full_name":"Golden State Valkyries"},"game_datetime_eastern":"2026-10-19T17:00:00-07:00"}
    return PlayoffContext("2026-10-18" if off else "2026-10-19", "2026-10-19", not off, pd.DataFrame(), ng, "WNBA Finals • Game 2", "GSV leads 1-0", "VERIFIED_MULTI_SOURCE", ("WNBA","ESPN"), "No WNBA game today. Next verified game is tomorrow." if off else "")


def view(*, unresolved=False, selected=True):
    return PlayerDecisionView("p1","A Player","Atlanta Dream","Golden State Valkyries","g1","https://img/p.png","https://img/t.png",34.0,"STARTER","UNRESOLVED" if unresolved else "VERIFIED",20.0,7.0,5.0,32.0,29.5,3,.64,.36,.075,"🔥 BEST BET",84.2,selected,"UNRESOLVED" if unresolved else "VERIFIED_MULTI_SOURCE")


def test_customer_surface_is_pra_first_and_hides_internal_pipeline(monkeypatch):
    import wnba_pra_product_view_v1 as page
    import wnba_pra_advanced_diagnostics_v1 as diag
    fake=FakeStreamlit(); monkeypatch.setattr(page,"st",fake); monkeypatch.setattr(diag,"st",fake)
    page.render_pra_product(snapshot(final=[{"game_id":"g1","player_key":"p1"}]), ctx(), (view(),), pd.DataFrame([{"player_key":"p1","book_count":3}]))
    text="\n".join(fake.visible)
    assert "WNBA PRA" in text and "PRA Player Board" in text and "P / R / A" in text and "Final PRA Card" in text
    assert "3 books" in text
    for banned in ("Step 6","Step 7","Step 8","Step 9","RUN PRA 5,000,000 STANDARD SIMS","PRA production HOLD","Monte Carlo restore DISABLED"):
        assert banned not in text
    assert ("⚙️ Advanced Diagnostics", False) in fake.expanders


def test_off_day_shows_no_game_today_and_next_matchup(monkeypatch):
    import wnba_pra_product_view_v1 as page
    import wnba_pra_advanced_diagnostics_v1 as diag
    fake=FakeStreamlit(); monkeypatch.setattr(page,"st",fake); monkeypatch.setattr(diag,"st",fake)
    page.render_pra_product(snapshot(), ctx(off=True), (), pd.DataFrame())
    text="\n".join(fake.visible)
    assert "No WNBA game today" in text
    assert "Atlanta Dream" in text and "Golden State Valkyries" in text


def test_no_market_keeps_projection_research_and_plain_language_pause(monkeypatch):
    import wnba_pra_product_view_v1 as page
    import wnba_pra_advanced_diagnostics_v1 as diag
    fake=FakeStreamlit(); monkeypatch.setattr(page,"st",fake); monkeypatch.setattr(diag,"st",fake)
    no_market=view(selected=False); no_market=no_market.__class__(**{**no_market.__dict__,"market_line":None,"book_count":0})
    page.render_pra_product(snapshot(), ctx(), (no_market,), pd.DataFrame())
    text="\n".join(fake.visible)
    assert "32.0" in text
    assert "PRA market lines are not available yet" in text


def test_unresolved_availability_keeps_research_and_blocks_final_message(monkeypatch):
    import wnba_pra_product_view_v1 as page
    import wnba_pra_advanced_diagnostics_v1 as diag
    fake=FakeStreamlit(); monkeypatch.setattr(page,"st",fake); monkeypatch.setattr(diag,"st",fake)
    page.render_pra_product(snapshot(final=[{"game_id":"g1","player_key":"p1"}]), ctx(), (view(unresolved=True, selected=False),), pd.DataFrame())
    text="\n".join(fake.visible)
    assert "32.0" in text
    assert "Final PRA decisions are waiting for verified availability." in text


def test_final_card_uses_only_snapshot_selected_rows_max_five_and_css_is_mobile_safe(monkeypatch):
    import wnba_pra_product_view_v1 as page
    import wnba_pra_advanced_diagnostics_v1 as diag
    fake=FakeStreamlit(); monkeypatch.setattr(page,"st",fake); monkeypatch.setattr(diag,"st",fake)
    views=[]; final=[]
    for i in range(7):
        base=view(selected=i<6)
        v=base.__class__(**{**base.__dict__,"player_key":f"p{i}","player":f"Player {i}","game_id":f"g{i}"})
        views.append(v)
        if i<6: final.append({"game_id":f"g{i}","player_key":f"p{i}"})
    page.render_pra_product(snapshot(final=final), ctx(), tuple(views), pd.DataFrame())
    text="\n".join(fake.visible)
    assert sum(f"Player {i}" in text for i in range(6)) >= 5
    final_text=text.split("Final PRA Card",1)[-1]
    assert "Player 5" not in final_text and "Player 6" not in final_text
    assert "@media(max-width:720px)" in page.PRODUCT_CSS
    assert "min-width:" not in page.PRODUCT_CSS
