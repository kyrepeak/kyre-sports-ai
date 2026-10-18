from __future__ import annotations
import pandas as pd


def _row(book, line, odds, freshness="FRESH", player_key="p1", player="A Player"):
    return {"player_key": player_key, "player": player, "book": book, "line": line, "over_odds": odds, "freshness": freshness, "projection": 31.2, "model_over": .61, "edge": .06}


def test_three_current_books_build_verified_median_consensus():
    from wnba_pra_market_consensus_v1 import build_market_consensus
    src = pd.DataFrame([_row("A", 29.5, -110), _row("B", 29.5, -105), _row("C", 29.5, +100)])
    before = src.copy(deep=True)
    out = build_market_consensus(src)
    assert len(out) == 1
    r = out.iloc[0]
    assert r["book_count"] == 3 and r["current_quote_count"] == 3
    assert r["consensus_line"] == 29.5 and r["min_line"] == 29.5 and r["max_line"] == 29.5
    assert r["best_over_odds"] == 100
    assert r["evidence_state"] == "VERIFIED_MULTI_SOURCE"
    assert set(r["books"]) == {"A", "B", "C"}
    pd.testing.assert_frame_equal(src, before)


def test_different_current_lines_use_median_and_range():
    from wnba_pra_market_consensus_v1 import build_market_consensus
    out = build_market_consensus(pd.DataFrame([_row("A", 28.5, -115), _row("B", 29.5, -110), _row("C", 30.5, +105)]))
    r = out.iloc[0]
    assert r["consensus_line"] == 29.5
    assert r["min_line"] == 28.5 and r["max_line"] == 30.5


def test_single_current_quote_is_single_source():
    from wnba_pra_market_consensus_v1 import build_market_consensus
    r = build_market_consensus(pd.DataFrame([_row("A", 30.5, -110)])).iloc[0]
    assert r["evidence_state"] == "SINGLE_SOURCE"
    assert r["current_quote_count"] == 1


def test_stale_quotes_excluded_from_current_consensus_but_counted():
    from wnba_pra_market_consensus_v1 import build_market_consensus
    out = build_market_consensus(pd.DataFrame([_row("A", 29.5, -110), _row("B", 45.5, +120, "STALE")]))
    r = out.iloc[0]
    assert r["book_count"] == 2
    assert r["current_quote_count"] == 1
    assert r["consensus_line"] == 29.5
    assert r["books"] == ("A", "B")


def test_only_stale_quotes_are_labeled_stale_and_empty_input_stays_empty():
    from wnba_pra_market_consensus_v1 import build_market_consensus
    stale = build_market_consensus(pd.DataFrame([_row("B", 31.5, +100, "STALE")])).iloc[0]
    assert stale["evidence_state"] == "STALE"
    assert stale["current_quote_count"] == 0
    assert pd.isna(stale["consensus_line"])
    empty = build_market_consensus(pd.DataFrame())
    assert empty.empty
