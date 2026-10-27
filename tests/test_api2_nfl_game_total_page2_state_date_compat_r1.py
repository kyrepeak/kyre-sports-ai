import nfl_game_totals_hub_v8_1 as mobile


def test_mobile_exposes_primary_state_date_compat_alias_for_page2() -> None:
    assert mobile._STATE_DATE_KEY == mobile._DATE_STATE_KEYS[0]
