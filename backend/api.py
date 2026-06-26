import os
import webview
import json
import re
from .model_manager import ModelManager
from .pdf_processor import PDFProcessor
from .llm_handler import LLMHandler
from .docx_processor import DocxProcessor
from .layout_processor import LayoutProcessor

def is_new_document_start(text):
    print("[DEBUG] is_new_document_start: начало")
    lines = text[:1500].split('\n')
    keywords = [
        'ДОГОВОР', 'АКТ', 'ПРИЛОЖЕНИЕ', 'СОГЛАШЕНИЕ', 'СЧЕТ', 'УПД', 
        'СПРАВКА', 'ДОВЕРЕННОСТЬ', 'ЗАЯВЛЕНИЕ', 'ПРИКАЗ', 'КОНТРАКТ',
        'НАКЛАДНАЯ', 'РЕШЕНИЕ', 'ЗАКЛЮЧЕНИЕ', 'ПРОТОКОЛ', 'ВЫПИСКА', 'ПАСПОРТ', 'ЧЕК'
    ]
    
    kw_patterns = {}
    for kw in keywords:
        spaced_kw = r'\s*'.join(list(kw))
        pattern = r'\b(' + spaced_kw + r')'
        kw_patterns[kw] = re.compile(pattern)

    print(f"[DEBUG] is_new_document_start: подготовлено {len(lines)} строк для проверки")
    for i, line in enumerate(lines):
        line = line.strip().upper()
        if not line:
            continue
        
        word_count = len(line.split())
        print(f"[DEBUG] Проверка строки {i}: '{line[:50]}...' (слов: {word_count})")
        
        for kw, pattern in kw_patterns.items():
            match = pattern.search(line)
            if match:
                print(f"[DEBUG] Найдено ключевое слово: {kw}")
                if word_count <= 10:
                    return True
                if match.start(1) <= 15 and word_count <= 25:
                    return True
                    
    print("[DEBUG] is_new_document_start: конец (False)")
    return False

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

