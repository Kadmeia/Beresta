import os
import re

class LayoutProcessor:
    def __init__(self):
        self.docling_converter = None
        self.pp_structure = None

    def check_engine(self, engine_name):
        if engine_name == 'docling':
            try:
                import docling
                return True
            except ImportError:
                return False
        elif engine_name == 'ppstructure':
            try:
                from paddleocr import PPStructure
                return True
            except ImportError:
                return False
        return False

    def _run_pip_with_progress(self, packages, progress_callback):
        import subprocess
        import sys
        cmd = [sys.executable, "-m", "pip", "install"] + packages
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            buffer = []
            while True:
                char = process.stdout.read(1)
                if not char:
                    break
                if char in ('\r', '\n'):
                    line = "".join(buffer).strip()
                    if line and progress_callback:
                        if "Downloading" in line or "Collecting" in line or "%" in line or "MB" in line or "kB" in line or "━" in line:
                            short_line = line if len(line) < 80 else line[:77] + "..."
                            progress_callback(short_line)
                        elif "Successfully installed" in line:
                            progress_callback("Установка библиотек завершена...")
                        elif "ERROR:" in line or "error:" in line.lower():
                            print(f"PIP ERROR: {line}")
                    buffer = []
                else:
                    buffer.append(char)
            process.wait()
            if process.returncode != 0:
                raise Exception(f"Код {process.returncode}")
            return True
        except Exception as e:
            raise Exception(f"Сбой установки: {str(e)}")

    def download_engine(self, engine_name, progress_callback=None):
        import sys
        import subprocess
        
        if engine_name == 'docling':
            if progress_callback:
                progress_callback("Подготовка окружения для Docling...")
            try:
                # Install pip packages dynamically
                if progress_callback:
                    progress_callback("Установка библиотек Docling (~2 ГБ, включая PyTorch). Это может занять несколько минут...")
                # Use streaming pip install
                self._run_pip_with_progress(["--upgrade", "pip"], None)
                self._run_pip_with_progress(["docling", "beautifulsoup4"], progress_callback)
                
                import site
                import importlib
                sys.path.append(site.getusersitepackages())
                importlib.invalidate_caches()
                
                import docling
                from docling.document_converter import DocumentConverter
                # Initialize converter to trigger model download
                if progress_callback:
                    progress_callback("Скачивание нейросетевых моделей Docling...")
                self.docling_converter = DocumentConverter()
                if progress_callback:
                    progress_callback("Скачивание завершено!")
                return True
            except Exception as e:
                print(f"Docling download error: {e}")
                if progress_callback:
                    progress_callback(f"Ошибка загрузки: {str(e)}")
                return False
                
        elif engine_name == 'ppstructure':
            if progress_callback:
                progress_callback("Подготовка окружения для PP-Structure...")
            try:
                if progress_callback:
                    progress_callback("Установка библиотек PaddleOCR и OpenCV (~200 МБ)...")
                    
                self._run_pip_with_progress(["--upgrade", "pip"], None)
                self._run_pip_with_progress(["paddlepaddle", "paddleocr==2.8.1", "opencv-python-headless>=4.8.0", "beautifulsoup4", "PyMuPDF", "numpy<2.0.0"], progress_callback)
                
                import site
                import importlib
                sys.path.append(site.getusersitepackages())
                importlib.invalidate_caches()
                
                try:
                    from paddleocr import PPStructureV3 as PPStructure
                except ImportError:
                    from paddleocr import PPStructure
                
                # --- HOOK FOR PADDLEOCR ---
                import paddleocr.paddleocr
                orig_get_model_config = paddleocr.paddleocr.get_model_config
                def hooked_get_model_config(task, version, sub_task, lang):
                    if sub_task == 'layout' and lang in ['ru', 'cyrillic']:
                        lang = 'en'
                    return orig_get_model_config(task, version, sub_task, lang)
                paddleocr.paddleocr.get_model_config = hooked_get_model_config
                # --------------------------
                
                import logging
                logging.getLogger('ppocr').setLevel(logging.ERROR)
                
                if progress_callback:
                    progress_callback("Скачивание моделей PP-Structure (~200 МБ)...")
                self.pp_structure = PPStructure(lang='ru', show_log=False)
                if progress_callback:
                    progress_callback("Скачивание завершено!")
                return True
            except Exception as e:
                print(f"PPStructure download error: {e}")
                if progress_callback:
                    progress_callback(f"Ошибка загрузки: {str(e)}")
                return False
        return False

    def extract_with_docling(self, file_path, status_callback=None):
        if not self.docling_converter:
            if status_callback:
                status_callback("Инициализация Docling...")
            from docling.document_converter import DocumentConverter
            self.docling_converter = DocumentConverter()

        if status_callback:
            status_callback("Анализ верстки и таблиц (Docling)...")
            
        try:
            result = self.docling_converter.convert(file_path)
            pages_text = []
            # doc.pages is a dict with page numbers as keys
            for page_no in sorted(result.document.pages.keys()):
                if status_callback:
                    status_callback(f"Экспорт страницы {page_no} (Docling)...")
                page_md = result.document.export_to_markdown(page_no=page_no)
                pages_text.append({'page_num': page_no, 'text': page_md})
            return pages_text
        except Exception as e:
            print(f"Docling extraction error: {e}")
            raise ValueError(f"Ошибка извлечения через Docling: {e}")

    def extract_with_ppstructure(self, file_path, status_callback=None):
        if not self.pp_structure:
            if status_callback:
                status_callback("Инициализация PP-Structure...")
            try:
                from paddleocr import PPStructureV3 as PPStructure
            except ImportError:
                from paddleocr import PPStructure
                
            # --- HOOK FOR PADDLEOCR ---
            # PaddleOCR's PPStructure crashes if lang='ru' because it tries to find 
            # a Russian layout model, which doesn't exist (only 'en' and 'ch' exist).
            # We hook the config fetcher to force 'en' only for the 'layout' subtask.
            import paddleocr.paddleocr
            orig_get_model_config = paddleocr.paddleocr.get_model_config
            def hooked_get_model_config(task, version, sub_task, lang):
                if sub_task == 'layout' and lang in ['ru', 'cyrillic']:
                    lang = 'en'
                return orig_get_model_config(task, version, sub_task, lang)
            paddleocr.paddleocr.get_model_config = hooked_get_model_config
            # --------------------------

            import logging
            logging.getLogger('ppocr').setLevel(logging.ERROR)
            self.pp_structure = PPStructure(lang='ru', show_log=False)
            
        if status_callback:
            status_callback("Анализ верстки и таблиц (PP-Structure)...")
            
        try:
            import cv2
            import fitz
            import numpy as np
            
            doc = fitz.open(file_path)
            full_markdown = []
            
            for i in range(len(doc)):
                if status_callback:
                    status_callback(f"Структурный анализ (стр. {i+1})...")
                page = doc[i]
                pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                if pix.n == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
                elif pix.n == 1:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
                elif pix.n == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                
                result = self.pp_structure(img)
                
                # Convert PPStructure result to basic Markdown
                page_md = ""
                for region in result:
                    if region['type'] == 'table':
                        html = region['res']['html']
                        # Basic HTML table to text (rough fallback)
                        # A proper html to md parser would be better, but we do a simple extraction
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(html, 'html.parser')
                        rows = soup.find_all('tr')
                        for r in rows:
                            cols = r.find_all(['td', 'th'])
                            page_md += "| " + " | ".join([c.get_text().strip() for c in cols]) + " |\n"
                        page_md += "\n"
                    else:
                        text_lines = []
                        for line in region['res']:
                            text_lines.append(line['text'])
                        page_md += " ".join(text_lines) + "\n\n"
                        
                full_markdown.append({'page_num': i + 1, 'text': page_md})
                
            return full_markdown
        except Exception as e:
            print(f"PPStructure extraction error: {e}")
            raise ValueError(f"Ошибка извлечения через PP-Structure: {e}")

    def extract_text(self, file_path, engine="docling", status_callback=None):
        if engine == "docling":
            return self.extract_with_docling(file_path, status_callback)
        elif engine == "ppstructure":
            return self.extract_with_ppstructure(file_path, status_callback)
        else:
            raise ValueError(f"Unknown layout engine: {engine}")

    def unload_engine(self):
        self.docling_converter = None
        self.pp_structure = None
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if hasattr(torch, 'mps') and torch.mps.is_available():
                torch.mps.empty_cache()
        except ImportError:
            pass

