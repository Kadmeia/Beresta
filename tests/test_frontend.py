import os
import pytest
from playwright.sync_api import sync_playwright

FRONTEND_HTML = "file://" + os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"))

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()

@pytest.fixture
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    # Mock pywebview so the JS doesn't break
    page.add_init_script("""
        window.pywebview = {
            api: {
                check_model: () => Promise.resolve(true),
                get_os_info: () => Promise.resolve('linux'),
                get_ocr_engine: () => Promise.resolve('tesseract'),
            }
        };
    """)
    page.goto(FRONTEND_HTML)
    yield page
    context.close()

def test_local_storage_persistence(page):
    # Wait for DOM to be ready
    page.wait_for_selector('#opt-parties', state='attached')
    
    # The default state of opt-parties is checked
    # We uncheck it. Using evaluate click because it might be visually hidden by CSS
    page.evaluate("document.getElementById('opt-parties').click()")
    
    # We enter a custom prefix
    page.fill('input[placeholder="Например: 2025_"]', 'TEST_PREFIX_')
    
    # Simulate the 'change' event to trigger saveSettings() since fill might just trigger input
    page.evaluate("document.querySelector('input[placeholder=\"Например: 2025_\"]').dispatchEvent(new Event('change'))")
    
    # Reload page
    page.reload()
    page.wait_for_selector('#opt-parties', state='attached')
    
    # Verify settings persisted via localStorage
    assert not page.is_checked('#opt-parties')
    assert page.input_value('input[placeholder="Например: 2025_"]') == 'TEST_PREFIX_'

def test_generate_auto_name_removes_underscores(page):
    # Call renderPreviewTable to initialize the global variable
    page.evaluate("""
        window.pywebview.api.process_files = () => Promise.resolve([{
            start_page: 1,
            end_page: 1,
            parties: 'ООО "РОГА"_ИП КОПЫТА',
            short_name: 'Акт',
            date: '15.05.2025',
            isManualEdit: false
        }]);
        selectedFiles = ['dummy.pdf'];
        startProcessing();
    """)
    # Wait for the table to render
    page.wait_for_selector('#preview-table tbody tr', state='attached')
    
    # Enter a prefix with underscores
    page.fill('input[placeholder="Например: 2025_"]', 'PREFIX_')
    
    # Check "Add pages" to see if it appends "- 1 л"
    page.evaluate("document.getElementById('opt-pages').click()")
        
    # Trigger auto name generation
    page.evaluate("triggerAutoName(0)")
    
    # Get the generated name
    # We must access previewData through evaluate since it's a let variable, not window.
    new_name = page.evaluate("previewData[0].new_name")
    
    # The underscores from prefix and parties should be replaced by spaces.
    # The quotes should be removed.
    assert "_" not in new_name
    assert '"' not in new_name
    assert "ООО РОГА ИП КОПЫТА" in new_name
    assert new_name.endswith('.pdf')
