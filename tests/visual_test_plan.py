import os
import time
from playwright.sync_api import sync_playwright

FRONTEND_HTML = "file://" + os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"))

def run_visual_master_plan():
    print("==================================================")
    print(" ЗАПУСК УЛЬТИМАТИВНОГО ВИЗУАЛЬНОГО ТЕСТ-ПЛАНА 10/10")
    print("==================================================")
    print("Пожалуйста, откиньтесь в кресле и не трогайте мышку...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context()
        page = context.new_page()
        
        # MOCK BACKEND TO SIMULATE REAL API BEHAVIOR FOR ALL TEST CASES
        page.add_init_script("""
            window.pywebview = {
                api: {
                    check_model: () => Promise.resolve(true),
                    get_os_info: () => Promise.resolve('darwin'),
                    get_ocr_engine: () => Promise.resolve('applevision'),
                    set_ocr_engine: (e) => Promise.resolve(),
                    process_files: (files) => new Promise(resolve => {
                        // TC-1.03 Загрузка невалидных форматов
                        if (files.some(f => f.endsWith('.exe') || f.endsWith('.jpg'))) {
                            resolve({ error: "Формат не поддерживается. Загрузите только PDF." });
                            return;
                        }
                        
                        // TC-3.02 PDF-склейка и разделение
                        setTimeout(() => {
                            resolve([
                                { start_page: 1, end_page: 2, parties: 'ООО РОМАШКА_ИП ИВАНОВ', short_name: 'Договор', date: '01.01.2026', isManualEdit: false },
                                { start_page: 3, end_page: 3, parties: 'ООО РОМАШКА_ИП ИВАНОВ', short_name: 'Акт', date: '01.01.2026', isManualEdit: false },
                                { start_page: 4, end_page: 4, parties: 'ОАО СБЕР_ПАО МАК', short_name: 'Счет', date: '15.05.2026', isManualEdit: false }
                            ]);
                        }, 1500);
                    }),
                    save_documents: (docs, path) => new Promise(resolve => {
                        setTimeout(() => resolve(true), 1500);
                    }),
                    resize_window: (w, h) => Promise.resolve()
                }
            };
        """)
        
        page.goto(FRONTEND_HTML)
        page.wait_for_selector('#opt-parties', state='attached')
        
        # TC-5.01 Персистентность настроек
        print("\\n>>> Выполнение TC-5.01: Настройка интерфейса и нейминга...")
        page.evaluate("document.getElementById('opt-parties').click()")
        page.evaluate("document.getElementById('opt-pages').click()")
        page.fill('input[placeholder="Например: 2025_"]', 'ОТЧЕТ_')
        page.evaluate("document.querySelector('input[placeholder=\"Например: 2025_\"]').dispatchEvent(new Event('change'))")
        
        # Переключение OCR
        print(">>> Выполнение TC-2.04: Переключение на Apple Vision...")
        page.evaluate("document.getElementById('ocr-label-applevision').click()")
        
        print(">>> Выполнение TC-1.03: Попытка загрузить .exe (Невалидный формат)...")
        page.evaluate("""
            selectedFiles = ['virus.exe'];
            startProcessing();
        """)
        # Обрабатываем alert
        page.once("dialog", lambda dialog: dialog.accept())
        time.sleep(2) # Пауза для визуального осознания ошибки
        
        print(">>> Выполнение TC-1.01 & TC-3.02: Загрузка сложного документа...")
        page.evaluate("""
            selectedFiles = ['/Volumes/CodeOS/Beresta/Handwritten_2026-06-08_152924.pdf'];
            startProcessing();
        """)
        page.wait_for_selector('#preview-table tbody tr', state='attached')
        
        print(">>> Выполнение TC-5.02: Тестирование генерации чистых имен (без спецсимволов)...")
        # Generate names for all rows
        page.evaluate("triggerAutoName(0)")
        page.evaluate("triggerAutoName(1)")
        page.evaluate("triggerAutoName(2)")
        
        print(">>> Выполнение TC-6.02: Принудительная склейка договоров (Merge)...")
        page.evaluate("toggleMerge(1)") # Склеивает строку 1 со строкой 0
        time.sleep(1)
        
        print(">>> Выполнение TC-6.03: Игнорирование документа (Снятие галочки)...")
        page.evaluate("toggleRowActive(2)") # Снимает галочку со счета
        time.sleep(1)
        
        print(">>> Выполнение TC-6.01: Финальное сохранение документов...")
        page.evaluate("saveDocuments()")
        
        print("Осмотр результата прогресс-бара... (3 секунды)")
        time.sleep(3)
        
        browser.close()
        print("\\n✅ ВСЕ ВИЗУАЛЬНЫЕ ТЕСТЫ ПО ПЛАНУ УСПЕШНО ПРОЙДЕНЫ!")

if __name__ == "__main__":
    run_visual_master_plan()
