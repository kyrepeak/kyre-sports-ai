from __future__ import annotations

from base64 import b64decode
from io import BytesIO
import inspect
from pathlib import Path
import tarfile

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
    expected = {"nfl", "cfb", "nba", "mlb", "wnba"}
    assert len(nav._SPORT_LOGO_BUNDLE_PARTS) == 7
    root = Path(nav.__file__).resolve().parent
    encoded = "".join((root / part).read_text(encoding="ascii").strip() for part in nav._SPORT_LOGO_BUNDLE_PARTS)
    archive = b64decode(encoded)
    with tarfile.open(fileobj=BytesIO(archive), mode="r:gz") as bundle:
        assert set(bundle.getnames()) == {f"{sport_id}.svg" for sport_id in expected}
        for sport_id in expected:
            member = bundle.extractfile(f"{sport_id}.svg")
            assert member is not None
            assert "<svg" in member.read().decode("utf-8").lower()

    assert set(nav._SPORT_LOGO_DATA_URIS) == expected
    assert all(uri.startswith("data:image/svg+xml;base64,") for uri in nav._SPORT_LOGO_DATA_URIS.values())
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
