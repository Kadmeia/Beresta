import re

with open('frontend/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update subtitle text to remove Tesseract
html = html.replace('Для чистых документов лучше подходит Tesseract, для\n                фото — EasyOCR.', 'Вы можете использовать встроенную нейросеть Apple Vision (работает моментально) или скачать мощную модель PaddleOCR (для кривых сканов и фото).')

# 2. Remove Tesseract block
tesseract_block = """                <label
                    style="border: 1px solid var(--border-color); padding: 16px; border-radius: 12px; cursor: pointer; display: flex; align-items: flex-start; gap: 12px; transition: var(--transition);"
                    id="ocr-label-tesseract" onclick="setOcrEngine('tesseract')">
                    <input type="radio" name="ocr_engine" value="tesseract"
                        style="margin-top: 4px; accent-color: var(--accent); transform: scale(1.2);">
                    <div>
                        <div style="font-weight: 600; font-size: 1.05rem; margin-bottom: 4px; color: var(--text-main);">
                            Tesseract (Быстрый)</div>
                        <div style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.4;">Идеален для чистых
                            документов, актов, договоров. Работает моментально.</div>
                    </div>
                </label>"""
html = html.replace(tesseract_block, "")

# 3. Modify PaddleOCR block to add download button
paddle_block_old = """                <label
                    style="border: 1px solid var(--border-color); padding: 16px; border-radius: 12px; cursor: pointer; display: flex; align-items: flex-start; gap: 12px; transition: var(--transition);"
                    id="ocr-label-paddleocr" onclick="setOcrEngine('paddleocr')">
                    <input type="radio" name="ocr_engine" value="paddleocr" checked
                        style="margin-top: 4px; accent-color: var(--accent); transform: scale(1.2);">
                    <div>
                        <div style="font-weight: 600; font-size: 1.05rem; margin-bottom: 4px; color: var(--text-main);">
                            PaddleOCR (Нейросеть)</div>
                        <div style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.4;">Читает
                            фото со смартфона, кривые сканы. Отличная скорость и точность.
                        </div>
                    </div>
                </label>"""

paddle_block_new = """                <div
                    style="border: 1px solid var(--border-color); padding: 16px; border-radius: 12px; display: flex; flex-direction: column; gap: 12px; transition: var(--transition);"
                    id="ocr-container-paddleocr">
                    <label style="cursor: pointer; display: flex; align-items: flex-start; gap: 12px;" onclick="setOcrEngine('paddleocr')">
                        <input type="radio" name="ocr_engine" value="paddleocr" id="ocr-radio-paddleocr"
                            style="margin-top: 4px; accent-color: var(--accent); transform: scale(1.2);">
                        <div>
                            <div style="font-weight: 600; font-size: 1.05rem; margin-bottom: 4px; color: var(--text-main);">
                                PaddleOCR <span style="font-size: 0.75rem; background: var(--border-color); padding: 2px 6px; border-radius: 4px; margin-left: 6px;">~150 МБ</span></div>
                            <div style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.4;">Мощная нейросеть. Читает фото со смартфона, кривые сканы. Отличная скорость и точность.</div>
                        </div>
                    </label>
                    <button id="btn-download-paddle" onclick="downloadPaddleOCR()" class="btn-outline" style="width: 100%; margin-top: 4px;">
                        Скачать (~150 МБ)
                    </button>
                    <div id="paddle-downloaded-mark" style="display: none; color: var(--accent); font-size: 0.85rem; font-weight: 500; align-items: center; gap: 6px;">
                        <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                        Модель скачана и готова
                    </div>
                </div>"""

html = html.replace(paddle_block_old, paddle_block_new)

with open('frontend/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
