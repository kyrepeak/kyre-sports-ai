"""Regression checks for CFB O/U multi-source logo resolver V2."""
from __future__ import annotations

import cfb_over_under_logo_resolver_v2 as logos


def test_wikipedia_candidate_scoring_handles_miami_fl_with_acc_context():
    page = {
        "title": "Miami Hurricanes football",
        "extract": "The Miami Hurricanes compete in the ACC.",
    }
    assert logos._candidate_score(page, "Miami (FL)", "ACC") >= 12.0


def test_best_official_url_prefers_football_athletics_link():
    page = {
        "extlinks": [
            {"url": "https://www.youtube.com/example"},
            {"url": "https://example.edu/"},
            {"url": "https://famuathletics.com/sports/football"},
        ]
    }
    assert logos._best_official_url(page) == "https://famuathletics.com/sports/football"


def test_official_html_parser_prefers_logo_image():
    parser = logos._LogoHtmlParser("Florida A&M")
    parser.feed(
        '''
        <html><head><meta property="og:image" content="https://example.com/hero.jpg"></head>
        <body>
          <img class="site-logo" alt="Florida A&M Logo" src="/images/famu-logo.png">
          <img alt="player photo" src="/images/player.jpg">
        </body></html>
        '''
    )
    assert parser.image_candidates
    score, src = sorted(parser.image_candidates, reverse=True)[0]
    assert score > 0
    assert src == "/images/famu-logo.png"


def test_resolve_team_logo_prefers_official_over_wikipedia(monkeypatch):
    page = {
        "pageid": 1,
        "title": "Florida A&M Rattlers football",
        "_logo_score": 20.0,
        "fullurl": "https://en.wikipedia.org/wiki/Florida_A%26M_Rattlers_football",
        "thumbnail": {"source": "https://upload.wikimedia.org/wiki-thumb.png"},
        "extlinks": [{"url": "https://famuathletics.com/sports/football"}],
    }
    monkeypatch.setattr(logos, "_wikipedia_candidates", lambda *a, **k: ([page], []))
    monkeypatch.setattr(
        logos,
        "_official_page_logo",
        lambda *a, **k: ("https://famuathletics.com/images/logo.png", []),
    )
    monkeypatch.setattr(logos, "_commons_logo", lambda *a, **k: ("", []))

    out = logos.resolve_team_logo.__wrapped__("Florida A&M", "florida-a-m", "SWAC")
    assert out["logo_provider"] == "official_athletics"
    assert out["logo"] == "https://famuathletics.com/images/logo.png"
    assert out["confidence"] == "HIGH"


def test_resolve_team_logo_uses_wikipedia_when_official_unavailable(monkeypatch):
    page = {
        "pageid": 2,
        "title": "Miami Hurricanes football",
        "_logo_score": 20.0,
        "fullurl": "https://en.wikipedia.org/wiki/Miami_Hurricanes_football",
        "original": {"source": "https://upload.wikimedia.org/Miami_Hurricanes_logo.svg"},
        "extlinks": [{"url": "https://miamihurricanes.com/sports/football"}],
    }
    monkeypatch.setattr(logos, "_wikipedia_candidates", lambda *a, **k: ([page], []))
    monkeypatch.setattr(logos, "_official_page_logo", lambda *a, **k: ("", []))
    monkeypatch.setattr(logos, "_commons_logo", lambda *a, **k: ("", []))

    out = logos.resolve_team_logo.__wrapped__("Miami (FL)", "miami-fl", "ACC")
    assert out["logo_provider"] == "wikipedia_pageimage"
    assert out["logo"] == "https://upload.wikimedia.org/Miami_Hurricanes_logo.svg"


def test_resolve_team_logo_uses_commons_as_last_fallback(monkeypatch):
    monkeypatch.setattr(logos, "_wikipedia_candidates", lambda *a, **k: ([], []))
    monkeypatch.setattr(
        logos,
        "_commons_logo",
        lambda *a, **k: ("https://upload.wikimedia.org/commons-logo.svg", []),
    )

    out = logos.resolve_team_logo.__wrapped__("Example State", "example-state", "ACC")
    assert out["logo_provider"] == "wikimedia_commons"
    assert out["logo"].endswith("commons-logo.svg")


