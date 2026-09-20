from __future__ import annotations

from pathlib import Path

import cfb_game_total_clean_page_v15 as page


ROOT = Path(__file__).resolve().parents[1]


def test_v164_identity_marker_is_natively_hidden(monkeypatch) -> None:
    rendered: list[str] = []
    monkeypatch.setattr(
        page.st,
        "markdown",
        lambda html, **kwargs: rendered.append(str(html)),
    )

    page._render_v164_identity()

    assert len(rendered) == 1
    html = rendered[0]
    assert 'data-testid="cfb-game-total-v164-active"' in html
    assert 'hidden aria-hidden="true"' in html
    assert 'style="display:none!important"' in html
    assert page.ACTIVE_MARKER in html
    assert page.DEPLOYMENT_PROOF_MARKER in html
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False


def test_production_verifier_reads_hidden_identity_not_visible_body() -> None:
    source = (ROOT / "devsystem" / "production_verify_v164_logos.py").read_text(
        encoding="utf-8"
    )

    assert 'frame.locator(\'[data-testid="cfb-game-total-v164-active"]\').last' in source
    assert 'identity.wait_for(state="attached"' in source
    assert "if identity.is_visible():" in source
    assert 'identity.text_content(timeout=5000)' in source
    assert 'verification_text = body + "\\n" + identity_text' in source
    assert "REQUIRED_PATCH_MARKER not in verification_text" in source
