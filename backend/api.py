import os

# Clean proxy environment variables to prevent httpx.InvalidURL: Invalid port: ':1'
for key in ['no_proxy', 'NO_PROXY']:
    if key in os.environ:
        parts = [p for p in os.environ[key].split(',') if p != '::1' and p != '::1/128']
        os.environ[key] = ','.join(parts)

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

    # Дополнительные шаблоны для рукописного текста и некачественного OCR
    city_pattern = re.compile(r'^\s*#*\s*[гГrR]\s*\.\s*[А-ЯA-Z]', re.IGNORECASE)
    quote_pattern = re.compile(r'[«\"“]\s*[»\"”]\s*\d+')
    date_pattern = re.compile(r'\b\d{1,2}\s+\S*\s*\d{4}\b')
        
    print(f"[DEBUG] is_new_document_start: подготовлено {len(lines)} строк для проверки")
    for i, line in enumerate(lines[:10]):  # проверяем первые 10 строк
        line_clean = line.strip().upper()
        if not line_clean:
            continue
        
        # Фильтруем строки, которые содержат слова, характерные для обычного текста или подписей, а не заголовков
        stop_words = [
            'ЯВЛЯЕТСЯ', 'ОБЯЗУЕТСЯ', 'СОСТАВЛЕН', 'ЭКЗЕМПЛ', 'КАЖДОЙ', 
            'СИЛОЙ', 'ОПЛАТИ', 'СТОИМОСТЬ', 'ПРАВА СТОРОН', 
            'ПОДПИСИ СТОРОН', 'МЕСТО НАХОЖДЕНИЯ', 'РЕКВИЗИТЫ СТОРОН',
            'АДРЕСА И РЕКВИЗИТЫ', 'ПОДПИСАЛИ', 'ПОДПИСЬ', 'ПЕЧАТЬ', 
            'ГЕНЕРАЛЬНЫЙ ДИРЕКТОР', 'ВСТУПАЕТ В СИЛУ', 'НАПРАВЛЕННЫЕ', 
            'ФАЙЛООБМЕН', 'ЗАКАЗЧИК', 'ИСПОЛНИТЕЛЬ', 'М.П.'
        ]
        if any(sw in line_clean for sw in stop_words):
            print(f"[DEBUG] Пропущена строка (найдено стоп-слово): '{line_clean[:50]}'")
            continue
        
        word_count = len(line_clean.split())
        print(f"[DEBUG] Проверка строки {i}: '{line_clean[:50]}...' (слов: {word_count})")
        
        # 1. Проверка стандартных ключевых слов
        for kw, pattern in kw_patterns.items():
            match = pattern.search(line_clean)
            if match:
                print(f"[DEBUG] Найдено ключевое слово: {kw}")
                if word_count <= 10:
                    return True
                if match.start(1) <= 15 and word_count <= 25:
                    return True
                    
        # 2. Проверка шаблона города (г. Москва, r. M, Г. Пермь)
        if city_pattern.search(line):
            print(f"[DEBUG] Найден шаблон города в строке {i}: {line}")
            return True
            
        # 3. Проверка шаблона пустых кавычек и номера («  » 1214)
        if quote_pattern.search(line):
            print(f"[DEBUG] Найден шаблон кавычек/номера в строке {i}: {line}")
            return True

        # 4. Проверка шаблона даты (## 30  2023 .)
        if date_pattern.search(line):
            print(f"[DEBUG] Найден шаблон даты в строке {i}: {line}")
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

    def check_all_dependencies_exist(self):
        """Checks if all required local models, llama-server, and libraries are installed."""
        missing = self.get_missing_dependencies()
        return len(missing) == 0

    def get_missing_dependencies(self):
        """Returns a list of missing dependencies with descriptions and sizes."""
        missing = []
        try:
            # 1. llama-server
            if not self.model_manager.check_llama_server_exists():
                missing.append({
                    "id": "llama_server",
                    "name": "Движок llama-server",
                    "size": "30 МБ",
                    "size_bytes": 30 * 1024 * 1024
                })
            # 2. LLM Model
            if not self.model_manager.check_model_exists("accurate_9b"):
                missing.append({
                    "id": "model",
                    "name": "ИИ-модель Qwen 9B",
                    "size": "5.5 ГБ",
                    "size_bytes": int(5.5 * 1024 * 1024 * 1024)
                })
            # 3. PaddleOCR
            if not self.pdf_processor.check_paddleocr_exists():
                missing.append({
                    "id": "paddleocr",
                    "name": "Модели PaddleOCR",
                    "size": "100 МБ",
                    "size_bytes": 100 * 1024 * 1024
                })
            # 4. Docling
            if not self.layout_processor.check_engine("docling"):
                missing.append({
                    "id": "docling",
                    "name": "Библиотека Docling",
                    "size": "2.0 ГБ",
                    "size_bytes": int(2.0 * 1024 * 1024 * 1024)
                })
            # 5. PP-Structure
            if not self.layout_processor.check_engine("ppstructure"):
                missing.append({
                    "id": "ppstructure",
                    "name": "Библиотека PP-Structure",
                    "size": "200 МБ",
                    "size_bytes": 200 * 1024 * 1024
                })
        except Exception as e:
            print(f"Error getting missing dependencies: {e}")
        return missing

    def get_processing_estimate(self, file_paths, app_mode, ocr_engine, llm_active):
        """
        Estimates the processing time in seconds based on hardware specs (CPU, GPU, RAM),
        file types, total page counts, and chosen pipeline settings.
        """
        import sys
        import os
        import platform
        import psutil
        
        # 1. Считаем общее количество страниц
        total_pages = 0
        total_docs = len(file_paths)
        is_docx_only = True
        
        for path in file_paths:
            if not os.path.exists(path):
                continue
            ext = path.split('.')[-1].lower()
            if ext == 'pdf':
                is_docx_only = False
                try:
                    import fitz
                    doc = fitz.open(path)
                    total_pages += len(doc)
                    doc.close()
                except:
                    total_pages += 1 # fallback
            elif ext == 'docx':
                total_pages += 1 # docx parsed extremely fast, counts as 1 page weight
            else:
                is_docx_only = False
                total_pages += 1 # images, etc.

        # 2. Детектируем характеристики железа
        cpu_count = os.cpu_count() or 4
        
        # RAM
        total_ram_gb = 8.0
        try:
            total_ram_gb = psutil.virtual_memory().total / (1024**3)
        except:
            try:
                if sys.platform == 'darwin':
                    import subprocess
                    res = subprocess.run(['sysctl', 'hw.memsize'], capture_output=True, text=True)
                    total_ram_gb = int(res.stdout.split()[-1]) / (1024**3)
            except:
                pass

        # GPU
        has_gpu = False
        gpu_type = "CPU"
        if sys.platform == 'darwin':
            # Apple Silicon M-series check
            if platform.machine().lower() in ['arm64', 'aarch64']:
                has_gpu = True
                gpu_type = "Apple Silicon"
        else:
            try:
                import torch
                if torch.cuda.is_available():
                    has_gpu = True
                    gpu_type = "NVIDIA CUDA"
            except:
                pass

        # 3. Моделируем скорость
        # Базовое время обработки 1 страницы скана (в секундах)
        base_ocr_time = 4.0 # Default: paddleocr
        if ocr_engine == 'docling':
            base_ocr_time = 8.0
        elif ocr_engine == 'ppstructure':
            base_ocr_time = 6.0
        elif ocr_engine == 'applevision':
            base_ocr_time = 0.5

        # Коэффициенты ускорения за счет GPU/архитектуры
        if has_gpu:
            if gpu_type == "NVIDIA CUDA":
                ocr_speed_factor = 0.25 # в 4 раза быстрее
                llm_speed_factor = 0.12 # в 8 раз быстрее (CUDA-ускорение)
            elif gpu_type == "Apple Silicon":
                ocr_speed_factor = 0.40 # в 2.5 раза быстрее (Metal/NE)
                llm_speed_factor = 0.20 # в 5 раз быстрее (Metal/NE)
        else:
            # CPU только
            ocr_speed_factor = 1.0
            llm_speed_factor = 1.0

        # Влияние ядер CPU (для фонового OCR и Docling на CPU)
        cpu_coeff = 1.0 / (min(cpu_count, 8) / 4.0)

        # Влияние оперативной памяти RAM
        if total_ram_gb < 8.0:
            ram_coeff = 1.6
        elif total_ram_gb < 16.0:
            ram_coeff = 1.2
        elif total_ram_gb >= 32.0:
            ram_coeff = 0.85
        else:
            ram_coeff = 1.0

        # Расчет времени OCR/Разметки
        if is_docx_only:
            ocr_time = total_docs * 0.3 # DOCX обрабатываются практически мгновенно
        else:
            ocr_time = total_pages * base_ocr_time * cpu_coeff * ram_coeff * ocr_speed_factor

        # Расчет времени работы LLM (Qwen 9B)
        llm_time = 0.0
        if llm_active:
            # Базовое время инференса локальной 9B модели на CPU для одного документа: ~25 секунд
            base_llm_time = 25.0
            llm_time = total_docs * base_llm_time * ram_coeff * llm_speed_factor

        # Фиксированные накладные расходы (запуск сервера, сохранение файлов, UI)
        overhead = 3.0
        if llm_active and not self.model_manager.check_llama_server_exists():
            # Если llama-server еще не запущен, добавляем время на его старт
            overhead += 5.0

        estimated_seconds = int(ocr_time + llm_time + overhead)
        
        # Минимальный лимит, если документов много или страницы большие
        if estimated_seconds < 5:
            estimated_seconds = 5
            
        print(f"[ESTIMATION] Hardware detected: {cpu_count} CPU cores, {total_ram_gb:.1f} GB RAM, GPU: {gpu_type}.")
        print(f"[ESTIMATION] Params: pages={total_pages}, docs={total_docs}, is_docx={is_docx_only}, ocr={ocr_engine}, llm_active={llm_active}.")
        print(f"[ESTIMATION] Estimated OCR time: {ocr_time:.1f}s, LLM time: {llm_time:.1f}s. Total estimate: {estimated_seconds} seconds.")
        
        return estimated_seconds

    def download_all_dependencies(self):
        """Downloads all missing dependencies sequentially."""
        import threading
        
        def task():
            try:
                # 1. Download llama-server
                if not self.model_manager.check_llama_server_exists():
                    self.send_status("1/5 Установка движка llama-server...")
                    success = self.model_manager.download_llama_server(self.send_status)
                    if not success:
                        raise Exception("Не удалось скачать llama-server")

                # 2. Download LLM model
                if not self.model_manager.check_model_exists("accurate_9b"):
                    self.send_status("2/5 Установка ИИ-модели Qwen 9B (~5.5 ГБ)...")
                    success = self.model_manager.download_model("accurate_9b", self.send_status)
                    if success != "Done":
                        raise Exception("Не удалось скачать ИИ-модель")

                # 3. Download PaddleOCR
                if not self.pdf_processor.check_paddleocr_exists():
                    self.send_status("3/5 Установка моделей распознавания PaddleOCR...")
                    success = self.pdf_processor.download_paddleocr(self.send_status)
                    if not success:
                        raise Exception("Не удалось скачать модели PaddleOCR")

                # 4. Download Docling layout engine
                if not self.layout_processor.check_engine("docling"):
                    self.send_status("4/5 Установка библиотек Docling (~2 ГБ)...")
                    success = self.layout_processor.download_engine("docling", self.send_status)
                    if not success:
                        raise Exception("Не удалось установить библиотеки Docling")

                # 5. Download PP-Structure layout engine
                if not self.layout_processor.check_engine("ppstructure"):
                    self.send_status("5/5 Установка библиотек PP-Structure...")
                    success = self.layout_processor.download_engine("ppstructure", self.send_status)
                    if not success:
                        raise Exception("Не удалось установить библиотеки PP-Structure")

                self.send_status("Все компоненты успешно установлены! Запуск программы...")
                if self.window:
                    self.window.evaluate_js("window.dependenciesDownloadComplete && window.dependenciesDownloadComplete(true)")

            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_status(f"Ошибка при установке компонентов: {str(e)}")
                if self.window:
                    self.window.evaluate_js(f"window.dependenciesDownloadComplete && window.dependenciesDownloadComplete(false)")

        threading.Thread(target=task, daemon=True).start()
        return "Started"

    def exit_app(self):
        """Destroys the window and exits the application."""
        import os
        try:
            if self.window:
                self.window.destroy()
        except:
            pass
        os._exit(0)

    def get_models_status(self):
        server_exists = self.model_manager.check_llama_server_exists()
        return {
            "accurate_9b": {
                "installed": self.model_manager.check_model_exists("accurate_9b") and server_exists,
                "active": True
            }
        }
        
    def get_gemini_config(self):
        return {"api_key": "", "model": ""}
        
    def save_gemini_config(self, api_key, model):
        return True

    def get_ollama_config(self):
        return {"model": "", "base_url": ""}

    def save_ollama_config(self, model, base_url):
        return True
        
    def set_active_model(self, model_type):
        self.model_manager.set_active_model_type("accurate_9b")
        if self.llm_handler:
            self.llm_handler.unload_model()
            self.llm_handler = None
        return True
        
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
        import time
        t_pipeline_start = time.time()

        if extract_settings is None:
            extract_settings = {"split": True, "use_ai": True}

        # Step 1: Run OCR/text extraction on all files and save page texts in memory
        all_files_pages = []
        total_files = len(file_paths)
        for idx, path in enumerate(file_paths, 1):
            self.send_status("Распознаем текст...")
            t_ocr_start = time.time()
            
            def status_wrapper(msg):
                self.send_status(msg)

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
                
                t_ocr_end = time.time()
                print(f"[TIMING] OCR для {os.path.basename(path)} занял {t_ocr_end - t_ocr_start:.2f} сек.")
                        
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
        active = "accurate_9b"

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
            self.send_status(f"Анализируем документ... {start_percent}%")
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
                    is_new = False
                    t_split_start = time.time()
                    if mode == "rename":
                        is_new = False
                    elif mode == "extract":
                        is_candidate = extract_settings.get('split', True) and is_new_document_start(text)
                        if is_candidate:
                            is_new = self.llm_handler.is_new_document(
                                text, page_num,
                                progress_callback=lambda tokens: self.send_status(f"Определяем границы документа... {percent}%")
                            )
                    else:
                        is_candidate = is_new_document_start(text)
                        if is_candidate:
                            is_new = self.llm_handler.is_new_document(
                                text, page_num,
                                progress_callback=lambda tokens: self.send_status(f"Определяем границы документа... {percent}%")
                            )
                    t_split_end = time.time()
                    if is_candidate:
                        print(f"[TIMING] Проверка границ (стр. {page_num}) заняла {t_split_end - t_split_start:.2f} сек.")
                    
                    print(f"DEBUG PIPELINE: page_num={page_num}, is_candidate={is_candidate}, is_new={is_new}, text_start={repr(text[:200])}")
                    
                    if is_new or current_doc is None:
                        retries = 0
                        max_retries = 2
                        
                        text = text.replace('N@', '№').replace('N?', '№')
                        
                        if mode == "extract" and extract_settings.get("use_ai", True):
                            print(f"[INFO] Запуск ИИ коррекции текста для страницы {page_num}...")
                            self.send_status(f"Проводим умную коррекцию... {percent}%")
                            proofread_text = self.llm_handler.proofread_text(
                                p['text'],
                                progress_callback=lambda tokens: self.send_status(f"Проводим умную коррекцию... {percent}%")
                            )
                            text = proofread_text[:3000]
                            p['text'] = proofread_text
                        
                        print(f"[INFO] Запуск извлечения реквизитов (analyze_text) для страницы {page_num}...")
                        self.send_status(f"Извлекаем юридические реквизиты... {percent}%")
                        t_name_start = time.time()
                        analysis = self.llm_handler.analyze_text(
                            text, page_num, retry=retries,
                            progress_callback=lambda tokens: self.send_status(f"Извлекаем юридические реквизиты... {percent}%")
                        )
                        
                        while (analysis.get('short_name') == 'Документ' or not analysis.get('date') or analysis.get('date') == '-') and retries < max_retries:
                            retries += 1
                            self.send_status(f"Перепроверка данных... {percent}%")
                            
                            if retries == 1:
                                self.send_status(f"Улучшаем качество текста... {percent}%")
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
                                progress_callback=lambda tokens: self.send_status(f"Перепроверка данных... {percent}%")
                            )
                        t_name_end = time.time()
                        print(f"[TIMING] Именование/Реквизиты (стр. {page_num}) заняло {t_name_end - t_name_start:.2f} сек. Попыток: {retries + 1}")
                        print(f"[INFO] Результат анализа: {analysis}")

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
                                    self.send_status(f"Проводим умную коррекцию... {percent}%")
                                    proofread_text = self.llm_handler.proofread_text(
                                        p['text'],
                                        progress_callback=lambda tokens: self.send_status(f"Проводим умную коррекцию... {percent}%")
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

        t_pipeline_end = time.time()
        print(f"[TIMING] Общее время работы алгоритма: {t_pipeline_end - t_pipeline_start:.2f} сек.")
        self.send_status("Ожидание проверки... 100%")
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
                
                # Ограничение длины имени файла во избежание ошибки "File name too long" (max 255 байт)
                new_name_bytes = new_name.encode('utf-8')
                if len(new_name_bytes) > 150:
                    new_name = new_name_bytes[:150].decode('utf-8', errors='ignore').strip(' .')
                
                current_output_dir = output_dir.strip() if output_dir else os.path.dirname(original_path)
                os.makedirs(current_output_dir, exist_ok=True)
                
                self.send_status(f"Сохранение: {new_name}...")
                
                current_saved_files = []
                
                if mode == "extract":
                    for fmt in export_formats:
                        if fmt == "docx":
                            final_path = self.docx_processor.create_docx_from_text(
                                item.get('text', ''),
                                new_name,
                                current_output_dir
                            )
                            current_saved_files.append(final_path)
                        elif fmt == "md":
                            final_path = os.path.join(current_output_dir, new_name.replace('.docx', '').replace('.pdf', '') + '.md')
                            with open(final_path, 'w', encoding='utf-8') as f:
                                f.write(item.get('text', ''))
                            current_saved_files.append(final_path)
                        elif fmt == "txt":
                            final_path = os.path.join(current_output_dir, new_name.replace('.docx', '').replace('.pdf', '') + '.txt')
                            with open(final_path, 'w', encoding='utf-8') as f:
                                f.write(item.get('text', ''))
                            current_saved_files.append(final_path)
                elif original_path.lower().endswith('.docx'):
                    # Save docx
                    final_path = self.docx_processor.split_and_save(
                        original_path, 
                        start_page,
                        end_page,
                        new_name, 
                        current_output_dir
                    )
                    current_saved_files.append(final_path)
                else:
                    # Save pdf
                    final_path = self.pdf_processor.split_and_save(
                        original_path, 
                        start_page, 
                        end_page, 
                        new_name, 
                        current_output_dir
                    )
                    current_saved_files.append(final_path)
                    
                saved_files.extend(current_saved_files)
                
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

