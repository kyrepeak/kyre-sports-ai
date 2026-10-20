from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def _requirement_names() -> set[str]:
    names: set[str] = set()
    for raw in (ROOT / 'requirements.txt').read_text(encoding='utf-8').splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        name = re.split(r'[<>=!~\[; ]', line, maxsplit=1)[0].strip().lower().replace('_', '-')
        if name:
            names.add(name)
    return names


def test_cfb_player_props_page1_declares_all_root_runtime_dependencies():
    names = _requirement_names()
    assert 'httpx' in names, 'CFB Player Props Page 1 imports httpx in Streamlit production but root requirements.txt does not declare it'
    assert 'fastapi' in names, 'CFB market identity imports fastapi in Streamlit production but root requirements.txt does not declare it'
