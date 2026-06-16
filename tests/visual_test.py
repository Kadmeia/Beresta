import os
import time
from playwright.sync_api import sync_playwright

FRONTEND_HTML = "file://" + os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"))

def run_visual_test():
    print("Запускаю визуальный тест. Пожалуйста, не трогайте мышку и клавиатуру...")
    
    with sync_playwright() as p:
        # Launch visually with slow_mo to make actions visible to human eye
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        context = browser.new_context()
        page = context.new_page()
        
        # Mock pywebview so the JS doesn't break
        page.add_init_script("""
            window.pywebview = {
                api: {
                    check_model: () => Promise.resolve(true),
                    get_os_info: () => Promise.resolve('darwin'),
                    get_ocr_engine: () => Promise.resolve('paddleocr'),
                    process_files: () => new Promise(resolve => {
                        setTimeout(() => {
                            resolve([
                                { start_page: 1, end_page: 1, parties: 'ООО "РОГА"_ИП КОПЫТА', short_name: 'Акт', date: '15.05.2025', isManualEdit: false },
                                { start_page: 2, end_page: 3, parties: 'ОАО АЛЬФА_ЗАО БЕТА', short_name: 'Договор', date: '10.04.2025', isManualEdit: false }
                            ]);
                        }, 2000);
                    })
                }
            };
        """)
        
        page.goto(FRONTEND_HTML)
        page.wait_for_selector('#opt-parties', state='attached')
        
        print("Шаг 1: Проверка сохранения настроек (localStorage)")
        # Uncheck a box
        page.evaluate("document.getElementById('opt-parties').click()")
        # Type a prefix
        page.fill('input[placeholder="Например: 2025_"]', 'ВИЗУАЛЬНЫЙ_ТЕСТ_')
        page.evaluate("document.querySelector('input[placeholder=\"Например: 2025_\"]').dispatchEvent(new Event('change'))")
        
        print("Шаг 2: Перезагрузка страницы, чтобы убедиться, что настройки сохранились")
        page.reload()
        page.wait_for_selector('#opt-parties', state='attached')
        
        print("Шаг 3: Имитация загрузки PDF файла")
        # Trigger the process visually
        page.evaluate("""
            selectedFiles = ['/Volumes/CodeOS/Beresta/Handwritten_2026-06-08_152924.pdf'];
            startProcessing();
        """)
        
        print("Ожидание обработки документа...")
        page.wait_for_selector('#preview-table tbody tr', state='attached')
        
        print("Шаг 4: Проверка очистки подчеркиваний и кавычек в названиях")
        # Ensure 'opt-pages' is checked
        if not page.is_checked('#opt-pages'):
            page.evaluate("document.getElementById('opt-pages').click()")
            
        # Trigger naming logic for first row
        page.evaluate("triggerAutoName(0)")
        # Trigger naming logic for second row
        page.evaluate("triggerAutoName(1)")
        
        print("Осмотр результата... (задержка 5 секунд)")
        time.sleep(5)
        
        browser.close()
        print("Визуальный тест успешно завершен!")

if __name__ == "__main__":
    run_visual_test()