class Api:
    def __init__(self):
        self.model_manager = ModelManager()
        self.pdf_processor = PDFProcessor()
        self.docx_processor = DocxProcessor()
        self.layout_processor = LayoutProcessor()
        self.llm_handler = None
        self.window = None
        self.is_processing = False

        self._load_ocr_engine()

    def _load_ocr_engine(self):
        import os, json
        config_path = self.model_manager.config_path
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    engine = config.get("ocr_engine")
                    if engine:
                        self.set_ocr_engine(engine)
            except Exception as e:
                print(f"Error loading OCR engine from config: {e}")


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
            file_types = ('Документы и сканы (*.pdf;*.docx;*.png;*.jpg;*.jpeg)', 'Все файлы (*.*)')
            result = self.window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True, file_types=file_types)
            return result if result else []
        return []

    def open_folder_dialog(self):
        import webview
        if self.window:
            result = self.window.create_file_dialog(webview.FileDialog.FOLDER)
            return result[0] if result else ""
        return ""

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

    def check_layout_engine(self, engine):
        return self.layout_processor.check_engine(engine)

    def download_layout_engine(self, engine):
        def dl_task():
            def custom_cb(msg):
                print(f"LAYOUT_STATUS: {msg}")
                if self.window:
                    safe_msg = msg.replace('`', "'").replace('\\', '\\\\')
                    self.window.evaluate_js(f"window.updateLayoutDownloadStatus && window.updateLayoutDownloadStatus(`{safe_msg}`)")
                    
            try:
                success = self.layout_processor.download_engine(engine, custom_cb)
                if self.window:
                    if success:
                        self.window.evaluate_js(f"window.layoutDownloadComplete && window.layoutDownloadComplete(true, '{engine}')")
                    else:
                        self.window.evaluate_js(f"window.layoutDownloadComplete && window.layoutDownloadComplete(false, '{engine}')")
            except Exception as e:
                print(f"Error in layout download: {e}")
                if self.window:
                    self.window.evaluate_js(f"window.layoutDownloadComplete && window.layoutDownloadComplete(false, '{engine}')")

        import threading
        t = threading.Thread(target=dl_task, daemon=True)
        t.start()
        return "Started"

    def check_model(self):
        """Called by frontend on startup. Returns true if active model and engine exist."""
        active = self.model_manager.get_active_model_type()
        if active == "smolagents_local":
            return True
        if hasattr(self.model_manager, 'gemini_models') and active in self.model_manager.gemini_models:
            return True
        model_exists = self.model_manager.check_model_exists(active)
        server_exists = self.model_manager.check_llama_server_exists()
        return model_exists and server_exists

    def get_models_status(self):
        active = self.model_manager.get_active_model_type()
        server_exists = self.model_manager.check_llama_server_exists()
        status = {}
        for m_type in self.model_manager.models:
            status[m_type] = {
                "installed": self.model_manager.check_model_exists(m_type) and server_exists,
                "active": m_type == active
            }
        if hasattr(self.model_manager, 'gemini_models'):
            for m_type in self.model_manager.gemini_models:
                status[m_type] = {
                    "installed": True,
                    "active": m_type == active
                }
        status["smolagents_local"] = {
            "installed": True,
            "active": active == "smolagents_local"
        }
        return status
        
    def get_gemini_config(self):
        return self.model_manager.get_gemini_config()
        
    def save_gemini_config(self, api_key, model):
        self.model_manager.set_gemini_config(api_key, model)
        return True

    def get_ollama_config(self):
        return self.model_manager.get_ollama_config()

    def save_ollama_config(self, model, base_url):
        self.model_manager.set_ollama_config(model, base_url)
        return True
        
    def set_active_model(self, model_type):
        if hasattr(self.model_manager, 'gemini_models') and model_type in self.model_manager.gemini_models:
            self.model_manager.set_active_model_type(model_type)
            if self.llm_handler:
                self.llm_handler.unload_model()
                self.llm_handler = None
            return True
        if model_type == "smolagents_local":
            self.model_manager.set_active_model_type(model_type)
            if self.llm_handler:
                self.llm_handler.unload_model()
                self.llm_handler = None
            return True
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
        engines = ['paddleocr', 'docling', 'tesseract']
        if sys.platform == 'darwin':
            engines.append('applevision')
        return engines

    def get_os_info(self):
        """Returns the OS platform identifier."""
        import sys
        return sys.platform

    def set_ocr_engine(self, engine):
        """Sets the active OCR engine."""
        import sys, os, json
        valid_engines = ['paddleocr', 'docling', 'tesseract']
        if sys.platform == 'darwin':
            valid_engines.append('applevision')
            
        if engine in valid_engines:
            self.pdf_processor.ocr_engine = engine
            # Save to config
            config_path = self.model_manager.config_path
            config = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                except Exception:
                    pass
            config["ocr_engine"] = engine
            try:
                with open(config_path, 'w') as f:
                    json.dump(config, f)
            except Exception as e:
                print(f"Error saving OCR engine to config: {e}")
            return True
        return False

    @_lock
    def download_model(self, model_type="fast"):
        """Starts model download and llama-server download"""
        def progress_callback(msg):
            self.send_status(msg)
            
        try:
            if not self.model_manager.check_llama_server_exists():
                self.send_status("Подготовка движка: скачивание llama-server...")
                success = self.model_manager.download_llama_server(progress_callback)
                if not success:
                    self.send_status("Ошибка при скачивании движка llama-server. Загрузка модели отменена.")
                    return "Error"
            
            self.send_status(f"Начинаем скачивание файлов нейросети {model_type}...")
            self.model_manager.download_model(model_type, progress_callback)
            
            if self.window:
                self.window.evaluate_js("window.checkModelStatus && window.checkModelStatus();")
            return "Started"
        except Exception as e:
            self.send_status(f"Ошибка установки компонентов: {str(e)}")
            return f"Error: {e}"

    @_lock
    def process_files(self, file_paths, mode="split", extract_settings=None):
        """
        Main pipeline for processing PDFs.
        Returns a list of JSON objects for the preview table.
        """
        if extract_settings is None:
            extract_settings = {"split": True, "use_ai": True}

        # Step 1: Run OCR/text extraction on all files and save page texts in memory
        all_files_pages = []
        total_files = len(file_paths)
        for idx, path in enumerate(file_paths, 1):
            prefix = f"[{idx}/{total_files}]"
            self.send_status(f"{prefix} Извлекаем текст: {os.path.basename(path)}...")
            
            def status_wrapper(msg):
                self.send_status(f"{prefix} {msg}")

            try:
                is_docx = path.lower().endswith('.docx')
                engine = self.pdf_processor.ocr_engine
                
                if engine in ['docling', 'ppstructure'] and not is_docx:
                    pages_text = self.layout_processor.extract_text(path, engine, status_wrapper)
                else:
                    if is_docx:
                        pages_text = self.docx_processor.extract_text(path, status_wrapper)
                    else:
                        pages_text = self.pdf_processor.extract_text(path, status_wrapper)
                        
                all_files_pages.append({
                    "path": path,
                    "is_docx": is_docx,
                    "pages_text": pages_text
                })
            except Exception as e:
                import traceback
                print(f"Exception during OCR extraction for {path}: {e}")
                traceback.print_exc()
                self.send_status(f"Ошибка извлечения текста {os.path.basename(path)}: {e}")
                
        if not all_files_pages:
            return [{"error": "Не удалось извлечь текст ни из одного документа. Проверьте консоль для подробностей."}]
                
        # Step 2: Unload OCR models from RAM
        self.send_status("Освобождаем память от OCR движка...")
        try:
            self.pdf_processor.unload_ocr()
            self.layout_processor.unload_engine()
        except Exception as e:
            print(f"Error unloading OCR: {e}")

        # Step 3: Run LLM-based analysis page-by-page
        active = self.model_manager.get_active_model_type()
        is_gemini = hasattr(self.model_manager, 'gemini_models') and active in self.model_manager.gemini_models

        if is_gemini:
            return self.process_documents_bulk_gemini(all_files_pages, mode, extract_settings)

        if active == "smolagents_local":
            return self.process_documents_smolagents(all_files_pages, mode, extract_settings)

        if not self.llm_handler:
            if not self.model_manager.check_model_exists(active):
                return {"error": "Модель не найдена. Пожалуйста, скачайте модель."}
            self.llm_handler = LLMHandler(self.model_manager.get_model_path(active))

        results = []
        total_files_analysis = len(all_files_pages)
        total_pages_all_files = sum(len(fd.get("pages_text", [])) for fd in all_files_pages)
        current_page_overall = 0
        
        for f_idx, file_data in enumerate(all_files_pages, 1):
            path = file_data["path"]
            is_docx = file_data["is_docx"]
            pages_text = file_data["pages_text"]
            
            prefix = f"[{f_idx}/{total_files_analysis}]"
            
            # Show a generic starting percent for the document if no pages yet
            start_percent = int((current_page_overall / max(total_pages_all_files, 1)) * 95)
            self.send_status(f"{prefix} Анализируем грамоту: {os.path.basename(path)}... {start_percent}%")
            print(f"\n[INFO] Начат анализ документа: {path}")
            try:
                current_doc = None
                
                for p in pages_text:
                    current_page_overall += 1
                    percent = int((current_page_overall / max(total_pages_all_files, 1)) * 95)
                    page_num = p['page_num']
                    text = p['text'][:3000]
                    
                    print(f"[INFO] Обработка страницы {page_num}/{len(pages_text)}...")
                    
                    is_candidate = False
                    if mode == "rename":
                        is_new = False
                    elif mode == "extract":
                        is_candidate = extract_settings.get('split', True) and is_new_document_start(text)
                        is_new = is_candidate and self.llm_handler.is_new_document(
                            text, page_num,
                            progress_callback=lambda tokens: self.send_status(f"{prefix} Проверка границ документа (стр. {page_num})... {percent}% ({tokens} токенов)")
                        )
                    else:
                        is_candidate = is_new_document_start(text)
                        is_new = is_candidate and self.llm_handler.is_new_document(
                            text, page_num,
                            progress_callback=lambda tokens: self.send_status(f"{prefix} Проверка границ документа (стр. {page_num})... {percent}% ({tokens} токенов)")
                        )
                    
                    print(f"DEBUG PIPELINE: page_num={page_num}, is_candidate={is_candidate}, is_new={is_new}, text_start={repr(text[:200])}")
                    
                    if is_new or current_doc is None:
                        retries = 0
                        max_retries = 2
                        
                        text = text.replace('N@', '№').replace('N?', '№')
                        
                        if mode == "extract" and extract_settings.get("use_ai", True):
                            print(f"[INFO] Запуск ИИ коррекции текста для страницы {page_num}...")
                            self.send_status(f"{prefix} ИИ коррекция текста (стр. {page_num})... {percent}%")
                            proofread_text = self.llm_handler.proofread_text(
                                p['text'],
                                progress_callback=lambda tokens: self.send_status(f"{prefix} ИИ коррекция (стр. {page_num})... {percent}% (чтение: {tokens} токенов)")
                            )
                            text = proofread_text[:3000]
                            p['text'] = proofread_text
                        
                        print(f"[INFO] Запуск извлечения реквизитов (analyze_text) для страницы {page_num}...")
                        self.send_status(f"{prefix} Определение реквизитов (стр. {page_num})... {percent}%")
                        analysis = self.llm_handler.analyze_text(
                            text, page_num, retry=retries,
                            progress_callback=lambda tokens: self.send_status(f"{prefix} Анализ ИИ (стр. {page_num})... {percent}% (обработано {tokens} токенов)")
                        )
                        print(f"[INFO] Результат анализа: {analysis}")
                        
                        while (analysis.get('short_name') == 'Документ' or not analysis.get('date') or analysis.get('date') == '-') and retries < max_retries:
                            retries += 1
                            self.send_status(f"{prefix} Перепроверка ИИ (стр. {page_num}), попытка {retries}... {percent}%")
                            
                            if retries == 1:
                                self.send_status(f"{prefix} Очистка текста OCR (стр. {page_num})... {percent}%")
                                try:
                                    ocr_text = self.pdf_processor.force_ocr_page(path, page_num)
                                    if len(ocr_text.strip()) > 20:
                                        ocr_text = ocr_text.replace('N@', '№').replace('N?', '№')
                                        text = ocr_text[:3000]
                                        p['text'] = ocr_text
                                    else:
                                        print("Force OCR returned empty/short text, keeping original text")
                                except Exception as e:
                                    print(f"Force OCR failed: {e}")
                            
                            analysis = self.llm_handler.analyze_text(
                                text, page_num, retry=retries,
                                progress_callback=lambda tokens: self.send_status(f"{prefix} Перепроверка ИИ (стр. {page_num}), попытка {retries}... {percent}% ({tokens} токенов)")
                            )

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

                        if current_doc:
                            current_doc['end_page'] = page_num - 1
                            results.append(current_doc)
                            
                        final_confidence = (analysis.get('short_name') != 'Документ' and analysis.get('date') not in [None, '', '-'])
                        current_doc = {
                            "start_page": page_num,
                            "end_page": page_num,
                            "actual_page_count": 1,
                            "parties": analysis.get('parties', ''),
                            "short_name": analysis.get('short_name', 'Документ'),
                            "full_name": analysis.get('full_name', f'Документ со стр. {page_num}'),
                            "date": analysis.get('date', ''),
                            "confidence": final_confidence,
                            "original_file": path,
                            "text": p['text'],
                            "image_b64": b64_image
                        }
                    else:
                        if current_doc:
                            current_doc['end_page'] = page_num
                            current_doc['actual_page_count'] = current_doc.get('actual_page_count', 0) + 1
                            if mode == "extract":
                                if extract_settings.get("use_ai", True):
                                    self.send_status(f"ИИ коррекция текста (стр. {page_num})... {percent}%")
                                    proofread_text = self.llm_handler.proofread_text(
                                        p['text'],
                                        progress_callback=lambda tokens: self.send_status(f"ИИ коррекция (стр. {page_num})... {percent}% (чтение: {tokens} токенов)")
                                    )
                                    p['text'] = proofread_text
                                current_doc['text'] += '\n\n' + p['text']
                            
                if current_doc:
                    current_doc['end_page'] = pages_text[-1]['page_num'] if pages_text else current_doc['end_page']
                    results.append(current_doc)
                    
            except Exception as e:
                import traceback
                print(f"[ERROR] Exception during analysis loop for {path}: {e}")
                traceback.print_exc()
                self.send_status(f"Ошибка при обработке {os.path.basename(path)}: {e}")

        self.send_status("Ожидание проверки... 100%")
        return results

    def process_documents_smolagents(self, all_files_pages, mode, extract_settings):
        from backend.smolagents_workflow import SmolAgentsWorkflow
        
        ollama_config = self.model_manager.get_ollama_config()
        results = []
        
        total_files = len(all_files_pages)
        for f_idx, file_data in enumerate(all_files_pages, 1):
            path = file_data["path"]
            is_docx = file_data["is_docx"]
            pages_text = file_data["pages_text"]
            
            prefix = f"[{f_idx}/{total_files}]"
            self.send_status(f"{prefix} Запуск SmolAgents для {os.path.basename(path)}...")
            
            try:
                workflow = SmolAgentsWorkflow(
                    file_path=path,
                    pages_text=pages_text,
                    mode=mode,
                    extract_settings=extract_settings,
                    ollama_config=ollama_config,
                    status_callback=lambda msg: self.send_status(f"{prefix} {msg}")
                )
                file_results = workflow.run()
                results.extend(file_results)
            except Exception as e:
                self.send_status(f"{prefix} Ошибка SmolAgents: {e}")
                print(f"SmolAgents error processing file {path}: {e}")
                
        self.send_status("Ожидание проверки...")
        return results

    def process_documents_bulk_gemini(self, all_files_pages, mode, extract_settings):
        import uuid
        active_model = self.model_manager.get_active_model_type()
        gemini_config = self.model_manager.get_gemini_config()
        if not gemini_config.get("api_key"):
            return {"error": "API ключ Gemini не настроен. Пожалуйста, введите его в настройках."}
            
        try:
            from backend.llm_handler import GeminiHandler
            gemini_handler = GeminiHandler(gemini_config["api_key"], active_model)
        except Exception as e:
            return {"error": f"Ошибка инициализации Gemini: {e}"}

        documents_to_analyze = []

        total_files = len(all_files_pages)
        for f_idx, file_data in enumerate(all_files_pages, 1):
            path = file_data["path"]
            is_docx = file_data["is_docx"]
            pages_text = file_data["pages_text"]
            
            prefix = f"[{f_idx}/{total_files}]"
            self.send_status(f"{prefix} Формируем блоки для Gemini: {os.path.basename(path)}...")
            
            current_doc = None
            for p in pages_text:
                page_num = p['page_num']
                text = p['text'][:3000]
                
                if mode == "rename":
                    is_new = False
                else:
                    is_candidate = extract_settings.get('split', True) if mode == "extract" else True
                    is_new = is_candidate and is_new_document_start(text)
                
                if is_new or current_doc is None:
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
                            pass
                            
                    if current_doc:
                        current_doc['end_page'] = page_num - 1
                        documents_to_analyze.append(current_doc)
                        
                    current_doc = {
                        "doc_id": str(uuid.uuid4()),
                        "start_page": page_num,
                        "end_page": page_num,
                        "actual_page_count": 1,
                        "is_docx": is_docx,
                        "original_file": path,
                        "text": p['text'],
                        "image_b64": b64_image,
                        "analysis_text": text
                    }
                else:
                    if current_doc:
                        current_doc['end_page'] = page_num
                        current_doc['actual_page_count'] += 1
                        if mode == "extract":
                            current_doc['text'] += '\n\n' + p['text']
            
            if current_doc:
                current_doc['end_page'] = pages_text[-1]['page_num'] if pages_text else current_doc['end_page']
                documents_to_analyze.append(current_doc)

        self.send_status("Gemini API: Анализ документов...")
        batch_size = 20
        total_batches = (len(documents_to_analyze) + batch_size - 1) // batch_size
        gemini_results = {}
        try:
            for i in range(0, len(documents_to_analyze), batch_size):
                batch_idx = (i // batch_size) + 1
                self.send_status(f"Gemini API: Анализ документов (пакет {batch_idx} из {total_batches})...")
                batch = documents_to_analyze[i:i+batch_size]
                batch_input = [{"doc_id": item["doc_id"], "text": item["analysis_text"]} for item in batch]
                res_list = gemini_handler.analyze_documents_bulk(batch_input)
                for res in res_list:
                    gemini_results[res.get("doc_id")] = res
        except Exception as e:
            print(f"Error during bulk Gemini processing: {e}")
            return {"error": f"Ошибка Gemini API: {str(e)}"}

        results = []
        from backend.llm_handler import format_parties, clean_doc_type, clean_doc_date

        for item in documents_to_analyze:
            d_id = item["doc_id"]
            analysis = gemini_results.get(d_id, {
                "parties": "-", "doc_type": "Документ", "number": "-", "date": "-"
            })
            
            raw_type = clean_doc_type(analysis.get("doc_type", "Документ"))
            doc_number = analysis.get("number", "-")
            clean_date = clean_doc_date(analysis.get("date", "-"), item["text"])
            parties = format_parties(analysis.get("parties", "-"))
            
            full_parts = []
            full_type = raw_type
            full_parts.append(full_type)
            if doc_number and doc_number != "-":
                clean_num = doc_number.replace("№", "").replace("номер", "").replace("No", "").strip()
                if clean_num:
                    full_parts.append(f"№{clean_num}")
            if clean_date and clean_date != "-":
                full_parts.append(f"от {clean_date}")
            full_name = " ".join(full_parts)

            doc_item = {
                "original_file": item["original_file"],
                "start_page": item["start_page"],
                "end_page": item["end_page"],
                "actual_page_count": item["actual_page_count"],
                "is_docx": item["is_docx"],
                "parties": parties,
                "short_name": raw_type,
                "full_name": full_name,
                "date": clean_date,
                "confidence": True,
                "isMerged": False,
                "isActive": True,
                "isManualEdit": False,
                "new_name": "",
                "text": item["text"],
                "image_b64": item["image_b64"]
            }
            results.append(doc_item)
            
        return results

    @_lock
    def save_documents(self, preview_data, output_dir, mode="split", export_formats=None):
        """
        Takes the edited preview data from frontend and splits/saves PDFs or DOCXs.
        """
        import re
        if export_formats is None:
            export_formats = ["docx"]
        elif isinstance(export_formats, str):
            export_formats = [export_formats]
        
        saved_files = []
        for item in preview_data:
            try:
                original_path = item.get('original_file')
                start_page = int(item.get('start_page', 1))
                end_page = int(item.get('end_page', 1))
                
                # Construct new name based on frontend settings
                # We assume frontend passes the finalized 'new_name' field
                new_name = item.get('new_name')
                if new_name:
                    new_name = re.sub(r'(?i)\.(pdf|docx)$', '', new_name)
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
                
                if mode == "extract":
                    for fmt in export_formats:
                        if fmt == "docx":
                            final_path = self.docx_processor.create_docx_from_text(
                                item.get('text', ''),
                                new_name,
                                current_output_dir
                            )
                        elif fmt == "md":
                            final_path = os.path.join(current_output_dir, new_name.replace('.docx', '').replace('.pdf', '') + '.md')
                            with open(final_path, 'w', encoding='utf-8') as f:
                                f.write(item.get('text', ''))
                        elif fmt == "txt":
                            final_path = os.path.join(current_output_dir, new_name.replace('.docx', '').replace('.pdf', '') + '.txt')
                            with open(final_path, 'w', encoding='utf-8') as f:
                                f.write(item.get('text', ''))
                elif original_path.lower().endswith('.docx'):
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
                error_msg = f"{e}"
                print(error_msg)
                raise ValueError(error_msg)
                
        self.send_status("Грамоты успешно сохранены!")
        return saved_files

    def get_page_image(self, file_path, page_num):
        """Generates a base64 preview image for a specific page of a PDF."""
        import base64
        import fitz
        try:
            if not os.path.exists(file_path):
                return ""
            doc = fitz.open(file_path)
            if page_num < 1 or page_num > len(doc):
                doc.close()
                return ""
            page = doc[page_num - 1]
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            img_data = pix.tobytes("jpeg", 80)
            b64_image = base64.b64encode(img_data).decode("utf-8")
            doc.close()
            return b64_image
        except Exception as e:
            print(f"Error in get_page_image: {e}")
            return ""

