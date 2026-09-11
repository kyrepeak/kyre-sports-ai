from pathlib import Path


WORKFLOW = Path('.github/workflows/devsystem-targeted-ci.yml')
EPOCH = Path('devsystem/browser_cache_epoch_v1.txt')
TOOLING = Path('devsystem/browser_tooling_v1.txt')
BROWSER_QA = Path('devsystem/browser_qa_v1.py')


def _browser_lane(text: str) -> str:
    return text.split('  browser-qa:', 1)[1].split('  cfb-critical:', 1)[0]


def test_browser_cache_contract_is_present_and_fail_safe():
    text = WORKFLOW.read_text(encoding='utf-8')
    lane = _browser_lane(text)
    browser_qa = BROWSER_QA.read_text(encoding='utf-8')

    assert 'Restore Browser QA stack' in lane
    assert 'id: browser-stack-cache' in lane
    assert lane.count('uses: actions/cache@v4') == 1
    assert '.venv-browser-qa' in lane
    assert '~/.cache/ms-playwright' in lane
    assert "steps.browser-stack-cache.outputs.cache-hit != 'true'" in lane
    assert 'Build Browser QA stack on cache miss' in lane
    assert '-r devsystem/browser_tooling_v1.txt' in lane
    assert 'python -m playwright install chromium' in lane
    assert 'Resolve Playwright cache identity' not in lane
    assert 'Restore Playwright browser binaries' not in lane
    assert 'Verify Chromium can launch' not in lane
    assert 'sync_playwright()' in browser_qa
    assert 'p.chromium.launch(' in browser_qa
    assert 'DEVSYSTEM_BROWSER_QA_GREEN' in browser_qa


def test_browser_stack_cache_is_bound_to_python_requirements_and_tooling():
    text = WORKFLOW.read_text(encoding='utf-8')
    lane = _browser_lane(text)

    assert 'id: browser-python' in lane
    assert 'steps.browser-python.outputs.python-version' in lane
    assert "devsystem-browser-stack-${{ runner.os }}-py${{ steps.browser-python.outputs.python-version }}-${{ hashFiles('requirements.txt', 'devsystem/browser_tooling_v1.txt', 'devsystem/browser_cache_epoch_v1.txt') }}" in lane


def test_browser_tooling_pins_playwright_identity():
    text = TOOLING.read_text(encoding='utf-8')

    assert 'pytest' in text
    assert 'requests' in text
    assert 'playwright==1.62.0' in text


def test_browser_cache_contract_tests_run_inside_protected_browser_lane():
    text = WORKFLOW.read_text(encoding='utf-8')
    lane = _browser_lane(text)

    assert 'Self-test browser QA and cache contracts' in lane
    assert 'tests/test_devsystem_browser_qa_v1.py' in lane
    assert 'tests/test_devsystem_browser_cache_v1.py' in lane


def test_browser_cache_keeps_real_qa_and_avoids_duplicate_restore_actions():
    text = WORKFLOW.read_text(encoding='utf-8')
    lane = _browser_lane(text)

    assert 'playwright install --with-deps chromium' not in lane
    assert 'Restore browser QA virtualenv' not in lane
    assert 'Restore Playwright browser binaries' not in lane
    assert 'python devsystem/browser_qa_v1.py' in lane
    assert '--base-url http://127.0.0.1:8501' in lane
    assert 'Upload browser QA evidence' in lane


def test_browser_cache_epoch_is_explicit_and_versioned():
    text = EPOCH.read_text(encoding='utf-8')

    assert 'DEVSYSTEM_BROWSER_CACHE_EPOCH=1' in text
    assert 'Bump the epoch' in text
