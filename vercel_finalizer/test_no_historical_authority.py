from pathlib import Path


def test_historical_authority_cannot_return():
    root = Path(__file__).parent
    sources = "\n".join((root / name).read_text(encoding="utf-8") for name in ("app.py", "publish_gate_build.py"))
    assert "/pulls/1526" not in sources
    assert "DEFAULT_PR_NUMBER = 1526" not in sources
    assert 'ALLOWED_BRANCH = "api2-universal-sports-source-finalization-v1-step1"' not in sources
