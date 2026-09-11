from pathlib import Path


WORKFLOW = Path('.github/workflows/devsystem-targeted-ci.yml')
EPOCH = Path('devsystem/browser_cache_epoch_v1.txt')
BROWSER_QA = Path('devsystem/browser_qa_v1.py')


def test_browser_cache_contract_is_present_and_fail_safe():
    text = WORKFLOW.read_text(encoding='utf-8')
    browser_qa = BROWSER_QA.read_text(encoding='utf-8')

    assert 'Restore browser QA virtualenv' in text
    assert 'actions/cache@v4' in text
    assert '.venv-browser-qa' in text
    assert "steps.browser-venv-cache.outputs.cache-hit != 'true'" in text
    assert 'Resolve Playwright cache identity' in text
    assert '~/.cache/ms-playwright' in text
    assert "steps.playwright-cache.outputs.cache-hit != 'true'" in text
    assert 'python -m playwright install chromium' in text
    assert 'Verify Chromium can launch' not in text
    assert 'sync_playwright()' in browser_qa
    assert 'p.chromium.launch(' in browser_qa
    assert 'DEVSYSTEM_BROWSER_QA_GREEN' in browser_qa


def test_browser_venv_cache_is_bound_to_exact_setup_python_version():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'id: browser-python' in text
    assert 'steps.browser-python.outputs.python-version' in text
    assert 'devsystem-browser-venv-${{ runner.os }}-py${{ steps.browser-python.outputs.python-version }}-' in text


def test_browser_cache_contract_tests_run_inside_protected_browser_lane():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'Self-test browser QA and cache contracts' in text
    assert 'tests/test_devsystem_browser_qa_v1.py' in text
    assert 'tests/test_devsystem_browser_cache_v1.py' in text


def test_browser_cache_avoids_expensive_with_deps_install_and_keeps_real_qa():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'playwright install --with-deps chromium' not in text
    assert 'python devsystem/browser_qa_v1.py' in text
    assert '--base-url http://127.0.0.1:8501' in text
    assert 'Upload browser QA evidence' in text


def test_browser_cache_epoch_is_explicit_and_versioned():
    text = EPOCH.read_text(encoding='utf-8')

    assert 'DEVSYSTEM_BROWSER_CACHE_EPOCH=1' in text
    assert 'Bump the epoch' in text
