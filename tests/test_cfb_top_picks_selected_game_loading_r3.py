from __future__ import annotations

from unittest.mock import patch

import cfb_top_picks_page_v11 as page

EVENT_ID = "401856732"


class _Spinner:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Board:
    def __init__(self):
        self.calls: list[str] = []

    def html(self, value: str):
        self.calls.append(value)


def run_selected_game_loading_regression() -> None:
    row = {
        "rank": 1,
        "event_id": EVENT_ID,
        "away": "Ole Miss",
        "home": "Texas",
        "pick": "Ole Miss",
        "probability_value": 0.83,
        "probability": 83,
        "odds": "-473",
    }
    board = _Board()

    def query_value(key):
        if key == page.prior.MARKET_QUERY:
            return "MONEYLINE"
        if key == page.prior.base.TOP_PICK_DETAIL_QUERY:
            return EVENT_ID
        return ""

    with (
        patch.object(page.st, "markdown", lambda *a, **k: None),
        patch.object(page.st, "spinner", lambda *a, **k: _Spinner()),
        patch.object(page.st, "empty", lambda: board),
        patch.object(page.prior, "build_market_top_picks", lambda *a, **k: ([row], {"slate_date": "2026-10-24"})),
        patch.object(page.prior.base, "_query_value", query_value),
        patch.object(
            page,
            "_page_html",
            lambda picks, diag, slate, event, detail, **k: "loading" if detail and detail.get("loading") else "detail",
        ),
        patch.object(page, "_build_pick_detail", lambda row, slate: {"ready": True, "event_id": EVENT_ID}),
    ):
        page.render_top_picks_page()

    assert board.calls == ["loading", "detail"], board.calls


def test_selected_game_loading_state_reaches_detail_without_attribute_error():
    run_selected_game_loading_regression()


if __name__ == "__main__":
    run_selected_game_loading_regression()
    print("CFB_TOP_PICKS_SELECTED_GAME_LOADING_R3_OK")
