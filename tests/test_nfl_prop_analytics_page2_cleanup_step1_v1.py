from pathlib import Path

SRC = Path("nfl_prop_analytics_page2_responsive_polish_v1.py").read_text()


def test_cleanup_step1_uses_html_injection_not_markdown():
    assert "st.html(" in SRC
    assert "st.markdown(" not in SRC
    assert 'data-prop-page2-responsive-polish="v1"' in SRC
    assert 'data-prop-page2-responsive-polish-css="v1"' in SRC


def test_cleanup_step1_keeps_responsive_contract():
    assert 'RESPONSIVE_TARGETS = (390, 768, 1440)' in SRC
    assert "@media (max-width:900px)" in SRC
    assert "@media (max-width:760px)" in SRC
    assert "@media (max-width:640px)" in SRC
    assert "@media (max-width:420px)" in SRC
    assert "MAY_MODIFY_PASSING_YARDS = False" in SRC
    assert "PRESENTATION_ONLY = True" in SRC
