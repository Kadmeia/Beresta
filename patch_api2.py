with open('backend/api.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_methods = """    def check_paddleocr(self):
        return self.docx_processor.pdf_processor.check_paddleocr_exists()

    def download_paddleocr(self):
        import threading
        def dl_task():
            success = self.docx_processor.pdf_processor.download_paddleocr(self.send_status)
            if success:
                self.send_status("Скачивание завершено. PaddleOCR готов.")
                # Force frontend to refresh
                if self.window:
                    self.window.evaluate_js('window.checkOcrStatus && window.checkOcrStatus();')
        
        t = threading.Thread(target=dl_task)
        t.start()
        return "Started"

"""

content = content.replace("    def check_model(self):", new_methods + "    def check_model(self):")

with open('backend/api.py', 'w', encoding='utf-8') as f:
    f.write(content)
