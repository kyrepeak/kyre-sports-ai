from universal_sports_nav_compat_v1 import apply_legacy_route_state, make_legacy_selectbox_bridge
from universal_sports_nav_controller_v1 import RouteState, apply_market_intent
from universal_sports_nav_registry_v1 import get_market, get_sport


def test_cfb_universal_shell_exposes_top_picks_as_fourth_market() -> None:
    cfb = get_sport("cfb")
    assert cfb is not None
    assert tuple(m.id for m in cfb.markets if m.live) == (
        "moneyline",
        "over-under",
        "game-total",
        "top-picks",
    )
    top_picks = get_market("cfb", "top-picks")
    assert top_picks is not None
    assert top_picks.label == "Top Picks"
    assert top_picks.legacy_market == "Top Picks"
    assert top_picks.legacy_market_key == "ks_cfb_market_touch"


def test_cfb_top_picks_tap_resolves_and_hands_off_to_existing_legacy_owner() -> None:
    initial = RouteState(
        sport_id="cfb",
        market_id="moneyline",
        source="canonical_url",
        epoch=7,
        last_market_by_sport={"cfb": "moneyline"},
    )
    selected = apply_market_intent(initial, "top-picks")
    assert selected.sport_id == "cfb"
    assert selected.market_id == "top-picks"
    assert selected.epoch == 8

    session = {}
    changed = apply_legacy_route_state(selected, session)
    assert "ks_cfb_market_touch" in changed
    assert session["ks_sport_touch"] == "College Football"
    assert session["ks_cfb_market_touch"] == "Top Picks"

    bridge = make_legacy_selectbox_bridge(lambda _label, options, *_a, **_k: list(options)[0], selected)
    assert bridge("🎯 CFB Market", ["Moneyline", "Over/Under", "Game Total", "Top Picks"]) == "Top Picks"
