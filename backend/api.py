import os
import webview
import json
from .model_manager import ModelManager
from .pdf_processor import PDFProcessor
from .llm_handler import LLMHandler
from .docx_processor import DocxProcessor

class Api:
    def __init__(self):
        self.model_manager = ModelManager()
        self.pdf_processor = PDFProcessor()
        self.docx_processor = DocxProcessor()
        self.llm_handler = None
        self.window = None
        self.is_processing = False


    def _lock(func):
        def wrapper(self, *args, **kwargs):
            if self.is_processing:
                return {"error": "Система уже обрабатывает другой запрос. Дождитесь завершения."} if func.__name__ == "process_files" else [] if func.__name__ == "save_documents" else False
            self.is_processing = True
            try:
                return func(self, *args, **kwargs)
            finally:
                self.is_processing = False
        return wrapper

    def set_window(self, window):
        self.window = window

    def send_status(self, message):
        """Sends a status message to the frontend"""
        if self.window:
            safe_msg = json.dumps(message)
            self.window.evaluate_js(f"window.updateStatus({safe_msg})")

    def resize_window(self, width, height):
        """Resizes the window dynamically"""
        if self.window:
            try:
                self.window.resize(width, height)
            except Exception as e:
                print(f"Error resizing window: {e}")

    def open_file_dialog(self):
        import webview
        if self.window:
            file_types = ('Документы (*.pdf;*.docx)', 'Все файлы (*.*)')
            result = self.window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True, file_types=file_types)
            return result if result else []
        return []
    def open_folder_dialog(self):
        import webview
        if self.window:
            result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
            return result[0] if result else None
        return None

    def save_dropped_file(self, filename, base64_data):
        """Saves a dragged-and-dropped file to a temporary location and returns the path."""
        import tempfile
        import base64
        import os
        
        try:
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, filename)
            
            if "," in base64_data:
                base64_data = base64_data.split(",")[1]
                
            file_data = base64.b64decode(base64_data)
            
            with open(file_path, 'wb') as f:
                f.write(file_data)
                
            return file_path
        except Exception as e:
            print(f"Error saving dropped file: {e}")
            return None

    def check_paddleocr(self):
        return self.pdf_processor.check_paddleocr_exists()

    def check_tesseract(self):
        return self.pdf_processor.check_tesseract_exists()

    def download_tesseract(self):
        import threading
        def dl_task():
            success = self.pdf_processor.download_tesseract(self.send_status)
            if success:
                self.send_status("Скачивание завершено. Tesseract готов.")
                if self.window:
                    self.window.evaluate_js('window.checkOcrStatus && window.checkOcrStatus();')
                    self.window.evaluate_js("setTimeout(() => { document.getElementById('progress-container').style.display = 'none'; document.getElementById('action-btn').style.display = 'block'; }, 2000);")
            else:
                if self.window:
                    self.window.evaluate_js("setTimeout(() => { document.getElementById('progress-container').style.display = 'none'; document.getElementById('action-btn').style.display = 'block'; }, 4000);")
        
        t = threading.Thread(target=dl_task)
        t.start()
        return "Started"

    def download_paddleocr(self):
        import threading
        def dl_task():
            success = self.pdf_processor.download_paddleocr(self.send_status)
            if success:
                self.send_status("Скачивание завершено. PaddleOCR готов.")
                # Force frontend to refresh
                if self.window:
                    self.window.evaluate_js('window.checkOcrStatus && window.checkOcrStatus();')
                    self.window.evaluate_js("setTimeout(() => { document.getElementById('progress-container').style.display = 'none'; document.getElementById('action-btn').style.display = 'block'; }, 2000);")
            else:
                if self.window:
                    self.window.evaluate_js("setTimeout(() => { document.getElementById('progress-container').style.display = 'none'; document.getElementById('action-btn').style.display = 'block'; }, 4000);")

        t = threading.Thread(target=dl_task)
        t.start()
        return "Started"

    def check_model(self):
        """Called by frontend on startup. Returns true if ANY model exists."""
        active = self.model_manager.get_active_model_type()
        return self.model_manager.check_model_exists(active)

    def get_models_status(self):
        active = self.model_manager.get_active_model_type()
        status = {}
        for m_type in self.model_manager.models:
            status[m_type] = {
                "installed": self.model_manager.check_model_exists(m_type),
                "active": m_type == active
            }
        return status
        
    def set_active_model(self, model_type):
        if model_type in self.model_manager.models and self.model_manager.check_model_exists(model_type):
            self.model_manager.set_active_model_type(model_type)
            if self.llm_handler:
                self.llm_handler.unload_model()
                self.llm_handler = None
            return True
        return False
        
    @_lock
    def delete_model(self, model_type):
        import os
        try:
            active = self.model_manager.get_active_model_type()
            path = self.model_manager.get_model_path(model_type)
            
            # Free memory and file handles if deleting active model
            if model_type == active and hasattr(self, 'llm_handler') and self.llm_handler:
                self.llm_handler.unload_model()
                self.llm_handler = None
            
            if os.path.exists(path):
                os.remove(path)
            
            # If we deleted the active model, fallback to another if exists
            if model_type == active:
                self.model_manager.get_active_model_type() # this triggers fallback in manager
                
            return True
        except Exception as e:
            print(f"Error deleting model: {e}")
            return False

    def get_ocr_engine(self):
        """Returns the currently active OCR engine."""
        return self.pdf_processor.ocr_engine

    def get_available_ocr_engines(self):
        """Returns available OCR engines based on OS."""
        import sys
        engines = ['tesseract', 'paddleocr']
        if sys.platform == 'darwin':
            engines.append('applevision')
        return engines

    def get_os_info(self):
        """Returns the OS platform identifier."""
        import sys
        return sys.platform

    def set_ocr_engine(self, engine):
        """Sets the active OCR engine."""
        import sys
        valid_engines = ['tesseract', 'paddleocr']
        if sys.platform == 'darwin':
            valid_engines.append('applevision')
            
        if engine in valid_engines:
            self.pdf_processor.ocr_engine = engine
            return True
        return False

    @_lock
    def download_model(self, model_type="fast"):
        """Starts model download"""
        def progress_callback(msg):
            self.send_status(msg)
            
        self.model_manager.download_model(model_type, progress_callback)
        return "Started"

    @_lock
    def process_files(self, file_paths, mode="split"):
        """
        Main pipeline for processing PDFs.
        Returns a list of JSON objects for the preview table.
        """
        if not self.llm_handler:
            active = self.model_manager.get_active_model_type()
            if not self.model_manager.check_model_exists(active):
                return {"error": "Модель не найдена. Пожалуйста, скачайте модель."}
            self.llm_handler = LLMHandler(self.model_manager.get_model_path(active))

        import re
        def is_new_document_start(text):
            lines = text[:1500].split('\n')
            keywords = ['ДОГОВОР', 'АКТ', 'ПРИЛОЖЕНИЕ', 'СОГЛАШЕНИЕ', 'СЧЕТ', 'УПД', 'СПРАВКА', 'ДОВЕРЕННОСТЬ', 'ЗАЯВЛЕНИЕ', 'ПРИКАЗ', 'КОНТРАКТ']
            
            # Создаем регулярные выражения для каждого ключевого слова
            # Разрешаем пробелы между буквами (П Р И Л О Ж Е Н И Е)
            # Требуем, чтобы слово не было частью другого слова (например, ДОГОВОРУ)
            kw_patterns = {}
            for kw in keywords:
                spaced_kw = r'\s*'.join(list(kw))
                pattern = r'(?:^|[^А-ЯЁA-Z])(' + spaced_kw + r')(?:[^А-ЯЁA-Z]|$)'
                kw_patterns[kw] = re.compile(pattern)

            for i, line in enumerate(lines):
                line = line.strip().upper()
                if not line:
                    continue
                
                word_count = len(line.split())
                
                for kw, pattern in kw_patterns.items():
                    match = pattern.search(line)
                    if match:
                        # 1. Если строка короткая (до 8 слов) - это заголовок
                        if word_count <= 8:
                            return True
                        # 2. Если ключевое слово находится в самом начале строки (с учетом нумерации "1. ")
                        if match.start(1) <= 5 and word_count <= 20:
                            return True
            return False

        results = []
        for path in file_paths:
            self.send_status(f"Анализируем грамоту: {os.path.basename(path)}...")
            try:
                is_docx = path.lower().endswith('.docx')
                if is_docx:
                    pages_text = self.docx_processor.extract_text(path, self.send_status)
                else:
                    pages_text = self.pdf_processor.extract_text(path, self.send_status)
                
                current_doc = None
                
                for p in pages_text:
                    page_num = p['page_num']
                    text = p['text'][:1500]
                    
                    if mode == "rename":
                        is_new = False
                    else:
                        is_new = is_new_document_start(text)
                    
                    if is_new or current_doc is None:
                        retries = 0
                        max_retries = 2
                        
                        # Initial text cleanup for common OCR artifacts
                        text = text.replace('N@', '№').replace('N?', '№')
                        self.send_status(f"Расшифровка нейросетью (стр. {page_num})...")
                        analysis = self.llm_handler.analyze_text(text, page_num, retry=retries)
                        
                        while (analysis.get('confidence_score', 0) < 85 or analysis.get('short_name') == 'Неизвестный документ') and retries < max_retries:
                            retries += 1
                            self.send_status(f"Перепроверка ИИ (стр. {page_num}), попытка {retries}...")
                            
                            # Если первая попытка провалилась, возможно текстовый слой PDF содержит мусор (частая проблема сканов).
                            # Принудительно запускаем визуальный OCR для этой страницы.
                            if retries == 1:
                                self.send_status(f"Очистка текста OCR (стр. {page_num})...")
                                try:
                                    ocr_text = self.pdf_processor.force_ocr_page(path, page_num)
                                    # Заменяем мусорный текст на распознанный
                                    if len(ocr_text.strip()) > 20:
                                        # Fix common OCR artifacts
                                        ocr_text = ocr_text.replace('N@', '№').replace('N?', '№')
                                        text = ocr_text[:1500]
                                        p['text'] = ocr_text
                                except Exception as e:
                                    print(f"Force OCR failed: {e}")
                            
                            expanded_text = p['text'][:1500 + (retries * 500)]
                            # Fix common OCR artifacts before LLM
                            expanded_text = expanded_text.replace('N@', '№').replace('N?', '№')
                            analysis = self.llm_handler.analyze_text(expanded_text, page_num, retry=retries)

                        b64_image = ""
                        if not is_docx:
                            try:
                                import fitz
                                import base64
                                tmp_doc = fitz.open(path)
                                tmp_page = tmp_doc[page_num - 1]
                                pix = tmp_page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                                img_data = pix.tobytes("jpeg", 80)
                                b64_image = base64.b64encode(img_data).decode("utf-8")
                                tmp_doc.close()
                            except Exception as e:
                                print(f"Error generating preview image: {e}")

                        # Закрываем предыдущий документ
                        if current_doc:
                            current_doc['end_page'] = page_num - 1
                            results.append(current_doc)
                            
                        # Начинаем новый документ
                        final_confidence = analysis.get('confidence_score', 0) >= 85
                        current_doc = {
                            "start_page": page_num,
                            "end_page": page_num,
                            "parties": analysis.get('parties', ''),
                            "short_name": analysis.get('short_name', 'Документ'),
                            "full_name": analysis.get('full_name', f'Документ со стр. {page_num}'),
                            "date": analysis.get('date', ''),
                            "confidence": final_confidence,
                            "original_file": path,
                            "text": text,
                            "image_b64": b64_image
                        }
                    else:
                        # Продолжение документа
                        if current_doc:
                            current_doc['end_page'] = page_num
                            
                # Добавляем последний документ
                if current_doc:
                    current_doc['end_page'] = pages_text[-1]['page_num'] if pages_text else current_doc['end_page']
                    results.append(current_doc)
                    
            except Exception as e:
                self.send_status(f"Ошибка при обработке {os.path.basename(path)}: {e}")

        self.send_status("Ожидание проверки...")
        return results

    @_lock
    def save_documents(self, preview_data, output_dir):
        """
        Takes the edited preview data from frontend and splits/saves PDFs or DOCXs.
        """
        import re
        saved_files = []
        for item in preview_data:
            try:
                original_path = item.get('original_file')
                start_page = int(item.get('start_page', 1))
                end_page = int(item.get('end_page', 1))
                
                # Construct new name based on frontend settings
                # We assume frontend passes the finalized 'new_name' field
                new_name = item.get('new_name')
                if not new_name:
                    # fallback
                    new_name = f"{item.get('short_name', 'Документ')} {item.get('date', '')}".strip()
                    
                # Очистка имени файла
                new_name = re.sub(r'[\\/*?:"<>|]', "", new_name)
                new_name = new_name.replace("Ошибка", "").strip()
                if not new_name:
                    new_name = f"Документ_стр_{start_page}"
                
                current_output_dir = output_dir.strip() if output_dir else os.path.dirname(original_path)
                os.makedirs(current_output_dir, exist_ok=True)
                
                self.send_status(f"Сохранение: {new_name}...")
                
                if original_path.lower().endswith('.docx'):
                    # Save docx
                    final_path = self.docx_processor.split_and_save(
                        original_path, 
                        start_page,
                        end_page,
                        new_name, 
                        current_output_dir
                    )
                else:
                    # Save pdf
                    final_path = self.pdf_processor.split_and_save(
                        original_path, 
                        start_page, 
                        end_page, 
                        new_name, 
                        current_output_dir
                    )
                saved_files.append(final_path)
            except Exception as e:
                error_msg = f"Ошибка сохранения в {current_output_dir}: {e}"
                print(error_msg)
                raise ValueError(error_msg)
                
        self.send_status("Грамоты успешно сохранены!")
        return saved_files
