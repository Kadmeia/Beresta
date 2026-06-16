import re

with open('frontend/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace CSS
css_old = r"""        /\* Preview Table Styles \*/.*?\.confidence-warn\s*\{.*?\}"""
css_new = r"""        /* Preview Layout Styles */
        .preview-container {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100vw; height: 100vh;
            background: var(--bg-color);
            z-index: 1000;
            flex-direction: column;
            overflow: hidden;
        }
        .preview-sidebar {
            width: 25%;
            min-width: 250px;
            border-right: 1px solid var(--border-color);
            background: var(--theme-switch-bg);
            display: flex;
            flex-direction: column;
            padding: 16px;
            gap: 16px;
            overflow-y: auto;
        }
        .preview-sidebar h3 {
            font-size: 13px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .page-thumbnail-container {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
            gap: 12px;
        }
        .thumbnail-card {
            background: var(--container-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            aspect-ratio: 1 / 1.4;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            position: relative;
            cursor: pointer;
            transition: all 0.2s;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            padding: 8px;
            text-align: center;
        }
        .thumbnail-card:hover {
            border-color: var(--accent);
            transform: translateY(-2px);
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        }
        .thumbnail-card .page-num {
            position: absolute;
            bottom: 6px;
            right: 6px;
            background: rgba(0,0,0,0.6);
            color: white;
            padding: 2px 6px;
            font-size: 10px;
            border-radius: 4px;
            font-weight: bold;
        }
        .table-area {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: var(--container-bg);
            overflow-y: auto;
            padding: 20px 24px;
        }
        .doc-table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }
        .doc-table th {
            padding: 12px 16px;
            background: var(--theme-switch-bg);
            color: var(--text-muted);
            font-size: 12px;
            font-weight: 600;
            border-bottom: 2px solid var(--border-color);
            text-transform: uppercase;
        }
        .doc-table td {
            padding: 10px 12px;
            border-bottom: 1px solid var(--border-color);
            vertical-align: middle;
            position: relative;
        }
        .row-warning { background-color: var(--drop-bg); }
        .row-success { background-color: rgba(45, 106, 79, 0.05); }
        [data-theme="dark"] .row-success { background-color: rgba(245, 158, 11, 0.05); }
        
        .input-field {
            width: 100%;
            padding: 8px 10px;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            font-size: 13px;
            color: var(--text-main);
            background-color: var(--container-bg);
            outline: none;
            transition: all 0.15s ease;
        }
        .input-field:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 2px rgba(45, 106, 79, 0.1);
        }
        .input-filename-custom {
            border-color: var(--accent) !important;
            font-weight: 500;
        }
        .pages-badge {
            display: inline-flex;
            align-items: center;
            background: var(--theme-switch-bg);
            color: var(--text-main);
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 12px;
            white-space: nowrap;
            z-index: 2;
            position: relative;
        }
        .btn-action {
            background: none;
            border: none;
            cursor: pointer;
            padding: 6px;
            border-radius: 4px;
            color: var(--text-muted);
            display: inline-flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s;
            z-index: 2;
            position: relative;
        }
        .btn-action:hover {
            background: var(--theme-switch-bg);
            color: var(--text-main);
        }
        .btn-action.btn-delete:hover {
            background: #fee2e2;
            color: #ef4444;
        }
        .actions-cell { display: flex; gap: 4px; }
        
        /* Merge Styles */
        .row-merged { background-color: var(--theme-switch-bg) !important; opacity: 0.8; }
        .row-merged td.status-cell::before {
            content: '';
            position: absolute;
            left: 50%;
            top: -15px;
            width: 2px;
            height: 40px;
            border-left: 2px dashed var(--accent);
            z-index: 1;
            transform: translateX(-50%);
        }
        .row-merged .hide-on-merge { display: none !important; }
        
        .merged-message {
            display: none;
            color: var(--text-main);
            font-size: 13px;
            font-weight: 500;
            background: rgba(45, 106, 79, 0.05);
            border: 1px dashed var(--accent);
            padding: 8px 12px;
            border-radius: 6px;
            align-items: center;
            gap: 8px;
        }
        [data-theme="dark"] .merged-message { background: rgba(245, 158, 11, 0.05); }
        .row-merged .merged-message { display: flex; }
        .btn-unlink { color: var(--accent) !important; background: rgba(45, 106, 79, 0.1); }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
            position: relative;
            z-index: 2;
        }
        .status-dot.warning { background-color: #f59e0b; }
        .status-dot.success { background-color: #10b981; }
        .status-dot.merged { background-color: var(--accent); }
        
        .footer-actions {
            background: var(--theme-switch-bg);
            padding: 16px 24px;
            border-top: 1px solid var(--border-color);
            display: flex;
            justify-content: flex-end;
            gap: 12px;
        }
        
        /* Modal Styles */
        .modal-overlay {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.6);
            backdrop-filter: blur(4px);
            display: flex; align-items: center; justify-content: center;
            opacity: 0; pointer-events: none;
            transition: opacity 0.25s ease;
            z-index: 1000;
        }
        .modal-overlay.active { opacity: 1; pointer-events: auto; }
        .modal-container {
            background: var(--container-bg);
            border-radius: 12px;
            width: 90%; max-width: 600px; height: 80%; max-height: 750px;
            display: flex; flex-direction: column;
            box-shadow: var(--shadow);
            transform: scale(0.95); transition: transform 0.25s ease;
            overflow: hidden;
        }
        .modal-overlay.active .modal-container { transform: scale(1); }
        .modal-header {
            padding: 16px 20px; border-bottom: 1px solid var(--border-color);
            display: flex; justify-content: space-between; align-items: center;
        }
        .modal-header h4 { font-size: 16px; font-weight: 600; margin: 0; }
        .btn-close-modal {
            background: none; border: none; font-size: 20px; cursor: pointer;
            color: var(--text-muted);
        }
        .modal-body {
            flex: 1; padding: 24px; overflow-y: auto;
            background: var(--theme-switch-bg);
            display: flex; justify-content: center; align-items: flex-start;
        }
        .scanned-document-mock {
            background: white; width: 100%; max-width: 480px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.08);
            border-radius: 4px; padding: 40px;
            font-family: 'Courier New', Courier, monospace;
            font-size: 12px; line-height: 1.5; color: #334155;
        }"""
content = re.sub(css_old, css_new, content, flags=re.DOTALL)

# 2. Replace HTML
html_old = r"""            <!-- Таблица предпросмотра -->.*?</div>\s*</div>"""
html_new = r"""            <!-- Проверка результатов (Сплит-макет) -->
            <div class="preview-container" id="preview-container">
                <header class="preview-header" style="background:var(--bg-color); padding:14px 24px; border-bottom:1px solid var(--border-color); display:flex; justify-content:space-between; align-items:center;">
                    <h2 style="font-size:18px; margin:0;">Проверка результатов</h2>
                    <div class="file-info" style="display:flex; align-items:center; gap:12px; background:var(--drop-bg); padding:6px 14px; border-radius:6px; font-size:13px;">
                        <span class="label" style="color:var(--text-muted);">Исходный файл:</span>
                        <span class="filename" id="preview-filename" style="font-weight:600; color:var(--text-main);">...</span>
                    </div>
                </header>
                <div class="main-layout" style="display:flex; flex:1; overflow:hidden;">
                    <aside class="preview-sidebar">
                        <h3>Превью страниц</h3>
                        <div class="page-thumbnail-container" id="preview-thumbnails"></div>
                    </aside>
                    <main class="table-area">
                        <table class="doc-table" id="preview-table">
                            <thead>
                                <tr>
                                    <th style="width: 40px;"></th>
                                    <th style="width: 100px;">Страницы</th>
                                    <th style="width: 250px;">Стороны</th>
                                    <th style="width: 180px;">Тип документа</th>
                                    <th style="width: 120px;">Дата</th>
                                    <th>Итоговое имя файла</th>
                                    <th style="width: 100px; text-align: center;">Действия</th>
                                </tr>
                            </thead>
                            <tbody></tbody>
                        </table>
                    </main>
                </div>
                <footer class="footer-actions">
                    <button class="btn-outline" style="background: transparent; color: var(--text-main);" onclick="resetTable()">Отмена</button>
                    <button class="btn-primary" style="margin-top: 0; width: auto;" onclick="saveDocuments()">Утвердить и сохранить</button>
                </footer>
                
                <!-- Модальное окно просмотра документа -->
                <div class="modal-overlay" id="previewModal">
                    <div class="modal-container">
                        <div class="modal-header">
                            <h4>Просмотр страницы <span id="previewPageNum">1</span></h4>
                            <button class="btn-close-modal" onclick="closePreview()">&times;</button>
                        </div>
                        <div class="modal-body">
                            <div class="scanned-document-mock">
                                <h3 style="text-align: center; margin-bottom: 20px; font-weight: bold;" id="previewDocTitle">ДОКУМЕНТ</h3>
                                <p style="margin-bottom: 15px;">г. Москва <span style="float: right;">"__" _______ 202_ г.</span></p>
                                <p style="margin-bottom: 12px;"><b><span id="previewDocCompany">ООО "Компания"</span></b>, именуемое в дальнейшем "Сторона 1"...</p>
                                <p style="margin-bottom: 12px;">1. ПРЕДМЕТ ДОГОВОРА<br>1.1. Настоящий документ регулирует отношения сторон...</p>
                                <p style="margin-bottom: 12px;">2. СТОИМОСТЬ РАБОТ И ПОРЯДОК РАСЧЕТОВ<br>2.1. Стоимость определяется согласно договоренностям...</p>
                                <div style="margin-top: 50px; border-top: 1px dashed var(--border-color); padding-top: 10px;">
                                    <p>ПОДПИСИ СТОРОН:</p>
                                    <p style="margin-top: 15px;">От Стороны 1: _______________</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>"""
content = re.sub(html_old, html_new, content, flags=re.DOTALL)

with open('frontend/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

