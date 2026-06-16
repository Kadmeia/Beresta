with open('frontend/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

js_code = """
        window.checkOcrStatus = function() {
            if (window.pywebview && pywebview.api) {
                pywebview.api.check_paddleocr().then(exists => {
                    const btn = document.getElementById('btn-download-paddle');
                    const mark = document.getElementById('paddle-downloaded-mark');
                    const rdo = document.getElementById('ocr-radio-paddleocr');
                    const container = document.getElementById('ocr-container-paddleocr');
                    
                    if (exists) {
                        if (btn) btn.style.display = 'none';
                        if (mark) mark.style.display = 'flex';
                        if (rdo) rdo.disabled = false;
                        if (container) container.style.opacity = '1';
                    } else {
                        if (btn) btn.style.display = 'block';
                        if (mark) mark.style.display = 'none';
                        if (rdo) {
                            rdo.disabled = true;
                            if (rdo.checked) {
                                // Fallback to applevision if paddle was checked but deleted
                                setOcrEngine('applevision');
                                document.querySelector('input[name="ocr_engine"][value="applevision"]').checked = true;
                            }
                        }
                        if (container) container.style.opacity = '0.7';
                    }
                });
            }
        };

        function downloadPaddleOCR() {
            if (window.pywebview && pywebview.api) {
                const btn = document.getElementById('btn-download-paddle');
                btn.disabled = true;
                btn.innerText = "Скачивание (см. статус сверху)...";
                pywebview.api.download_paddleocr().then(() => {
                    // Update happens via checkOcrStatus called from python
                });
                closeOcrManager();
            }
        }
"""

# Insert JS code before window.addEventListener("pywebviewready"
html = html.replace('window.addEventListener("pywebviewready"', js_code + '\n        window.addEventListener("pywebviewready"')

# Also call checkOcrStatus on pywebviewready
html = html.replace('            loadSettings();', '            loadSettings();\n            window.checkOcrStatus();')

# Default applevision since tesseract is gone
html = html.replace("let currentOcrEngine = 'tesseract';", "let currentOcrEngine = 'applevision';")

with open('frontend/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
