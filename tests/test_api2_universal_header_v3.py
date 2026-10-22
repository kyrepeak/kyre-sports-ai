from __future__ import annotations

import inspect
from pathlib import Path

import universal_page_experience_runtime_v1 as runtime
import universal_sports_nav_ui_v1 as nav


def test_universal_nav_is_mounted_before_transition_and_destination_slots() -> None:
    source = inspect.getsource(runtime._render_page_experience_active)
    nav_pos = source.index("core._render_destination_shell(runtime.active)")
    transition_pos = source.index("transition_slot = st.empty()")
    destination_pos = source.index("destination_slot = st.empty()")
    assert nav_pos < transition_pos < destination_pos


def test_header_brand_is_professional_and_sport_labels_are_words_only() -> None:
    assert nav.HEADER_TITLE == "KYRE SPORTS AI"
    assert nav.HEADER_SUBTITLE == "Professional Sports Analytics"
    assert nav._SPORT_LABELS == {"nfl": "NFL", "cfb": "CFB", "nba": "NBA", "mlb": "MLB", "wnba": "WNBA"}
    assert all(icon not in "".join(nav._SPORT_LABELS.values()) for icon in ("🏈", "🏟️", "🏀", "⚾"))


def test_every_sport_logo_is_local_and_embedded_without_runtime_hotlinks() -> None:
    assert set(nav._SPORT_LOGO_ASSET_PATHS) == {"nfl", "cfb", "nba", "mlb", "wnba"}
    assert set(nav._SPORT_LOGO_DATA_URIS) == {"nfl", "cfb", "nba", "mlb", "wnba"}
    for sport_id, relative_path in nav._SPORT_LOGO_ASSET_PATHS.items():
        asset = Path(nav.__file__).resolve().parent / relative_path
        assert asset.is_file(), f"missing local {sport_id} league mark"
        assert "<svg" in asset.read_text(encoding="utf-8").lower()
        assert nav._SPORT_LOGO_DATA_URIS[sport_id].startswith("data:image/svg+xml;base64,")
    joined = " ".join(nav._SPORT_LOGO_DATA_URIS.values()).lower()
    assert "http://" not in joined
    assert "https://" not in joined
    assert "espn" not in joined


def test_header_css_is_top_sticky_premium_and_logo_backed() -> None:
    css = nav._NAV_CSS.lower().replace(" ", "")
    assert "position:sticky" in css
    assert "top:.2rem" in css or "top:0" in css
    assert "backdrop-filter:blur" in css
    assert "ks-universal-brand-title" in css
    assert "ks-universal-brand-subtitle" in css
    assert "background-image:url(" in css
    assert "data:image/svg+xml;base64," in css
    assert "https://" not in css
    assert "data-testid=\"stpills\"" in css


def test_header_markup_contains_title_and_subtitle() -> None:
    markup = nav._brand_markup()
    assert "KYRE SPORTS AI" in markup
    assert "Professional Sports Analytics" in markup
    assert "ks-universal-brand-title" in markup
    assert "ks-universal-brand-subtitle" in markup