def test_resolve_visuals_fills_only_missing_side(monkeypatch):
    monkeypatch.setattr(
        logos.espn,
        "resolve_visuals",
        lambda game: {
            "away": {
                "logo": "https://a.espncdn.com/away.png",
                "source": "ESPN College Football",
            },
            "home": {},
        },
    )

    calls = []

    def fallback(name, slug="", conference=""):
        calls.append((name, slug, conference))
        return {
            "logo": "https://upload.wikimedia.org/home.svg",
            "logo_provider": "wikipedia_pageimage",
            "source": "Wikipedia / Wikimedia",
        }

    monkeypatch.setattr(logos, "resolve_team_logo", fallback)

    out = logos.resolve_visuals(
        {
            "away_team": "Florida A&M",
            "away_team_slug": "florida-a-m",
            "away_conference": "SWAC",
            "home_team": "Miami (FL)",
            "home_team_slug": "miami-fl",
            "home_conference": "ACC",
        }
    )

    assert out["away"]["logo"] == "https://a.espncdn.com/away.png"
    assert out["away"]["logo_provider"] == "espn"
    assert out["home"]["logo"] == "https://upload.wikimedia.org/home.svg"
    assert calls == [("Miami (FL)", "miami-fl", "ACC")]


def test_resolve_visuals_can_fill_both_when_espn_is_empty(monkeypatch):
    monkeypatch.setattr(
        logos.espn,
        "resolve_visuals",
        lambda game: {"away": {}, "home": {}},
    )

    def fallback(name, slug="", conference=""):
        return {
            "logo": f"https://upload.wikimedia.org/{slug}.svg",
            "logo_provider": "wikimedia_commons",
            "source": "Wikimedia Commons",
        }

    monkeypatch.setattr(logos, "resolve_team_logo", fallback)

    out = logos.resolve_visuals(
        {
            "away_team": "Florida A&M",
            "away_team_slug": "florida-a-m",
            "away_conference": "SWAC",
            "home_team": "Miami (FL)",
            "home_team_slug": "miami-fl",
            "home_conference": "ACC",
        }
    )
    assert out["away"]["logo"].endswith("florida-a-m.svg")
    assert out["home"]["logo"].endswith("miami-fl.svg")


def test_page_image_rejects_game_photo_and_wrong_team_logo():
    oregon_photo = {
        "original": {
            "source": "https://upload.wikimedia.org/wikipedia/commons/9/90/2017-11-25_Civil_War_07.jpg"
        }
    }
    wrong_harvard = {
        "original": {
            "source": "https://upload.wikimedia.org/wikipedia/commons/a/af/Dartmouth_College_Big_Green_logo.svg"
        }
    }
    miami_logo = {
        "original": {
            "source": "https://upload.wikimedia.org/wikipedia/commons/e/e9/Miami_Hurricanes_logo.svg"
        }
    }

    assert logos._page_image(oregon_photo, "Oregon") == ""
    assert logos._page_image(wrong_harvard, "Harvard") == ""
    assert logos._page_image(miami_logo, "Miami (FL)").endswith("Miami_Hurricanes_logo.svg")


def test_candidate_score_penalizes_rivalry_page():
    team_page = {
        "title": "Harvard Crimson football",
        "extract": "The Harvard Crimson football team competes in the Ivy League.",
    }
    rivalry_page = {
        "title": "Harvard–Dartmouth football rivalry",
        "extract": "The Harvard–Dartmouth football rivalry is an annual series.",
    }

    assert logos._candidate_score(team_page, "Harvard", "Ivy") > logos._candidate_score(
        rivalry_page,
        "Harvard",
        "Ivy",
    )


def test_wikipedia_html_logo_rejects_site_wordmark(monkeypatch):
    html = '''
    <html><body>
      <img class="mw-logo-wordmark" src="/static/images/mobile/copyright/wikipedia-wordmark-en-25.svg">
      <img alt="Notre Dame Fighting Irish logo" src="//upload.wikimedia.org/Notre_Dame_Fighting_Irish_logo.svg">
    </body></html>
    '''
    monkeypatch.setattr(
        logos.team_data_v1,
        "_fetch_text_with_fallback",
        lambda *a, **k: (html, []),
    )
    url, _ = logos._wikipedia_html_logo.__wrapped__(
        "https://en.wikipedia.org/wiki/Notre_Dame_Fighting_Irish_football",
        "Notre Dame",
    )
    assert "Notre_Dame_Fighting_Irish_logo.svg" in url
    assert "wikipedia-wordmark" not in url


def test_wikimedia_logo_guard_rejects_team_photo():
    photo = "https://thumb.wikimedia.org/wikipedia/en/thumb/3/31/1924-Four-Horsemen-Notre-Dame.jpg/330px-1924-Four-Horsemen-Notre-Dame.jpg"
    logo = "https://upload.wikimedia.org/wikipedia/commons/2/2f/Notre_Dame_Fighting_Irish_logo.svg"

    assert logos._is_wikimedia_logo_url(photo, "Notre Dame") is False
    assert logos._is_wikimedia_logo_url(logo, "Notre Dame") is True
