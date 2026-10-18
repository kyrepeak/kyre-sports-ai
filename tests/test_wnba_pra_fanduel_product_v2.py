from __future__ import annotations

from contextlib import contextmanager
import pandas as pd

from wnba_pra_playoff_context_v1 import PlayoffContext
from wnba_pra_product_snapshot_v1 import PRAProductSnapshot
from wnba_pra_product_view_model_v1 import PlayerDecisionView


class FakeStreamlit:
    def __init__(self):
        self.visible = []
        self.expanders = []
        self.json_payloads = []
    def markdown(self, value, **kwargs): self.visible.append(str(value))
    def caption(self, value, **kwargs): self.visible.append(str(value))
    def info(self, value, **kwargs): self.visible.append(str(value))
    def warning(self, value, **kwargs): self.visible.append(str(value))
    def json(self, value, **kwargs): self.json_payloads.append(value)
    @contextmanager
    def expander(self, label, expanded=False):
        self.expanders.append((label, expanded))
        yield self


def snapshot(*, market=None, final=None, market_meta=None):
    return PRAProductSnapshot(
        "2026-10-19", pd.DataFrame(), {"state":"VERIFIED"}, pd.DataFrame(),
        pd.DataFrame(market or []), market_meta or {}, pd.DataFrame(), {},
        pd.DataFrame(), {"source":"preserved-mc"}, pd.DataFrame(final or []),
        {"state":"VERIFIED"}, {"state":"VERIFIED"},
    )


def ctx():
    return PlayoffContext(
        "2026-10-19", "2026-10-19", True, pd.DataFrame(), None,
        "WNBA Finals • Game 2", "Series context", "VERIFIED_MULTI_SOURCE",
        ("WNBA", "ESPN"), "",
    )


def view(*, player="Allisha Gray", eligible=True, line=31.5, selected=True):
    return PlayerDecisionView(
        "allisha gray", player, "Atlanta Dream", "Golden State Valkyries", "g1",
        "https://img/allisha.png", "https://img/dream.png", 35.0, "STARTER", "VERIFIED",
        20.0, 6.0, 5.0, 31.0, line if eligible else None, 2, .61, .39, .06,
        "OVER", 82.0, selected, "VERIFIED_MULTI_SOURCE",
        eligible, line if eligible else None, -108 if eligible else None,
        -112 if eligible else None, "CURRENT" if eligible else "UNAVAILABLE",
    )


def _render(monkeypatch, views, *, snap=None):
    import wnba_pra_product_view_v2 as product
    import wnba_pra_advanced_diagnostics_v1 as diagnostics

    fake = FakeStreamlit()
    monkeypatch.setattr(product, "st", fake)
    monkeypatch.setattr(diagnostics, "st", fake)
    product.render_pra_product(snap or snapshot(), ctx(), tuple(views), pd.DataFrame())
    return fake


def test_primary_fanduel_card_is_compact_decision_first_and_source_clear(monkeypatch):
    fake = _render(monkeypatch, [view()])
    text = "\n".join(fake.visible)

    assert "Allisha Gray" in text
    assert "https://img/allisha.png" in text
    assert "https://img/dream.png" in text
    assert "Atlanta Dream" in text and "Golden State Valkyries" in text
    assert "FanDuel PRA" in text and "31.5" in text
    assert "Model PRA" in text and "31.0" in text
    assert "Over / Under" in text and "61.0%" in text and "39.0%" in text
    assert "Edge" in text and "6.0 pp" in text
    assert "OVER" in text and "82.0" in text
    assert "CURRENT" in text and "VERIFIED MULTI SOURCE" in text
    assert "Step 5" not in text and "provider failover" not in text.lower()


def test_projection_only_or_non_fanduel_player_never_renders_on_primary_board(monkeypatch):
    fake = _render(monkeypatch, [view(player="Projection Only", eligible=False, selected=False)])
    text = "\n".join(fake.visible)

    assert "Projection Only" not in text
    assert "FanDuel PRA markets are pending" in text
    assert "31.5" not in text


def test_stale_or_missing_market_renders_honest_pending_state_without_substitution(monkeypatch):
    snap = snapshot(
        market=[{"game_id":"g1","player":"Allisha Gray","book":"DraftKings","line":32.5,"freshness":"FRESH"}],
        market_meta={"state":"STALE_STORED_MARKETS","freshness_state":"STALE"},
    )
    fake = _render(monkeypatch, [], snap=snap)
    text = "\n".join(fake.visible)

    assert "FanDuel PRA markets are pending" in text
    assert "DraftKings" not in text
    assert "32.5" not in text


def test_expandable_analysis_contains_customer_evidence_sections(monkeypatch):
    fake = _render(monkeypatch, [view()])
    text = "\n".join(fake.visible)

    assert any("Full PRA Analysis" in label for label, _ in fake.expanders)
    assert "P / R / A" in text
    assert "Minutes + Role" in text
    assert "Recent Form" in text
    assert "Opponent Context" in text
    assert "Matchup History" in text
    assert "Sources + Freshness" in text


def test_advanced_diagnostics_remains_collapsed(monkeypatch):
    fake = _render(monkeypatch, [view()])
    diagnostic = [item for item in fake.expanders if "Advanced Diagnostics" in item[0]]
    assert diagnostic == [("⚙️ Advanced Diagnostics", False)]
